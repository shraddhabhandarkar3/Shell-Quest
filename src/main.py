"""ShellQuest entry point.

Wires together the engine (sandbox, runner, checker, theme_builder) and the
integrations (Box, Apify) into the interactive game loop. Implemented in TICKET-7.
"""

import atexit
import json
import os
import signal
import sys
import time
import uuid
from datetime import datetime

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.ui import (
    show_title, scraping_status,
    show_level_banner, show_challenge_header,
    show_challenge_success, show_level_complete,
    show_completion, show_status_table, show_goodbye,
    set_terminal_title, show_prompt_reminder,
    game_msg, show_command_output, show_cd_result, console,
    _style,
)

from src.engine.sandbox import create_sandbox, seed_sandbox
from src.engine.runner import execute_command, handle_cd
from src.engine.checker import validate_challenge
from src.engine.theme_builder import build_level_from_theme, compute_challenge_answers
from src.integrations.box_client import (
    init_box, save_player_state, load_player_state, fetch_ai_hint,
    create_session_tasks, complete_challenge_task, cleanup_session_tasks,
    update_leaderboard, get_leaderboard,
    create_completion_certificate,
)
from src.integrations.apify_client import scrape_theme_content, fetch_shell_challenges

console = Console()
_active_cleanup = None


def fetch_github_profile(username: str) -> dict:
    """Fetch GitHub profile via the public REST API (no Apify needed)."""
    import requests
    fallback = {"name": username, "avatar": f"https://github.com/{username}.png", "bio": ""}
    try:
        resp = requests.get(
            f"https://api.github.com/users/{username}",
            headers={"User-Agent": "ShellQuest/1.0"},
            timeout=3,
        )
        if resp.status_code == 200:
            data = resp.json()
            fallback["name"] = data.get("name") or username
            fallback["bio"] = data.get("bio") or ""
    except Exception:
        pass
    return fallback


def fetch_hint(command: str) -> str:
    """Fetch a tldr hint via GitHub raw (no Apify needed)."""
    import requests
    for section in ["common", "linux"]:
        try:
            resp = requests.get(
                f"https://raw.githubusercontent.com/tldr-pages/tldr/main/pages/{section}/{command}.md",
                timeout=5,
            )
            if resp.status_code == 200:
                lines = resp.text.strip().split("\n")
                desc = next((l.lstrip("> ").strip() for l in lines if l.startswith(">")), f"The {command} command")
                examples = [l.strip("`") for l in lines if l.startswith("`") and l.endswith("`")]
                ex_lines = "\n".join(f"  [cyan]$ {e}[/]" for e in examples[:4])
                return f"[yellow]Hint: {desc}[/]\n{ex_lines}" if ex_lines else f"[yellow]Hint: {desc}[/]"
        except Exception:
            continue
    return f"[yellow]Hint: try the [cyan]{command}[/cyan] command[/]"


def main() -> None:
    """Launch the ShellQuest game loop."""
    global _active_cleanup

    def _cleanup_and_exit(sig=None, frame=None):
        if _active_cleanup:
            _active_cleanup()
        console.print("\n[dim]Thanks for playing![/]")
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup_and_exit)
    atexit.register(lambda: _active_cleanup() if _active_cleanup else None)

    show_title()

    # Init Box (graceful if not configured or not yet implemented)
    try:
        init_box()
    except NotImplementedError:
        pass

    # Player setup
    try:
        name = questionary.text("What's your name?").ask()
        if not name:
            name = "Explorer"
        github_user = questionary.text(
            "GitHub username (optional, press Enter to skip):"
        ).ask()
    except KeyboardInterrupt:
        console.print("\n[dim]Thanks for playing![/]")
        return

    player = {
        "id": str(uuid.uuid4()),
        "name": name,
        "github_username": github_user or "",
        "github_avatar": "",
        "github_bio": "",
        "completed_themes": [],
        "total_score": 0,
    }

    if github_user:
        try:
            with console.status("[dim]Looking up GitHub (3s max)...[/]"):
                profile = fetch_github_profile(github_user)
            player["github_avatar"] = profile.get("avatar", "")
            player["github_bio"] = profile.get("bio", "")
            display = profile.get("name", name)
            game_msg(f"Welcome, {display}!", style="dim")
            if player["github_bio"]:
                game_msg(f'"{player["github_bio"]}"', style="dim")
        except NotImplementedError:
            game_msg(f"Welcome, {name}!", style="dim")
    else:
        game_msg(f"Welcome, {name}!", style="dim")

    # Try to load existing state (best-effort)
    try:
        existing = load_player_state(player["id"])
    except NotImplementedError:
        existing = None
    if existing:
        player["completed_themes"] = existing.get("completed_themes", [])
        player["total_score"] = existing.get("total_score", 0)

    # Load themes
    themes_path = os.path.join(os.path.dirname(__file__), "data", "themes.json")
    with open(themes_path) as f:
        themes = json.load(f)["themes"]

    # Main selection loop
    while True:
        console.print()
        completed_ids = [t["theme_id"] for t in player["completed_themes"]]

        choices = []
        for t in themes:
            done = t["id"] in completed_ids
            result = next(
                (r for r in player["completed_themes"] if r["theme_id"] == t["id"]),
                None,
            )
            if done and result:
                label = f"✓ {result.get('stars', '')} {t['icon']} {t['name']}"
            else:
                label = f"  {t['icon']} {t['name']} — {t['description']}"
            choices.append(questionary.Choice(label, value=t["id"]))
        choices.append(questionary.Choice("  Quit", value="quit"))

        try:
            theme_id = questionary.select("Choose your adventure:", choices=choices).ask()
        except KeyboardInterrupt:
            theme_id = None

        if not theme_id or theme_id == "quit":
            set_terminal_title("ShellQuest")
            show_goodbye(name)
            break

        theme = next(t for t in themes if t["id"] == theme_id)

        # Scrape content (Apify → Wikipedia fallback handled inside)
        with scraping_status(theme):
            try:
                scraped = scrape_theme_content(theme)
            except NotImplementedError:
                scraped = None
            if not scraped:
                scraped = _wikipedia_fallback(theme)

        if not scraped:
            game_msg("Couldn't build this theme. Try another.", style="red")
            continue

        level = build_level_from_theme(theme, scraped)

        # Create and seed sandbox
        try:
            sandbox_path, cleanup = create_sandbox()
        except Exception as e:
            game_msg(f"Couldn't create sandbox: {e}", style="red")
            continue

        _active_cleanup = cleanup
        seed_sandbox(sandbox_path, level["files"])
        compute_challenge_answers(level["level_2_challenges"], sandbox_path)

        # Create Box Tasks for all challenges (visible in Box web UI)
        all_challenges = level["level_1_challenges"] + level["level_2_challenges"]
        task_map = create_session_tasks(level["files"], all_challenges, sandbox_path)

        def _cleanup_session():
            cleanup_session_tasks(task_map)
            cleanup()

        # ── Level 1 ──────────────────────────────────────────────────────────
        show_level_banner(theme, 1, level["story_level_1"], level["commands_taught_l1"])

        l1_result = _play_challenges(level["level_1_challenges"], sandbox_path, theme, task_map)

        if l1_result is None:
            _cleanup_session()
            _active_cleanup = None
            continue

        l1_score, l1_max, l1_time = l1_result

        show_level_complete(1, l1_score, l1_max, theme["id"])

        try:
            proceed = questionary.confirm(
                "Ready for Level 2? The data needs analysis now.", default=True
            ).ask()
        except KeyboardInterrupt:
            proceed = False

        if not proceed:
            _save_theme_result(player, theme, l1_score, l1_max, 0, 0, int(l1_time))
            _cleanup_session()
            _active_cleanup = None
            continue

        # ── Level 2 ──────────────────────────────────────────────────────────
        show_level_banner(theme, 2, level["story_level_2"], level["commands_taught_l2"])

        l2_result = _play_challenges(level["level_2_challenges"], sandbox_path, theme, task_map)

        if l2_result is None:
            _save_theme_result(player, theme, l1_score, l1_max, 0, 0, int(l1_time))
            _cleanup_session()
            _active_cleanup = None
            continue

        l2_score, l2_max, l2_time = l2_result

        # ── SO Bonus round ────────────────────────────────────────────────────
        bonus_score = 0
        try:
            with console.status("[dim]Fetching a real challenge from StackOverflow...[/]"):
                so_questions = fetch_shell_challenges(theme)
        except NotImplementedError:
            so_questions = None

        if so_questions:
            import random
            q = random.choice(so_questions[:5])
            console.print(f"\n[yellow]{'━' * 50}[/]")
            console.print("[bold magenta]⭐ BONUS — Real question from StackOverflow[/]")
            game_msg(f'"{q["title"]}"', theme.get("id", ""), style="bold")
            game_msg(
                f"Commands that might help: {', '.join(q['commands'][:4])}",
                theme.get("id", ""), style="dim"
            )
            game_msg(
                "Try to solve it in the sandbox. Type 'done' when finished or 'skip' to skip.",
                theme.get("id", ""), style="dim"
            )
            while True:
                try:
                    user_input = console.input("[magenta]bonus:~$ [/]").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not user_input:
                    continue
                if user_input == "done":
                    bonus_score = 10
                    game_msg("Nice work! +10 bonus pts", theme.get("id", ""), style="green")
                    break
                elif user_input in ("skip", "quit"):
                    game_msg("Skipped.", theme.get("id", ""), style="dim")
                    break
                elif user_input.startswith("cd"):
                    args = user_input[2:].strip() or "~"
                    cd_result = handle_cd(args, sandbox_path, sandbox_path)
                    if cd_result["error"]:
                        show_command_output("", cd_result["error"])
                else:
                    result = execute_command(user_input, sandbox_path, sandbox_path)
                    show_command_output(result["stdout"], result["stderr"])

        # ── Final summary ─────────────────────────────────────────────────────
        total_score = l1_score + l2_score + bonus_score
        total_max = l1_max + l2_max
        total_time = l1_time + l2_time

        if total_score >= total_max * 0.8:
            stars = "★★★"
        elif total_score >= total_max * 0.5:
            stars = "★★☆"
        else:
            stars = "★☆☆"

        show_completion(theme, l1_score, l1_max, l2_score, l2_max, total_time, stars)

        _save_theme_result(
            player, theme, l1_score, l1_max, l2_score, l2_max, int(total_time), stars
        )
        _cleanup_session()
        _active_cleanup = None
        time.sleep(1)


# ---------------------------------------------------------------------------
# Wikipedia fallback (used when Apify client is not yet implemented)
# ---------------------------------------------------------------------------

def _wikipedia_fallback(theme: dict) -> list[dict] | None:
    import requests
    results = []
    for query in theme["scrape_queries"]:
        if "wikipedia.org/wiki/" not in query["url"]:
            continue
        title = query["url"].split("/wiki/")[-1]
        try:
            resp = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
                timeout=10,
                headers={"User-Agent": "ShellQuest/1.0"},
            )
            resp.raise_for_status()
            content = resp.json().get("extract", "")
            if content and len(content) > 50:
                results.append({
                    "url": query["url"],
                    "filename": query["filename"],
                    "content": content,
                })
        except Exception:
            continue
    return results or None


# ---------------------------------------------------------------------------
# Challenge loop
# ---------------------------------------------------------------------------

def _play_challenges(challenges: list, sandbox_path: str, theme: dict, task_map: dict = None):
    """Play through a list of challenges.

    Returns (score, max_score, elapsed_seconds) or None if the player quit.
    """
    current_dir = sandbox_path
    start_time = time.time()
    total_score = 0
    max_score = sum(c["points"] for c in challenges)
    results = []

    for i, challenge in enumerate(challenges):
        set_terminal_title(
            f"ShellQuest  |  {theme.get('name', '')}  |  "
            f"Challenge {i + 1}/{len(challenges)}  |  {total_score} pts"
        )
        show_challenge_header(
            challenge, i, len(challenges), theme.get("id", ""),
            points_so_far=total_score,
            points_max=max_score,
        )

        hint_used = False
        points_earned = 0
        last_stdout = ""

        while True:
            rel = os.path.relpath(current_dir, sandbox_path)
            prompt_path = "~" if rel == "." else f"~/{rel}"
            show_prompt_reminder(theme.get("id", ""))

            try:
                user_input = console.input(f"[green]shellquest:{prompt_path}$ [/]")
            except (EOFError, KeyboardInterrupt):
                return None

            user_input = user_input.strip()
            if not user_input:
                continue

            # ── Meta-commands ─────────────────────────────────────────────
            if user_input == "hint":
                hint = None
                # Resolve which file to pass to Box AI:
                # L2 challenges carry hint_file; L1 use validation.target
                hint_file_rel = (
                    challenge.get("hint_file")
                    or challenge.get("validation", {}).get("target", "")
                )
                if hint_file_rel:
                    hint_file_abs = os.path.join(sandbox_path, hint_file_rel)
                    if os.path.isfile(hint_file_abs):
                        with console.status("[dim]Asking Box AI...[/]"):
                            hint = fetch_ai_hint(challenge["hint_command"], hint_file_abs)
                # Fall back to tldr
                if not hint:
                    with console.status("[dim]Fetching hint...[/]"):
                        hint = fetch_hint(challenge["hint_command"])
                game_msg(hint, theme.get("id", ""), style="yellow")
                hint_used = True
                continue

            elif user_input == "leaderboard":
                scores = get_leaderboard()
                if not scores:
                    game_msg("No scores yet — be the first to finish!", theme.get("id", ""), style="dim")
                else:
                    from rich.table import Table
                    tbl = Table(title="Leaderboard", border_style=_style(theme.get("id",""))["color"])
                    tbl.add_column("Player")
                    tbl.add_column("Theme")
                    tbl.add_column("Score", justify="right")
                    tbl.add_column("Time")
                    tbl.add_column("Stars")
                    for s in scores[:10]:
                        tbl.add_row(
                            s.get("name", ""),
                            s.get("theme_id", ""),
                            str(s.get("score", 0)),
                            _fmt_time(s.get("time_seconds", 0)),
                            s.get("stars", ""),
                        )
                    console.print(tbl)
                continue

            elif user_input == "skip":
                game_msg("Skipped.", theme.get("id", ""), style="dim")
                break

            elif user_input == "status":
                show_status_table(results, i, total_score, theme.get("id", ""))
                continue

            elif user_input == "quit":
                return None

            # ── cd (handled separately — doesn't produce stdout) ──────────
            elif user_input.startswith("cd"):
                args = user_input[2:].strip() or "~"
                cd_result = handle_cd(args, current_dir, sandbox_path)
                if cd_result["error"]:
                    show_command_output("", cd_result["error"])
                else:
                    current_dir = cd_result["new_dir"]
                    new_rel = os.path.relpath(current_dir, sandbox_path)
                    show_cd_result("~" if new_rel == "." else f"~/{new_rel}", theme.get("id", ""))
                last_stdout = ""

            # ── Regular shell command ─────────────────────────────────────
            else:
                result = execute_command(user_input, current_dir, sandbox_path)
                show_command_output(result["stdout"], result["stderr"])
                last_stdout = result["stdout"]

            # ── Validate after every command (including cd) ───────────────
            check = validate_challenge(
                challenge["validation"],
                sandbox_path,
                current_dir,
                last_stdout=last_stdout,
            )

            if check["passed"]:
                points_earned = challenge["points"]
                if hint_used:
                    points_earned = int(points_earned * 0.8)
                total_score += points_earned
                show_challenge_success(challenge["success_message"], points_earned, theme.get("id", ""))
                if task_map:
                    task_info = task_map.get(challenge["id"], {})
                    if task_info.get("task_id"):
                        complete_challenge_task(task_info["task_id"])
                break

        results.append(points_earned)

    elapsed = time.time() - start_time
    return total_score, max_score, elapsed


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def _save_theme_result(
    player: dict,
    theme: dict,
    l1_score: int,
    l1_max: int,
    l2_score: int,
    l2_max: int,
    total_time: int,
    stars: str = "",
) -> None:
    result = {
        "theme_id": theme["id"],
        "theme_name": theme["name"],
        "level_1_score": l1_score,
        "level_1_max": l1_max,
        "level_2_score": l2_score,
        "level_2_max": l2_max,
        "total_time_seconds": total_time,
        "stars": stars,
        "completed_at": datetime.now().isoformat(),
    }
    idx = next(
        (i for i, t in enumerate(player["completed_themes"]) if t["theme_id"] == theme["id"]),
        None,
    )
    if idx is not None:
        player["completed_themes"][idx] = result
    else:
        player["completed_themes"].append(result)

    player["total_score"] = sum(
        t["level_1_score"] + t["level_2_score"] for t in player["completed_themes"]
    )

    try:
        with console.status("[dim]Saving progress...[/]"):
            save_player_state(player)
        console.print("[dim]Progress saved![/]")
    except NotImplementedError:
        console.print("[dim]Progress saved locally.[/]")

    # Update shared leaderboard
    total = l1_score + l2_score
    with console.status("[dim]Updating leaderboard...[/]"):
        update_leaderboard(player, theme["id"], total, total_time, stars)

    # Generate completion certificate
    with console.status("[dim]Generating certificate...[/]"):
        cert_url = create_completion_certificate(
            player, theme, l1_score, l1_max, l2_score, l2_max, total_time, stars
        )
    if cert_url:
        game_msg(f"Your completion certificate:", style="cyan")
        game_msg(cert_url, style="bold cyan")
        game_msg("Share this link — anyone can view it, no login needed.", style="dim")


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


if __name__ == "__main__":
    main()
