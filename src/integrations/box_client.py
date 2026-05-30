"""Box integration.

Four responsibilities:

1. Player state persistence — save and load per-player progress to Box so
   sessions survive across machines. Always mirrors locally so the game
   works offline.

2. AI-powered contextual hints — when a player requests a hint, upload the
   relevant sandbox file to Box and call POST /ai/ask to get a hint that
   is specific to the actual file content, not generic documentation.
   Deletes the temp file from Box after the hint is returned.

3. Challenge task tracking — at the start of each theme session, upload
   sandbox files to Box and create a Box Task on each file whose challenge
   the player needs to solve. As challenges are completed, mark the
   corresponding tasks complete. Judges watching Box web UI see tasks
   ticking off on real files in real time. Clean up uploaded files at
   session end.

4. Global leaderboard — maintain a single shared leaderboard.json in Box
   that all players write to on theme completion. Uses Box file lock API
   to prevent concurrent write corruption. Players can query the current
   standings at any time.

   BONUS: generate a plain-text completion certificate, upload it to Box,
   create a shared link with open access, and return the URL.

Auth: prefers CCG (auto-refreshing, non-expiring) when BOX_ENTERPRISE_ID is
set, otherwise falls back to the 60-minute Developer Token. All functions
degrade gracefully — if Box is not configured or any call fails, they return
None/False/empty without raising. Implemented in TICKET-5.
"""

import io
import json
import os
import pathlib
import time
from datetime import datetime

import requests
from rich.console import Console
from dotenv import load_dotenv

load_dotenv()
console = Console()

_client = None
_box_enabled = False

BOX_DEVELOPER_TOKEN = os.environ.get("BOX_DEVELOPER_TOKEN")
BOX_CLIENT_ID = os.environ.get("BOX_CLIENT_ID")
BOX_CLIENT_SECRET = os.environ.get("BOX_CLIENT_SECRET")
BOX_ENTERPRISE_ID = os.environ.get("BOX_ENTERPRISE_ID")
BOX_STATE_FOLDER_ID = os.environ.get("BOX_STATE_FOLDER_ID")

_API = "https://api.box.com/2.0"


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_box() -> None:
    """Initialise the Box client. Call once at game startup.

    Uses CCG auth (auto-refreshing) when BOX_ENTERPRISE_ID + client creds are
    present; otherwise the Developer Token. Sets module-level flags so every
    other function knows whether Box is available.
    """
    global _client, _box_enabled

    if not (BOX_CLIENT_ID and BOX_CLIENT_SECRET and
            (BOX_ENTERPRISE_ID or BOX_DEVELOPER_TOKEN)):
        console.print("[dim][Box] Not configured — using local storage[/]")
        return

    try:
        from boxsdk import Client
        if BOX_ENTERPRISE_ID:
            from boxsdk import CCGAuth
            auth = CCGAuth(
                client_id=BOX_CLIENT_ID,
                client_secret=BOX_CLIENT_SECRET,
                enterprise_id=BOX_ENTERPRISE_ID,
            )
            mode = "CCG"
        else:
            from boxsdk import OAuth2
            auth = OAuth2(
                client_id=BOX_CLIENT_ID,
                client_secret=BOX_CLIENT_SECRET,
                access_token=BOX_DEVELOPER_TOKEN,
            )
            mode = "developer token"

        _client = Client(auth)
        user = _client.user().get()
        _box_enabled = True
        console.print(
            f"[dim][Box] Connected as {user.name} (via {mode})[/]")
        if not BOX_STATE_FOLDER_ID:
            console.print(
                "[dim][Box] BOX_STATE_FOLDER_ID not set — run "
                "scripts/setup_box.py; using local storage for now[/]")
    except Exception as e:
        console.print(
            f"[dim][Box] Auth failed: {e} — using local storage[/]")
        _box_enabled = False


def _box_ready() -> bool:
    """True only when Box is connected AND a state folder is configured."""
    return bool(_box_enabled and _client and BOX_STATE_FOLDER_ID)


# ---------------------------------------------------------------------------
# Shared Box helpers
# ---------------------------------------------------------------------------

def _find_file_in_folder(folder_id: str, filename: str):
    """Return the Box file object named `filename` in a folder, or None."""
    try:
        for item in _client.folder(folder_id).get_items():
            if item.name == filename and item.type == "file":
                return _client.file(item.id)
    except Exception:
        pass
    return None


def _upload_or_update(folder_id: str, filename: str, content: str):
    """Create or update a text file in a Box folder. Returns the file or None."""
    try:
        stream = io.BytesIO(content.encode("utf-8"))
        existing = _find_file_in_folder(folder_id, filename)
        if existing:
            return existing.update_contents_with_stream(stream)
        return _client.folder(folder_id).upload_stream(stream, filename)
    except Exception as e:
        console.print(f"[dim][Box] Upload failed for {filename}: {e}[/]")
        return None


# ---------------------------------------------------------------------------
# Player state (Responsibility 1)
# ---------------------------------------------------------------------------

def save_player_state(player: dict) -> bool:
    """Save player state to Box (if connected) and always to local backup."""
    data = {**player, "last_saved": datetime.now().isoformat()}
    json_str = json.dumps(data, indent=2)

    _save_local(data)  # always

    if not _box_ready():
        return True

    try:
        filename = f"player-{player['id']}.json"
        return _upload_or_update(
            BOX_STATE_FOLDER_ID, filename, json_str) is not None
    except Exception as e:
        console.print(f"[dim][Box] Save failed: {e}[/]")
        return False


def load_player_state(player_id: str) -> dict | None:
    """Load player state, trying Box first then the local backup."""
    if _box_ready():
        try:
            found = _find_file_in_folder(
                BOX_STATE_FOLDER_ID, f"player-{player_id}.json")
            if found:
                return json.loads(found.content().decode("utf-8"))
        except Exception as e:
            console.print(f"[dim][Box] Load failed: {e}[/]")
    return _load_local(player_id)


# === Local fallback ===

def _local_dir() -> pathlib.Path:
    p = pathlib.Path.home() / ".shellquest"
    p.mkdir(exist_ok=True)
    return p


def _save_local(data: dict) -> None:
    try:
        with open(_local_dir() / f"player-{data['id']}.json", "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _load_local(player_id: str) -> dict | None:
    try:
        path = _local_dir() / f"player-{player_id}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# AI-powered hints (Responsibility 2)
# ---------------------------------------------------------------------------

def fetch_ai_hint(command: str, file_path: str) -> str | None:
    """Ask Box AI for a contextual hint about using `command` on a file.

    Uploads the file to Box, calls POST /ai/ask (single_item_qa), deletes the
    temp file, and returns the hint string — or None on any failure.
    """
    if not _box_ready():
        return None

    temp_file = None
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        # Keep a real extension at the END of the name — Box AI needs to
        # recognise the file as text to extract it, or it 400s.
        ext = os.path.splitext(file_path)[1] or ".txt"
        temp_name = f"_hint_{datetime.now():%H%M%S%f}{ext}"
        temp_file = _client.folder(BOX_STATE_FOLDER_ID).upload_stream(
            io.BytesIO(content), temp_name)

        prompt = (
            f"A learner is practising the shell command '{command}' on this "
            f"file. In one or two sentences, give a gentle hint about how "
            f"'{command}' could help them analyse THIS file's contents. "
            f"Do NOT give the full command or answer — just a nudge."
        )
        payload = {
            "mode": "single_item_qa",
            "prompt": prompt,
            "items": [{"id": temp_file.id, "type": "file"}],
        }
        # Use raw requests: the SDK's make_request doesn't set a JSON
        # content-type for /ai/ask and Box rejects it (400). A just-uploaded
        # file may not be processed for AI yet — Box returns 412 ("resource
        # modified, retry") until it's ready, so retry a few times.
        token = getattr(_client.auth, "access_token", None) or \
            BOX_DEVELOPER_TOKEN
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        for attempt in range(5):
            resp = requests.post(
                f"{_API}/ai/ask", headers=headers,
                data=json.dumps(payload), timeout=40)
            if resp.status_code == 200:
                return resp.json().get("answer", "").strip() or None
            if resp.status_code == 412 and attempt < 4:
                time.sleep(3)
                continue
            console.print(
                f"[dim][Box] AI hint HTTP {resp.status_code}[/]")
            return None
        return None
    except Exception as e:
        console.print(f"[dim][Box] AI hint failed: {e}[/]")
        return None
    finally:
        if temp_file is not None:
            try:
                _client.file(temp_file.id).delete()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Challenge task tracking (Responsibility 3)
# ---------------------------------------------------------------------------

def create_session_tasks(
    files: list[dict],
    challenges: list[dict],
    sandbox_path: str,
) -> dict:
    """Upload challenge files to Box and attach a Task to each.

    Returns {challenge_id: {"task_id": str, "file_id": str}}; {} if disabled.
    """
    if not _box_ready():
        return {}

    task_map = {}
    for challenge in challenges:
        target = challenge.get("validation", {}).get("target", "")
        if not target:
            continue
        # Use the first path segment as the file to attach the task to.
        file_entry = next(
            (f for f in files if f["path"] == target
             or target.startswith(f["path"])), None)
        if not file_entry:
            continue
        try:
            uploaded = _upload_or_update(
                BOX_STATE_FOLDER_ID,
                f"_task_{challenge['id']}_{os.path.basename(file_entry['path'])}",
                file_entry["content"])
            if not uploaded:
                continue
            task = _client.file(uploaded.id).create_task(
                message=challenge.get("instruction", challenge["id"])[:250],
                action="complete")
            task_map[challenge["id"]] = {
                "task_id": task.id, "file_id": uploaded.id}
        except Exception as e:
            console.print(
                f"[dim][Box] Task setup failed for {challenge['id']}: {e}[/]")
    if task_map:
        console.print(
            f"[dim][Box] Created {len(task_map)} challenge tasks[/]")
    return task_map


def complete_challenge_task(task_id: str) -> None:
    """Mark a Box Task complete (resolve its assignment). No-op if disabled."""
    if not (_box_enabled and _client and task_id):
        return
    try:
        task = _client.task(task_id)
        # A task is "completed" by resolving its assignment(s).
        assignments = task.get_assignments()
        resolved = False
        for assignment in assignments:
            assignment.update_info(data={"resolution_state": "completed"})
            resolved = True
        if not resolved:
            # No assignment yet — assign to the current user, then resolve.
            me = _client.user().get()
            assignment = task.assign(me)
            assignment.update_info(data={"resolution_state": "completed"})
    except Exception as e:
        console.print(f"[dim][Box] Task complete failed: {e}[/]")


def cleanup_session_tasks(task_map: dict) -> None:
    """Delete all Box files uploaded for this session's tasks. No-op if disabled."""
    if not (_box_enabled and _client):
        return
    for entry in (task_map or {}).values():
        try:
            _client.file(entry["file_id"]).delete()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Global leaderboard (Responsibility 4)
# ---------------------------------------------------------------------------

_LEADERBOARD = "leaderboard.json"


def update_leaderboard(
    player: dict,
    theme_id: str,
    score: int,
    total_time: int,
    stars: str,
) -> None:
    """Add/update this player's score in the shared Box leaderboard.

    lock → download → update → re-upload → unlock. No-op if disabled.
    """
    if not _box_ready():
        return

    box_file = _find_file_in_folder(BOX_STATE_FOLDER_ID, _LEADERBOARD)
    locked = False
    try:
        scores = []
        if box_file:
            try:
                box_file.lock()
                locked = True
            except Exception:
                pass  # best-effort lock
            scores = json.loads(box_file.content().decode("utf-8"))

        entry = {
            "name": player.get("name", "Explorer"),
            "github": player.get("github_username", ""),
            "theme_id": theme_id,
            "score": score,
            "time_seconds": total_time,
            "stars": stars,
        }
        # Replace any existing entry for this player+theme.
        scores = [s for s in scores
                  if not (s.get("name") == entry["name"]
                          and s.get("theme_id") == theme_id)]
        scores.append(entry)
        scores.sort(key=lambda s: s.get("score", 0), reverse=True)

        json_str = json.dumps(scores, indent=2)
        if box_file:
            box_file.update_contents_with_stream(
                io.BytesIO(json_str.encode("utf-8")))
        else:
            _client.folder(BOX_STATE_FOLDER_ID).upload_stream(
                io.BytesIO(json_str.encode("utf-8")), _LEADERBOARD)
    except Exception as e:
        console.print(f"[dim][Box] Leaderboard update failed: {e}[/]")
    finally:
        if locked:
            try:
                box_file.unlock()
            except Exception:
                pass


def get_leaderboard() -> list[dict]:
    """Return the current leaderboard, or [] if disabled/empty."""
    if not _box_ready():
        return []
    try:
        box_file = _find_file_in_folder(BOX_STATE_FOLDER_ID, _LEADERBOARD)
        if box_file:
            return json.loads(box_file.content().decode("utf-8"))
    except Exception as e:
        console.print(f"[dim][Box] Leaderboard fetch failed: {e}[/]")
    return []


# ---------------------------------------------------------------------------
# Completion certificate — BONUS
# ---------------------------------------------------------------------------

def create_completion_certificate(
    player: dict,
    theme: dict,
    l1_score: int,
    l1_max: int,
    l2_score: int,
    l2_max: int,
    total_time: int,
    stars: str,
) -> str | None:
    """Generate a text certificate, upload to Box, return a public shared URL."""
    if not _box_ready():
        return None

    total = l1_score + l2_score
    total_max = l1_max + l2_max
    now = datetime.now()
    handle = (f" (@{player['github_username']})"
              if player.get("github_username") else "")

    content = f"""
╔══════════════════════════════════════════════════╗
║            SHELLQUEST COMPLETION REPORT            ║
╚══════════════════════════════════════════════════╝

Player:  {player.get('name', 'Explorer')}{handle}
Theme:   {theme['icon']} {theme['name']}
Date:    {now.strftime('%B %d, %Y')}

────────────────────────────────────────────────────

RESULTS
  Level 1 (Exploration):   {l1_score}/{l1_max} pts
  Level 2 (Analysis):      {l2_score}/{l2_max} pts
  Total:                   {total}/{total_max} pts
  Time:                    {total_time // 60}m {total_time % 60}s
  Rating:                  {stars}

COMMANDS PRACTICED
  Level 1: ls, cat, mkdir, mv, cp
  Level 2: grep, wc, sort, uniq, pipes (|)

────────────────────────────────────────────────────

Verified by ShellQuest — powered by Box & Apify
""".strip()

    try:
        safe_name = player.get("name", "explorer").lower().replace(" ", "-")
        filename = (f"shellquest-{theme['id']}-{safe_name}-"
                    f"{now.strftime('%Y%m%d')}.txt")
        uploaded = _upload_or_update(BOX_STATE_FOLDER_ID, filename, content)
        if not uploaded:
            return None
        shared = _client.file(uploaded.id).get_shared_link(
            access="open", allow_download=True)
        return shared
    except Exception as e:
        console.print(f"[dim][Box] Certificate creation failed: {e}[/]")
        return None
