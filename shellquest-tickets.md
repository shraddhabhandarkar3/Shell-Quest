# ShellQuest — Build Tickets

## Project summary

A CLI game teaching shell commands through themed adventures built from live web content. Player picks a theme (ocean, space, forest, etc.), Apify scrapes real articles, the engine builds a sandbox filesystem from them, and the player solves challenges using real bash. Two difficulty levels per theme. Box persists player state across sessions.

**Sponsors:** Apify (content scraping, hints, GitHub profiles), Box (player state persistence)

---

## Architecture overview

```
Player picks theme
       ↓
Apify scrapes Wikipedia articles for that theme
       ↓
theme_builder.py transforms scraped content into:
  - Themed files (ocean_overview.txt, species_log.csv, etc.)
  - Level 1 challenges (ls, cat, mkdir, mv, cp)
  - Level 2 challenges (grep, wc, sort, uniq, pipes)
       ↓
sandbox.py creates /tmp/shellquest-{uuid}/ and seeds files
       ↓
Player runs REAL shell commands
       ↓
checker.py validates after each command:
  - Level 1: checks filesystem state (does the dir exist? is the file moved?)
  - Level 2: checks player's actual stdout (did their command produce the right output?)
       ↓
On completion: save state to Box + local backup
```

---

## Validation model (important — read before implementing)

Two categories of validation, matched to challenge type:

**State-based (Level 1 — file operations):**
The checker inspects the sandbox filesystem after each command. These validate that the player *changed the world correctly*, regardless of how they did it.

| Type | What it checks |
|------|---------------|
| `file_exists` | `os.path.exists(sandbox/target)` is True |
| `file_not_exists` | `os.path.exists(sandbox/target)` is False |
| `dir_exists` | Path exists and `os.path.isdir` is True |
| `file_content_contains` | File at target contains expected substring |

**Output-based (Level 2 — text processing):**
The checker examines the stdout from the player's *most recent command*. These validate that the player *ran the right analysis*, not just that the data exists.

| Type | What it checks |
|------|---------------|
| `player_output_contains` | Player's last stdout contains expected substring |
| `player_output_equals` | Player's last stdout, stripped, equals expected value |

The game loop passes `last_stdout` to the checker after every command. State-based checks ignore it. Output-based checks use it.

This means: for Level 2 challenges, the player must actually type a correct command (like `grep ERROR log.txt`), see the right output, and *then* the challenge passes. Typing `ls` won't trigger it because `ls` output won't contain "ERROR".

---

## Ticket structure

Each ticket has:
- **Owner:** A or B (who implements it)
- **Depends on:** which tickets must be done first
- **Prompt:** copy-paste into Claude Code
- **Acceptance criteria:** how to verify it works

---

## TICKET-0: Project scaffold

**Owner:** A and B together
**Depends on:** nothing

**Prompt:**

```
Create a Python project called "shellquest":

shellquest/
├── pyproject.toml           (name: shellquest, python >=3.10)
├── requirements.txt         (boxsdk[jwt], requests, questionary,
│                             rich, python-dotenv, pytest)
├── .env.example             (BOX_CONFIG_PATH, BOX_STATE_FOLDER_ID,
│                             APIFY_API_TOKEN)
├── .gitignore               (venv, __pycache__, .env,
│                             /tmp/shellquest-*)
├── src/
│   ├── __init__.py
│   ├── main.py              (entry point — empty main() function)
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── sandbox.py       (placeholder)
│   │   ├── runner.py        (placeholder)
│   │   ├── checker.py       (placeholder)
│   │   └── theme_builder.py (placeholder)
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── box_client.py    (placeholder)
│   │   └── apify_client.py  (placeholder)
│   └── data/
│       └── themes.json      (empty {"themes": []})
└── tests/
    ├── __init__.py
    ├── test_engine.py        (placeholder)
    └── test_checker.py       (placeholder)

Every placeholder file should have a module docstring explaining
its purpose and stub functions with correct signatures that
raise NotImplementedError. This way both teammates can import
from any module immediately without circular dependency issues.

Stub signatures needed:

sandbox.py:
  def create_sandbox() -> tuple[str, callable]: ...
  def seed_sandbox(sandbox_path: str, files: list[dict]) -> None: ...

runner.py:
  def execute_command(command: str, cwd: str, sandbox_root: str) -> dict: ...
  def handle_cd(args: str, current_dir: str, sandbox_root: str) -> dict: ...

checker.py:
  def validate_challenge(validation: dict, sandbox_path: str,
      current_dir: str, last_stdout: str = "") -> dict: ...

theme_builder.py:
  def process_scraped_content(raw_pages: list[dict], theme: dict) -> list[dict]: ...
  def build_level_1_challenges(files: list[dict], theme: dict) -> list[dict]: ...
  def build_level_2_challenges(files: list[dict], theme: dict) -> list[dict]: ...
  def build_level_from_theme(theme: dict, scraped_pages: list[dict]) -> dict: ...

box_client.py:
  def init_box() -> None: ...
  def save_player_state(player: dict) -> bool: ...
  def load_player_state(player_id: str) -> dict | None: ...

apify_client.py:
  def scrape_theme_content(theme: dict) -> list[dict] | None: ...
  def fetch_hint(command: str) -> str: ...
  def fetch_github_profile(username: str) -> dict: ...

Install all dependencies into a venv.
```

**Acceptance criteria:**
- `python -c "from src.engine import sandbox, runner, checker, theme_builder"` works
- `python -c "from src.integrations import box_client, apify_client"` works
- All stub functions exist with correct signatures

---

## TICKET-1: Theme definitions

**Owner:** A or B (whoever finishes TICKET-0 first)
**Depends on:** TICKET-0

**Prompt:**

```
Populate src/data/themes.json with 5 adventure themes.

Each theme has:
{
  "id": string,
  "name": string (adventure title),
  "icon": string (single emoji),
  "description": string (one line),
  "scrape_queries": [
    {
      "url": "https://en.wikipedia.org/wiki/...",
      "filename": "descriptive_name.txt"
    }
  ],
  "story_level_1": string (2-3 sentences — setup for exploration),
  "story_level_2": string (2-3 sentences — setup for analysis),
  "setting_name": string (used in challenge text, e.g. "research station")
}

The 5 themes:

1. id: "ocean"
   name: "Deep Ocean Explorer"
   icon: 🌊
   description: "Explore a marine research station"
   scrape_queries: Wikipedia pages for Ocean, Coral reef, Deep-sea creature
   filenames: ocean_overview.txt, coral_reefs.txt, deep_sea_creatures.txt
   setting_name: "research station"
   story_level_1: "You've just arrived at the Deep Ocean Research Station. The previous researcher left in a hurry and the data files are a mess. Explore the station's file system and get things organized before the next expedition departs."
   story_level_2: "The station is organized — nice work. Now the science team needs you to analyze the research data. Dig into the logs and files to find patterns and anomalies."

2. id: "forest"
   name: "Ancient Forest Ranger"
   icon: 🌲
   description: "Manage a forest conservation outpost"
   scrape: Forest, Redwood, Forest ecology
   filenames: forest_overview.txt, redwood_data.txt, ecology_notes.txt
   setting_name: "outpost"

3. id: "space"
   name: "Mars Mission Control"
   icon: 🚀
   description: "Run a space mission control center"
   scrape: Mars, Exploration of Mars, Exoplanet
   filenames: mars_briefing.txt, mission_history.txt, exoplanet_catalog.txt
   setting_name: "mission control"

4. id: "dinosaur"
   name: "Jurassic Data Lab"
   icon: 🦕
   description: "Recover files from a paleontology lab"
   scrape: Dinosaur, Tyrannosaurus, Fossil
   filenames: dinosaur_overview.txt, trex_research.txt, fossil_records.txt
   setting_name: "data lab"

5. id: "volcano"
   name: "Volcano Observatory"
   icon: 🌋
   description: "Monitor an active volcano station"
   scrape: Volcano, Lava, Volcanic eruption
   filenames: volcano_briefing.txt, lava_analysis.txt, eruption_history.txt
   setting_name: "observatory"

Write creative story text for all 5 themes (both level 1 and
level 2 stories). Keep the tone fun but not childish.
```

**Acceptance criteria:**
- `json.load(open("src/data/themes.json"))` parses without error
- All 5 themes have complete fields including both story variants
- All Wikipedia URLs are valid (spot-check 2-3 in a browser)

---

## TICKET-2: Sandbox and runner

**Owner:** Person A
**Depends on:** TICKET-0

**Prompt:**

```
Implement src/engine/sandbox.py and src/engine/runner.py.

=== sandbox.py ===

import os, shutil, uuid, pathlib

1. create_sandbox() -> tuple[str, callable]:
   - Creates /tmp/shellquest-{uuid4().hex[:8]}
   - Returns (sandbox_path, cleanup_fn)
   - cleanup_fn:
     * Verifies path starts with /tmp/shellquest-
     * Calls shutil.rmtree(path, ignore_errors=True)
     * Logs nothing (silent cleanup)

2. seed_sandbox(sandbox_path: str, files: list[dict]) -> None:
   - files is a list of {"path": "relative/path.txt",
     "content": "string content"}
   - For each file:
     * full_path = os.path.join(sandbox_path, file["path"])
     * os.makedirs(os.path.dirname(full_path), exist_ok=True)
     * Write content to file (utf-8)
   - Also create these empty directories (for challenge targets):
     * archive/
     * reports/
     Wait — do NOT create reports/ — that's a challenge for the
     player to create. Only create archive/ as a pre-existing
     empty directory and data/ if it's not already created by
     the files.

=== runner.py ===

import subprocess, os, re

BLOCKED_PREFIXES = [
    "sudo", "su ", "apt", "yum", "pip", "python", "python3",
    "node", "curl", "wget", "ssh", "nc", "dd", "mkfs", "fdisk",
    "mount", "umount", "reboot", "shutdown", "systemctl",
    "service", "chmod 777", "chown"
]

INTERACTIVE_COMMANDS = [
    "nano", "vim", "vi", "less", "more", "top", "htop", "man",
    "emacs", "pico"
]

1. execute_command(command: str, cwd: str,
                   sandbox_root: str) -> dict:
   """
   Returns {"stdout": str, "stderr": str, "exit_code": int}
   """
   command = command.strip()
   if not command:
       return {"stdout": "", "stderr": "", "exit_code": 0}

   # Get the base command (first word, before pipes)
   base_cmd = command.split("|")[0].strip().split()[0] \
       if command.strip() else ""

   # Check interactive
   if base_cmd in INTERACTIVE_COMMANDS:
       return {
           "stdout": "",
           "stderr": "Interactive programs aren't supported in "
               "ShellQuest. Try cat, grep, or echo instead.",
           "exit_code": 1
       }

   # Check blocked
   for prefix in BLOCKED_PREFIXES:
       if command.startswith(prefix) or \
           command.startswith(f"/{prefix}"):
           return {
               "stdout": "",
               "stderr": f"'{base_cmd}' is not available in "
                   "ShellQuest. Stick to file and text commands!",
               "exit_code": 1
           }

   # Check path escape via ..
   # Resolve any paths in the command that contain ..
   # Split on spaces (rough but sufficient), check each token
   tokens = command.split()
   for token in tokens:
       if ".." in token:
           resolved = os.path.realpath(
               os.path.join(cwd, token))
           sandbox_real = os.path.realpath(sandbox_root)
           if not resolved.startswith(sandbox_real):
               return {
                   "stdout": "",
                   "stderr": "Can't access paths outside the "
                       "sandbox!",
                   "exit_code": 1
               }

   # Check destructive rm on root
   if re.match(r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?(/|\*|/\*)",
               command):
       return {
           "stdout": "",
           "stderr": "Nice try — but we're protecting the "
               "filesystem here!",
           "exit_code": 1
       }

   # Execute
   try:
       result = subprocess.run(
           command,
           shell=True,
           capture_output=True,
           text=True,
           timeout=5,
           cwd=cwd,
           env={**os.environ, "HOME": sandbox_root}
       )
       stdout = result.stdout
       # Truncate very long output
       lines = stdout.split("\n")
       if len(lines) > 80:
           stdout = "\n".join(lines[:40]) + \
               f"\n... ({len(lines) - 40} more lines)\n"
       return {
           "stdout": stdout,
           "stderr": result.stderr,
           "exit_code": result.returncode
       }
   except subprocess.TimeoutExpired:
       return {
           "stdout": "",
           "stderr": "Command timed out (5s limit). Try a "
               "simpler command.",
           "exit_code": 1
       }
   except Exception as e:
       return {
           "stdout": "",
           "stderr": str(e),
           "exit_code": 1
       }


2. handle_cd(args: str, current_dir: str,
             sandbox_root: str) -> dict:
   """
   Returns {"new_dir": str | None, "error": str | None}
   """
   if not args or args == "~":
       return {"new_dir": sandbox_root, "error": None}

   target = os.path.realpath(os.path.join(current_dir, args))
   sandbox_real = os.path.realpath(sandbox_root)

   if not target.startswith(sandbox_real):
       return {
           "new_dir": None,
           "error": "Can't navigate outside the sandbox"
       }
   if not os.path.isdir(target):
       return {
           "new_dir": None,
           "error": f"Not a directory: {args}"
       }
   return {"new_dir": target, "error": None}


Write tests in tests/test_engine.py:

- test_create_sandbox: creates dir, cleanup removes it
- test_seed_sandbox: files exist with correct content after seed
- test_execute_ls: runs "ls" in a seeded sandbox, gets filenames
- test_execute_pipe: runs "echo hello | wc -w", gets "1"
- test_block_sudo: returns friendly error
- test_block_curl: returns friendly error
- test_block_interactive_vim: returns friendly error
- test_block_path_escape: "cat ../../etc/passwd" blocked
- test_cd_into_subdir: works, returns new path
- test_cd_escape_blocked: "cd ../../.." returns error
- test_cd_nonexistent: returns error
- test_timeout: "sleep 10" returns timeout error
```

**Acceptance criteria:**
- All tests pass
- `execute_command("ls", sandbox, sandbox)` returns file listing
- `execute_command("echo hello | wc -w", sandbox, sandbox)` returns "1"
- `execute_command("sudo rm -rf /", sandbox, sandbox)` returns friendly error
- `handle_cd("..", sandbox_root, sandbox_root)` stays in sandbox

---

## TICKET-3: Challenge checker

**Owner:** Person A
**Depends on:** TICKET-2

**Prompt:**

```
Implement src/engine/checker.py.

import os
from src.engine.runner import execute_command

def validate_challenge(validation: dict, sandbox_path: str,
                       current_dir: str,
                       last_stdout: str = "") -> dict:
    """
    Validates whether a challenge has been completed.

    Args:
        validation: dict with "type", "target" (optional),
            "expected" (optional)
        sandbox_path: root of the sandbox directory
        current_dir: player's current working directory
        last_stdout: stdout from the player's most recent command
            (used by player_output_* types)

    Returns:
        {"passed": bool, "message": str}
    """

    vtype = validation["type"]
    target = validation.get("target", "")
    expected = validation.get("expected", "")

    try:
        # === STATE-BASED CHECKS (Level 1) ===
        # These inspect the filesystem. They don't care what
        # command the player ran — only the outcome.

        if vtype == "file_exists":
            path = os.path.join(sandbox_path, target)
            if os.path.exists(path):
                return {"passed": True,
                    "message": "File found!"}
            return {"passed": False,
                "message": f"File not found at {target}"}

        elif vtype == "file_not_exists":
            path = os.path.join(sandbox_path, target)
            if not os.path.exists(path):
                return {"passed": True,
                    "message": "File successfully removed!"}
            return {"passed": False,
                "message": f"File still exists at {target}"}

        elif vtype == "dir_exists":
            path = os.path.join(sandbox_path, target)
            if os.path.isdir(path):
                return {"passed": True,
                    "message": "Directory created!"}
            return {"passed": False,
                "message": "Directory not found"}

        elif vtype == "file_content_contains":
            path = os.path.join(sandbox_path, target)
            if not os.path.exists(path):
                return {"passed": False,
                    "message": f"File {target} not found"}
            with open(path, "r", encoding="utf-8",
                      errors="replace") as f:
                content = f.read()
            if str(expected) in content:
                return {"passed": True,
                    "message": "Content verified!"}
            return {"passed": False,
                "message": "Expected content not found in file"}

        # === OUTPUT-BASED CHECKS (Level 2) ===
        # These check what the player's last command printed.
        # The player must actually run the right command and
        # produce the right output.

        elif vtype == "player_output_contains":
            # Check if the player's last stdout contains the
            # expected substring (case-insensitive)
            if not last_stdout.strip():
                return {"passed": False,
                    "message": "Run a command to produce output"}
            if expected.lower() in last_stdout.lower():
                return {"passed": True,
                    "message": "Correct output!"}
            return {"passed": False,
                "message": "Not quite — check your command"}

        elif vtype == "player_output_equals":
            # Check if the player's last stdout (trimmed) equals
            # the expected value. Compare as strings, stripped.
            if not last_stdout.strip():
                return {"passed": False,
                    "message": "Run a command to produce output"}
            actual = last_stdout.strip()
            exp = str(expected).strip()
            if actual == exp:
                return {"passed": True,
                    "message": "Exact match!"}
            # Also try: expected appears as a standalone token
            # in the output (for "wc -l" which prints "25 file.txt"
            # and we expect "25")
            if exp in actual.split():
                return {"passed": True,
                    "message": "Correct!"}
            return {"passed": False,
                "message": "Not quite — check your command"}

        else:
            return {"passed": False,
                "message": f"Unknown validation type: {vtype}"}

    except Exception as e:
        return {"passed": False,
            "message": f"Validation error: {str(e)}"}


Write thorough tests in tests/test_checker.py using pytest
with a tmp_path fixture:

STATE-BASED TESTS:
- test_file_exists_pass: create a file, check passes
- test_file_exists_fail: check for nonexistent file, fails
- test_file_not_exists_pass: file removed, check passes
- test_file_not_exists_fail: file still exists, fails
- test_dir_exists_pass: mkdir, check passes
- test_dir_exists_fail: no dir, fails
- test_file_content_pass: file contains expected string
- test_file_content_fail: file doesn't contain string
- test_file_content_missing_file: file doesn't exist, fails
  gracefully

OUTPUT-BASED TESTS:
- test_player_output_contains_pass:
    last_stdout="ERROR: connection lost\nERROR: timeout"
    expected="ERROR" → passes
- test_player_output_contains_fail:
    last_stdout="INFO: all good"
    expected="ERROR" → fails
- test_player_output_contains_empty:
    last_stdout="" → fails with "Run a command" message
- test_player_output_contains_case_insensitive:
    last_stdout="Error Found", expected="error" → passes
- test_player_output_equals_pass:
    last_stdout="25\n", expected="25" → passes
- test_player_output_equals_with_filename:
    last_stdout="25 log.txt\n", expected="25" → passes
    (because "25" is a token in the output)
- test_player_output_equals_fail:
    last_stdout="30\n", expected="25" → fails
- test_unknown_type: returns failed with message
```

**Acceptance criteria:**
- All tests pass
- State-based checks work independently of last_stdout
- Output-based checks require actual matching stdout
- `validate_challenge({"type": "player_output_contains", "expected": "ERROR"}, ..., last_stdout="all good")` returns `passed: False`
- No exceptions thrown on any input — always returns a dict

---

## TICKET-4: Apify integration

**Owner:** Person B
**Depends on:** TICKET-0

**Prompt:**

```
Implement src/integrations/apify_client.py.

Three responsibilities:
1. Scrape Wikipedia articles for game themes
2. Scrape tldr pages for command hints
3. Scrape GitHub profiles for player info

import requests, os, re
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv

load_dotenv()
console = Console()

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN")
_apify_enabled = bool(APIFY_TOKEN)

if not _apify_enabled:
    console.print(
        "[dim][Apify] Not configured — using fallback content[/]")

APIFY_BASE = "https://api.apify.com/v2"
CRAWLER_ACTOR = "apify~website-content-crawler"


def _call_crawler(urls: list[str], timeout: int = 30) -> list[dict]:
    """
    Internal helper: call Apify website-content-crawler with
    a list of URLs. Returns list of scraped page dicts.
    Raises on failure.
    """
    response = requests.post(
        f"{APIFY_BASE}/acts/{CRAWLER_ACTOR}"
        f"/run-sync-get-dataset-items",
        params={"token": APIFY_TOKEN},
        json={
            "startUrls": [{"url": u} for u in urls],
            "maxCrawlPages": len(urls),
            "crawlerType": "cheerio",
            "maxCrawlDepth": 0
        },
        headers={"Content-Type": "application/json"},
        timeout=timeout
    )
    response.raise_for_status()
    return response.json()


def _clean_scraped_text(text: str, max_chars: int = 3000) -> str:
    """Clean scraped markdown/text for use as game files."""
    # Remove markdown images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Remove link markup but keep link text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove markdown headers markup (keep text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Trim to max length at sentence boundary
    text = text.strip()
    if len(text) > max_chars:
        cut = text[:max_chars].rfind('.')
        text = text[:cut + 1] if cut > max_chars * 0.6 \
            else text[:max_chars]
    return text.strip()


# === FEATURE 1: Theme content scraping ===

def scrape_theme_content(theme: dict) -> list[dict] | None:
    """
    Scrape all URLs defined in theme["scrape_queries"].

    Returns list of:
        {"url": str, "filename": str, "content": str}
    or None on total failure.
    """
    urls = [q["url"] for q in theme["scrape_queries"]]

    # Try Apify first
    if _apify_enabled:
        try:
            items = _call_crawler(urls, timeout=45)
            results = []
            for query in theme["scrape_queries"]:
                matching = [
                    item for item in items
                    if query["url"] in item.get("url", "")
                ]
                if matching:
                    raw = matching[0].get("text", "") or \
                        matching[0].get("markdown", "") or ""
                    content = _clean_scraped_text(raw)
                    if content and len(content) > 50:
                        results.append({
                            "url": query["url"],
                            "filename": query["filename"],
                            "content": content
                        })
            if results:
                console.print(
                    f"[dim][Apify] Scraped {len(results)} pages "
                    f"for {theme['name']}[/]")
                return results
        except Exception as e:
            console.print(
                f"[dim][Apify] Scrape failed ({e}) — trying "
                f"fallback[/]")

    # Fallback: Wikipedia REST API (no Apify needed)
    return _wikipedia_fallback(theme)


def _wikipedia_fallback(theme: dict) -> list[dict] | None:
    """Fetch article summaries directly from Wikipedia API."""
    results = []
    for query in theme["scrape_queries"]:
        if "wikipedia.org/wiki/" not in query["url"]:
            continue
        title = query["url"].split("/wiki/")[-1]
        try:
            # Use the full extract, not just summary
            resp = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/"
                f"summary/{title}",
                timeout=10,
                headers={"User-Agent": "ShellQuest/1.0"})
            resp.raise_for_status()
            data = resp.json()
            content = data.get("extract", "")
            if content and len(content) > 50:
                results.append({
                    "url": query["url"],
                    "filename": query["filename"],
                    "content": content
                })
        except requests.RequestException:
            continue

    if results:
        console.print(
            f"[dim][Fallback] Loaded {len(results)} articles "
            f"from Wikipedia API[/]")
        return results

    # Last resort: minimal placeholder content
    console.print("[dim][Fallback] Using placeholder content[/]")
    return [
        {
            "url": q["url"],
            "filename": q["filename"],
            "content": (
                f"Research data file for {theme['name']}.\n"
                f"This document contains observations and "
                f"field notes collected at the "
                f"{theme['setting_name']}.\n"
                f"Data collection is ongoing.\n"
            ) * 5
        }
        for q in theme["scrape_queries"]
    ]


# === FEATURE 2: Command hints ===

def fetch_hint(command: str) -> str:
    """
    Fetch a usage hint for a shell command.
    Tries: Apify → GitHub raw tldr → generic fallback.
    Returns a rich-formatted string ready to console.print().
    """
    # Try Apify
    if _apify_enabled:
        try:
            items = _call_crawler(
                [f"https://tldr.inbrowser.app/pages/common/"
                 f"{command}"],
                timeout=15)
            if items:
                raw = items[0].get("text", "") or \
                    items[0].get("markdown", "")
                if raw:
                    return _format_hint(command, raw)
        except Exception:
            pass

    # Fallback: GitHub raw tldr-pages
    for section in ["common", "linux"]:
        try:
            resp = requests.get(
                f"https://raw.githubusercontent.com/tldr-pages"
                f"/tldr/main/pages/{section}/{command}.md",
                timeout=5)
            if resp.status_code == 200:
                return _format_hint(command, resp.text)
        except requests.RequestException:
            continue

    return f"[yellow]Hint: try looking up '{command}' — " \
        f"couldn't fetch docs right now[/]"


def _format_hint(command: str, raw_text: str) -> str:
    """Parse tldr-style markdown into a formatted hint panel."""
    lines = raw_text.strip().split("\n")
    description = ""
    examples = []

    for line in lines:
        line = line.strip()
        if line.startswith(">"):
            desc_part = line.lstrip("> ").strip()
            if desc_part:
                description += desc_part + " "
        elif line.startswith("`") and line.endswith("`"):
            examples.append(line.strip("`"))

    description = description.strip() or \
        f"The {command} command"
    example_lines = "\n".join(
        f"  [cyan]$ {ex}[/]" for ex in examples[:4])

    content = f"{description}\n\n{example_lines}" \
        if example_lines else description

    return Panel(
        content,
        title=f"hint: {command}",
        border_style="yellow",
        padding=(1, 2)
    ).__rich_console__(console, console.options).__next__()
    # Actually, Panel can't be converted to string that way.
    # Instead, return the panel content as a formatted string
    # and let the caller print it. Or use console.export_text.

    # Simpler approach: return a manually formatted string
    border = "─" * 44
    return (
        f"[yellow]┌─ hint: {command} {border[:40 - len(command)]}┐[/]\n"
        f"[yellow]│[/] {description}\n"
        f"[yellow]│[/]\n"
        + "\n".join(
            f"[yellow]│[/]   [cyan]$ {ex}[/]"
            for ex in examples[:4])
        + f"\n[yellow]└{border}─┘[/]"
    )


# === FEATURE 3: GitHub profile ===

def fetch_github_profile(username: str) -> dict:
    """
    Fetch GitHub profile info. Returns:
        {"name": str, "avatar": str, "bio": str}
    """
    fallback = {
        "name": username,
        "avatar": f"https://github.com/{username}.png",
        "bio": ""
    }

    if _apify_enabled:
        try:
            items = _call_crawler(
                [f"https://github.com/{username}"],
                timeout=15)
            if items:
                raw = items[0].get("text", "") or ""
                lines = [l.strip() for l in raw.split("\n")
                         if l.strip()]
                if lines:
                    fallback["name"] = lines[0][:50]
                    for line in lines[1:10]:
                        if 10 < len(line) < 160 and \
                            not line.startswith("http") and \
                            not line.startswith("{"):
                            fallback["bio"] = line
                            break
        except Exception:
            pass

    return fallback
```

**Acceptance criteria:**
- `scrape_theme_content(ocean_theme)` returns 3 pages of real content (with Apify token) or Wikipedia fallback (without)
- `fetch_hint("grep")` returns a formatted hint with description and examples
- `fetch_github_profile("octocat")` returns name, avatar URL, bio
- All three functions work with `APIFY_API_TOKEN=""` (fallback mode)
- No function ever raises an exception — all return graceful fallbacks
- Timeouts work (no hanging)

---

## TICKET-5: Box integration

**Owner:** Person B
**Depends on:** TICKET-0

**Prompt:**

```
Implement src/integrations/box_client.py.

Single responsibility: persist and retrieve player state.

from boxsdk import JWTAuth, Client
from rich.console import Console
import json, os, io, pathlib
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
console = Console()

_client = None
_box_enabled = False

BOX_CONFIG_PATH = os.environ.get("BOX_CONFIG_PATH")
BOX_STATE_FOLDER_ID = os.environ.get("BOX_STATE_FOLDER_ID")

if not (BOX_CONFIG_PATH and BOX_STATE_FOLDER_ID):
    console.print(
        "[dim][Box] Not configured — using local storage[/]")


def init_box() -> None:
    """Initialize Box client. Call once at startup."""
    global _client, _box_enabled

    if not (BOX_CONFIG_PATH and BOX_STATE_FOLDER_ID):
        return

    try:
        auth = JWTAuth.from_settings_file(BOX_CONFIG_PATH)
        auth.authenticate_instance()
        _client = Client(auth)
        user = _client.user().get()
        console.print(f"[dim][Box] Connected as {user.name}[/]")
        _box_enabled = True
    except Exception as e:
        console.print(
            f"[dim][Box] Auth failed: {e} — using local "
            f"storage[/]")
        _box_enabled = False


def save_player_state(player: dict) -> bool:
    """
    Save player state. Always saves locally. Also saves to Box
    if connected.

    player dict shape:
    {
        "id": str,
        "name": str,
        "github_username": str,
        "github_avatar": str,
        "github_bio": str,
        "completed_themes": [
            {
                "theme_id": str,
                "theme_name": str,
                "level_1_score": int,
                "level_1_max": int,
                "level_2_score": int,
                "level_2_max": int,
                "total_time_seconds": int,
                "stars": str,
                "completed_at": str (ISO)
            }
        ],
        "total_score": int
    }
    """
    data = {**player, "last_saved": datetime.now().isoformat()}
    json_str = json.dumps(data, indent=2)

    # Always save locally
    _save_local(data)

    if not _box_enabled:
        return True

    try:
        filename = f"player-{player['id']}.json"
        folder = _client.folder(BOX_STATE_FOLDER_ID)

        existing = _find_file_in_folder(folder, filename)
        stream = io.BytesIO(json_str.encode("utf-8"))

        if existing:
            existing.update_contents_with_stream(stream)
        else:
            folder.upload_stream(stream, filename)

        return True
    except Exception as e:
        console.print(f"[dim][Box] Save failed: {e}[/]")
        return False


def load_player_state(player_id: str) -> dict | None:
    """
    Load player state. Tries Box first, then local fallback.
    Returns None if no state found.
    """
    if _box_enabled:
        try:
            folder = _client.folder(BOX_STATE_FOLDER_ID)
            filename = f"player-{player_id}.json"
            found = _find_file_in_folder(folder, filename)
            if found:
                content = found.content().decode("utf-8")
                return json.loads(content)
        except Exception as e:
            console.print(f"[dim][Box] Load failed: {e}[/]")

    return _load_local(player_id)


def _find_file_in_folder(folder, filename: str):
    """Find a file by name in a Box folder. Returns file object
    or None."""
    try:
        for item in folder.get_items():
            if item.name == filename and item.type == "file":
                return _client.file(item.id)
    except Exception:
        pass
    return None


# === Local fallback ===

def _local_dir() -> pathlib.Path:
    p = pathlib.Path.home() / ".shellquest"
    p.mkdir(exist_ok=True)
    return p


def _save_local(data: dict) -> None:
    try:
        path = _local_dir() / f"player-{data['id']}.json"
        with open(path, "w") as f:
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
```

Also create scripts/setup_box.py:

```
"""
Run once to create the ShellQuest folder in Box and get
the folder ID for .env.

Usage: python scripts/setup_box.py
"""
from boxsdk import JWTAuth, Client
from dotenv import load_dotenv
import os

load_dotenv()

def main():
    config_path = os.environ.get("BOX_CONFIG_PATH")
    if not config_path:
        print("Set BOX_CONFIG_PATH in .env first")
        return

    auth = JWTAuth.from_settings_file(config_path)
    auth.authenticate_instance()
    client = Client(auth)

    user = client.user().get()
    print(f"Connected as: {user.name}")

    root = client.folder("0")

    # Find or create ShellQuest folder
    sq_folder = None
    for item in root.get_items():
        if item.name == "ShellQuest" and item.type == "folder":
            sq_folder = client.folder(item.id)
            print(f"Found existing ShellQuest folder: {item.id}")
            break
    if not sq_folder:
        sq_folder = root.create_subfolder("ShellQuest")
        print(f"Created ShellQuest folder: {sq_folder.id}")

    # Find or create state subfolder
    state_folder = None
    for item in sq_folder.get_items():
        if item.name == "state" and item.type == "folder":
            state_folder = client.folder(item.id)
            print(f"Found existing state folder: {item.id}")
            break
    if not state_folder:
        state_folder = sq_folder.create_subfolder("state")
        print(f"Created state folder: {state_folder.id}")

    print(f"\nAdd this to your .env:")
    print(f"BOX_STATE_FOLDER_ID={state_folder.id}")

if __name__ == "__main__":
    main()
```

**Acceptance criteria:**
- `init_box()` connects successfully with valid credentials
- `save_player_state(player)` creates a JSON file in Box (verify in Box web UI)
- `save_player_state(player)` again updates the same file (not duplicate)
- `load_player_state(id)` retrieves the saved data
- All functions work with no Box config (local fallback)
- `setup_box.py` creates folders and prints the ID
- No function ever crashes the game

---

## TICKET-6: Theme builder

**Owner:** Person A
**Depends on:** TICKET-2, TICKET-3

**Prompt:**

```
Implement src/engine/theme_builder.py.

This is the bridge between scraped content and playable game.
It produces files for the sandbox AND challenge definitions
for both levels.

import re, random
from datetime import datetime, timedelta


def process_scraped_content(raw_pages: list[dict],
                            theme: dict) -> list[dict]:
    """
    Transform scraped page data into sandbox files.

    raw_pages: [{"url": str, "filename": str, "content": str}]
    theme: theme dict from themes.json

    Returns: [{"path": str, "content": str}] ready for
             seed_sandbox()
    """
    files = []

    # 1. Add each scraped article as a text file
    for page in raw_pages:
        files.append({
            "path": page["filename"],
            "content": page["content"]
        })

    # 2. Generate a CSV data file from scraped content
    # Extract notable terms (capitalized words, multi-word terms)
    all_text = " ".join(p["content"] for p in raw_pages)
    terms = _extract_terms(all_text)

    csv_header = "id,term,category,occurrences,status"
    csv_rows = [csv_header]
    categories = ["primary", "secondary", "unclassified",
                  "archived", "active"]
    statuses = ["verified", "pending", "needs_review",
                "confirmed", "unverified"]
    for i, term in enumerate(terms[:20], 1):
        count = all_text.lower().count(term.lower())
        cat = categories[i % len(categories)]
        status = statuses[i % len(statuses)]
        csv_rows.append(f"{i},{term},{cat},{count},{status}")

    files.append({
        "path": "field_data.csv",
        "content": "\n".join(csv_rows) + "\n"
    })

    # 3. Generate a log file with realistic entries using
    # terms from the content
    log_lines = _generate_log(terms, setting=theme["setting_name"])
    files.append({
        "path": "station_log.txt",
        "content": "\n".join(log_lines) + "\n"
    })

    # 4. Generate a notes file (short excerpts)
    notes = _generate_notes(raw_pages)
    files.append({
        "path": "notes.txt",
        "content": notes
    })

    return files


def _extract_terms(text: str) -> list[str]:
    """Extract notable terms from text for use in generated files."""
    # Find capitalized multi-word terms and single notable words
    # Look for capitalized words that aren't sentence starters
    words = re.findall(r'\b[A-Z][a-z]{3,}\b', text)
    # Count frequency, pick top terms
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    # Sort by frequency, take top 25 unique terms
    sorted_terms = sorted(freq.items(), key=lambda x: -x[1])
    return [t[0] for t in sorted_terms[:25]]


def _generate_log(terms: list[str], setting: str,
                  num_lines: int = 25) -> list[str]:
    """Generate realistic log entries using scraped terms."""
    levels = (["INFO"] * 15 + ["WARNING"] * 6 + ["ERROR"] * 4)
    random.shuffle(levels)

    messages_info = [
        "Loaded data for {term}",
        "Updated record: {term}",
        "Scan complete: {term} sector",
        "Data sync: {term} collection",
        "Backup created: {term} dataset",
        "Routine check: {term} nominal",
        "Processed {term} readings",
    ]
    messages_warning = [
        "Missing entries for {term}",
        "{term} data needs review",
        "Incomplete record: {term}",
        "Anomaly detected near {term}",
        "{term} readings out of range",
    ]
    messages_error = [
        "Failed to load {term} data",
        "Connection lost during {term} sync",
        "Corrupt file: {term}_backup.dat",
        "Timeout reading {term} sensor",
    ]

    lines = []
    base_time = datetime(2024, 3, 15, 8, 0, 0)

    for i in range(min(num_lines, len(levels))):
        level = levels[i]
        term = terms[i % len(terms)] if terms else "data"
        delta = timedelta(minutes=random.randint(5, 45) * (i + 1))
        timestamp = (base_time + delta).strftime(
            "%Y-%m-%d %H:%M")

        if level == "INFO":
            msg = random.choice(messages_info)
        elif level == "WARNING":
            msg = random.choice(messages_warning)
        else:
            msg = random.choice(messages_error)

        lines.append(f"[{timestamp}] {level}: "
                     f"{msg.format(term=term)}")

    return lines


def _generate_notes(raw_pages: list[dict]) -> str:
    """Create a notes file from short excerpts of each article."""
    notes = []
    for page in raw_pages:
        sentences = re.split(r'(?<=[.!?])\s+', page["content"])
        # Pick 2-3 sentences from different parts of each article
        picks = []
        if len(sentences) >= 6:
            picks = [sentences[0], sentences[len(sentences)//2],
                     sentences[-2]]
        elif sentences:
            picks = sentences[:3]
        for s in picks:
            s = s.strip()
            if len(s) > 20:
                notes.append(f"- {s}")

    return "Field Notes\n" + "=" * 40 + "\n\n" + \
        "\n\n".join(notes) + "\n"


# === CHALLENGE BUILDERS ===

def build_level_1_challenges(files: list[dict],
                             theme: dict) -> list[dict]:
    """
    Build beginner challenges: ls, cat, mkdir, mv, cp.
    These use STATE-BASED validation — they check the filesystem.
    """
    main_file = files[0] if files else None
    notes_file = next((f for f in files
                       if f["path"] == "notes.txt"), None)
    csv_file = next((f for f in files
                     if f["path"].endswith(".csv")), None)

    challenges = []

    # 1. ls — explore
    challenges.append({
        "id": "l1_explore",
        "instruction": (
            f"Welcome to the {theme['setting_name']}! "
            "Start by listing all files and directories to see "
            "what's here."
        ),
        "hint_command": "ls",
        "validation": {
            "type": "player_output_contains",
            "expected": main_file["path"] if main_file else "notes"
        },
        "success_message": "Good — now you can see what you're "
            "working with!",
        "points": 10
    })

    # 2. cat — read a file
    if main_file:
        # Find a distinctive word in the content to verify
        # they actually read the file
        content_words = [
            w for w in main_file["content"].split()
            if len(w) > 5 and w.isalpha()
        ]
        verify_word = content_words[10] if len(
            content_words) > 10 else "data"
        challenges.append({
            "id": "l1_read",
            "instruction": (
                f"Read {main_file['path']} to learn about this "
                f"{theme['setting_name']}."
            ),
            "hint_command": "cat",
            "validation": {
                "type": "player_output_contains",
                "expected": verify_word
            },
            "success_message": "Now you know what this place "
                "is about!",
            "points": 10
        })

    # 3. mkdir — create a directory
    challenges.append({
        "id": "l1_mkdir",
        "instruction": (
            "This place needs organizing. Create a 'reports' "
            "directory to store your findings."
        ),
        "hint_command": "mkdir",
        "validation": {
            "type": "dir_exists",
            "target": "reports"
        },
        "success_message": "Nice — a place for everything!",
        "points": 15
    })

    # 4. mv — move a file
    if notes_file:
        challenges.append({
            "id": "l1_move",
            "instruction": (
                f"Move {notes_file['path']} into the reports/ "
                "directory to keep things tidy."
            ),
            "hint_command": "mv",
            "validation": {
                "type": "file_exists",
                "target": f"reports/{notes_file['path']}"
            },
            "success_message": (
                f"File relocated — the {theme['setting_name']} "
                "is getting tidier!"
            ),
            "points": 15
        })

    # 5. cp — backup a file
    if csv_file:
        challenges.append({
            "id": "l1_backup",
            "instruction": (
                f"Make a backup copy of {csv_file['path']} "
                f"called {csv_file['path']}.bak — never work "
                "without backups!"
            ),
            "hint_command": "cp",
            "validation": {
                "type": "file_exists",
                "target": f"{csv_file['path']}.bak"
            },
            "success_message": "Smart — always keep backups!",
            "points": 15
        })

    return challenges


def build_level_2_challenges(files: list[dict],
                             theme: dict) -> list[dict]:
    """
    Build intermediate challenges: wc, grep, sort, uniq, pipes.
    These use OUTPUT-BASED validation — they check the player's
    actual command output.

    IMPORTANT: All expected values are COMPUTED from the actual
    file content. This is what makes the game dynamic.
    """
    log_file = next((f for f in files
                     if "log" in f["path"] and
                     f["path"].endswith(".txt")), None)
    csv_file = next((f for f in files
                     if f["path"].endswith(".csv")), None)

    challenges = []

    if not log_file:
        return challenges

    log_content = log_file["content"]
    log_lines = log_content.strip().split("\n")
    log_path = log_file["path"]

    # Pre-compute values from actual content
    total_lines = len(log_lines)
    error_lines = [l for l in log_lines if "ERROR" in l]
    error_count = len(error_lines)
    warning_count = len([l for l in log_lines if "WARNING" in l])

    # 1. wc — count lines
    challenges.append({
        "id": "l2_count",
        "instruction": (
            f"How many entries are in {log_path}? "
            "Use a command to count the lines."
        ),
        "hint_command": "wc",
        "validation": {
            "type": "player_output_contains",
            "expected": str(total_lines)
        },
        "success_message": (
            f"Exactly {total_lines} entries — you're getting "
            "the hang of this!"
        ),
        "points": 15
    })

    # 2. grep — find errors
    if error_lines:
        # Expected: player output should contain "ERROR"
        # This validates they ran grep (or similar) correctly
        challenges.append({
            "id": "l2_grep",
            "instruction": (
                f"Something went wrong at the "
                f"{theme['setting_name']}. Search for all "
                f"'ERROR' entries in {log_path}."
            ),
            "hint_command": "grep",
            "validation": {
                "type": "player_output_contains",
                "expected": "ERROR"
            },
            "success_message": (
                f"Found {error_count} errors — good detective "
                "work!"
            ),
            "points": 15
        })

    # 3. grep + wc pipe — count errors
    if error_lines:
        challenges.append({
            "id": "l2_pipe_count",
            "instruction": (
                f"Now count exactly how many ERROR lines there "
                f"are in {log_path}. Chain two commands together "
                "with a pipe."
            ),
            "hint_command": "wc",
            "validation": {
                "type": "player_output_contains",
                "expected": str(error_count)
            },
            "success_message": (
                f"{error_count} errors confirmed. Piping "
                "commands is a superpower!"
            ),
            "points": 20
        })

    # 4. sort — sort the log
    challenges.append({
        "id": "l2_sort",
        "instruction": (
            f"Sort {log_path} alphabetically so the ERROR "
            "entries are grouped together."
        ),
        "hint_command": "sort",
        "validation": {
            "type": "player_output_contains",
            "expected": "ERROR"
        },
        "success_message": "Sorted! Notice how the entries "
            "group by type now.",
        "points": 15
    })

    # 5. Advanced pipe — unique categories in CSV
    if csv_file:
        csv_content = csv_file["content"]
        csv_lines = csv_content.strip().split("\n")
        # Count unique values in the category column (col 3)
        categories = set()
        for line in csv_lines[1:]:  # skip header
            parts = line.split(",")
            if len(parts) >= 3:
                categories.add(parts[2].strip())
        unique_count = len(categories)

        challenges.append({
            "id": "l2_uniq",
            "instruction": (
                f"The file {csv_file['path']} has a 'category' "
                f"column (the 3rd column). Find out how many "
                "unique categories there are. You'll need to "
                "chain cut, sort, and uniq together."
            ),
            "hint_command": "uniq",
            "validation": {
                "type": "player_output_contains",
                "expected": str(unique_count)
            },
            "success_message": (
                f"{unique_count} unique categories — you just "
                "built a real data pipeline!"
            ),
            "points": 25
        })

    return challenges


def build_level_from_theme(theme: dict,
                           scraped_pages: list[dict]) -> dict:
    """
    Main entry point. Returns a complete game level dict:
    {
        "title": str,
        "story_level_1": str,
        "story_level_2": str,
        "commands_taught_l1": [...],
        "commands_taught_l2": [...],
        "files": [...],
        "level_1_challenges": [...],
        "level_2_challenges": [...]
    }
    """
    files = process_scraped_content(scraped_pages, theme)
    l1 = build_level_1_challenges(files, theme)
    l2 = build_level_2_challenges(files, theme)

    return {
        "title": theme["name"],
        "story_level_1": theme["story_level_1"],
        "story_level_2": theme["story_level_2"],
        "commands_taught_l1": ["ls", "cat", "mkdir", "mv", "cp"],
        "commands_taught_l2": ["wc", "grep", "sort", "uniq",
                               "head", "|"],
        "files": files,
        "level_1_challenges": l1,
        "level_2_challenges": l2,
        "par_time_l1": 180,
        "par_time_l2": 300
    }
```

**Acceptance criteria:**
- `process_scraped_content` produces at least 5 files (3 articles + CSV + log + notes)
- `build_level_1_challenges` returns 5 challenges, all with state-based validation
- `build_level_2_challenges` returns 4-5 challenges, all with `player_output_contains` or `player_output_equals` validation
- Expected values in Level 2 are computed from actual content (not hardcoded)
- Calling `build_level_from_theme` with test data produces a complete level dict
- Test with manually crafted fake scraped content before integrating with real Apify data

---

## TICKET-7: Game loop

**Owner:** Person A
**Depends on:** TICKET-2, TICKET-3, TICKET-6

**Prompt:**

```
Implement the main game loop in src/main.py.

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import questionary
import time, json, os, signal, sys, uuid, atexit

from src.engine.sandbox import create_sandbox, seed_sandbox
from src.engine.runner import execute_command, handle_cd
from src.engine.checker import validate_challenge
from src.engine.theme_builder import build_level_from_theme
from src.integrations.box_client import (
    init_box, save_player_state, load_player_state)
from src.integrations.apify_client import (
    scrape_theme_content, fetch_hint, fetch_github_profile)

console = Console()
_active_cleanup = None


def main():
    global _active_cleanup

    # Signal handling
    def _cleanup_and_exit(sig=None, frame=None):
        if _active_cleanup:
            _active_cleanup()
        console.print("\n[dim]Thanks for playing![/]")
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup_and_exit)
    atexit.register(
        lambda: _active_cleanup() if _active_cleanup else None)

    # Welcome
    console.print(Panel(
        "[bold cyan]SHELLQUEST[/]\n"
        "[dim]Learn the command line by doing[/]",
        border_style="cyan", padding=(1, 4)))
    console.print(
        "[dim]  Type real shell commands to solve challenges\n"
        "  Type [cyan]hint[/] for help · [cyan]skip[/] to skip "
        "· [cyan]status[/] for progress\n[/]")

    # Init Box
    init_box()

    # Player setup
    name = questionary.text("What's your name?").ask()
    if not name:
        name = "Explorer"
    github_user = questionary.text(
        "GitHub username (optional, Enter to skip):").ask()

    player = {
        "id": str(uuid.uuid4()),
        "name": name,
        "github_username": github_user or "",
        "github_avatar": "",
        "github_bio": "",
        "completed_themes": [],
        "total_score": 0
    }

    if github_user:
        with console.status("[dim]Looking up your GitHub...[/]"):
            profile = fetch_github_profile(github_user)
        player["github_avatar"] = profile.get("avatar", "")
        player["github_bio"] = profile.get("bio", "")
        display = profile.get("name", name)
        console.print(f"[dim]Welcome, {display}![/]")
        if player["github_bio"]:
            console.print(f'[dim]"{player["github_bio"]}"[/]')
    else:
        console.print(f"[dim]Welcome, {name}![/]")

    # Load existing state
    existing = load_player_state(player["id"])
    if existing:
        player["completed_themes"] = existing.get(
            "completed_themes", [])
        player["total_score"] = existing.get("total_score", 0)

    # Load themes
    themes_path = os.path.join(
        os.path.dirname(__file__), "data", "themes.json")
    with open(themes_path) as f:
        themes = json.load(f)["themes"]

    # Main loop
    while True:
        console.print()
        completed_ids = [
            t["theme_id"] for t in player["completed_themes"]]

        choices = []
        for t in themes:
            done = t["id"] in completed_ids
            result = next(
                (r for r in player["completed_themes"]
                 if r["theme_id"] == t["id"]), None)
            if done and result:
                label = (f"✓ {result.get('stars', '')} "
                    f"{t['icon']} {t['name']}")
            else:
                label = f"  {t['icon']} {t['name']} — "  \
                    f"{t['description']}"
            choices.append(questionary.Choice(label, value=t["id"]))
        choices.append(questionary.Choice("  Quit", value="quit"))

        theme_id = questionary.select(
            "Choose your adventure:", choices=choices).ask()

        if theme_id == "quit" or theme_id is None:
            console.print("[dim]Thanks for playing![/]")
            break

        theme = next(t for t in themes if t["id"] == theme_id)

        # Scrape content
        with console.status(
            f"[cyan]Building your {theme['name']} "
            f"adventure...[/]"):
            scraped = scrape_theme_content(theme)

        if not scraped:
            console.print(
                "[red]Couldn't build this theme. Try another.[/]")
            continue

        # Build level
        level = build_level_from_theme(theme, scraped)

        # Create sandbox
        sandbox_path, cleanup = create_sandbox()
        _active_cleanup = cleanup
        seed_sandbox(sandbox_path, level["files"])

        # Play Level 1
        console.print(f"\n[bold yellow]{level['title']}[/]")
        console.print(f"[bold]Level 1: Exploration & Organization[/]")
        console.print(f"[dim]{level['story_level_1']}[/]")
        console.print(
            "[cyan]Commands:[/] " +
            ", ".join(level["commands_taught_l1"]))

        l1_result = _play_challenges(
            level["level_1_challenges"],
            sandbox_path, theme)

        if l1_result is None:
            # Player quit
            cleanup()
            _active_cleanup = None
            continue

        l1_score, l1_max, l1_time = l1_result

        # Transition to Level 2
        console.print(f"\n[yellow]{'━' * 50}[/]")
        console.print(
            f"[bold green]Level 1 Complete! "
            f"Score: {l1_score}/{l1_max}[/]\n")

        proceed = questionary.confirm(
            "Ready for Level 2? The data needs analysis now.",
            default=True).ask()

        if not proceed:
            # Save L1 only and continue
            _save_theme_result(
                player, theme, l1_score, l1_max, 0, 0,
                int(l1_time))
            cleanup()
            _active_cleanup = None
            continue

        # Play Level 2 (same sandbox, files already there)
        console.print(f"\n[bold]Level 2: Data Analysis[/]")
        console.print(f"[dim]{level['story_level_2']}[/]")
        console.print(
            "[cyan]Commands:[/] " +
            ", ".join(level["commands_taught_l2"]))

        l2_result = _play_challenges(
            level["level_2_challenges"],
            sandbox_path, theme)

        if l2_result is None:
            _save_theme_result(
                player, theme, l1_score, l1_max, 0, 0,
                int(l1_time))
            cleanup()
            _active_cleanup = None
            continue

        l2_score, l2_max, l2_time = l2_result

        # Final summary
        total_score = l1_score + l2_score
        total_max = l1_max + l2_max
        total_time = l1_time + l2_time

        console.print(f"\n[yellow]{'━' * 50}[/]")
        console.print(
            f"[bold yellow]{theme['icon']} "
            f"Adventure Complete![/]")
        console.print(f"  Level 1: {l1_score}/{l1_max} pts")
        console.print(f"  Level 2: {l2_score}/{l2_max} pts")
        console.print(f"  Total:   {total_score}/{total_max} pts")
        console.print(
            f"  Time:    {_fmt_time(total_time)}")

        if total_score >= total_max * 0.8:
            stars = "★★★"
            console.print(f"\n[green]{stars} Excellent![/]")
        elif total_score >= total_max * 0.5:
            stars = "★★☆"
            console.print(f"\n[yellow]{stars} Good job![/]")
        else:
            stars = "★☆☆"
            console.print(f"\n[dim]{stars} Keep practicing![/]")

        _save_theme_result(
            player, theme,
            l1_score, l1_max, l2_score, l2_max,
            int(total_time), stars)

        cleanup()
        _active_cleanup = None
        time.sleep(1)


def _play_challenges(challenges, sandbox_path, theme):
    """
    Play through a list of challenges. Returns
    (score, max_score, elapsed_seconds) or None if player quit.
    """
    current_dir = sandbox_path
    start_time = time.time()
    total_score = 0
    max_score = sum(c["points"] for c in challenges)
    results = []

    for i, challenge in enumerate(challenges):
        console.print(f"\n[blue]{'━' * 50}[/]")
        console.print(
            f"[bold]Challenge {i+1}/{len(challenges)}[/] "
            f"[dim]({challenge['points']} pts)[/]")
        console.print(challenge["instruction"])

        hint_used = False
        points_earned = 0
        last_stdout = ""

        while True:
            rel = os.path.relpath(current_dir, sandbox_path)
            prompt_path = "~" if rel == "." else f"~/{rel}"
            try:
                user_input = console.input(
                    f"[green]shellquest:{prompt_path}$ [/]")
            except EOFError:
                return None

            user_input = user_input.strip()
            if not user_input:
                continue

            # Special commands
            if user_input == "hint":
                with console.status("[dim]Fetching hint...[/]"):
                    hint = fetch_hint(challenge["hint_command"])
                console.print(hint)
                hint_used = True
                continue

            elif user_input == "skip":
                console.print("[yellow]Skipped![/]")
                break

            elif user_input == "status":
                tbl = Table(border_style="blue")
                tbl.add_column("Challenge")
                tbl.add_column("Status")
                tbl.add_column("Points", justify="right")
                for j, r in enumerate(results):
                    tbl.add_row(
                        f"Challenge {j+1}",
                        "[green]✓[/]" if r > 0 else "[red]✗[/]",
                        str(r))
                tbl.add_row(
                    f"Challenge {i+1}", "[yellow]...[/]", "—")
                console.print(tbl)
                console.print(
                    f"[dim]Score so far: {total_score}[/]")
                continue

            elif user_input == "quit":
                return None

            elif user_input.startswith("cd"):
                args = user_input[2:].strip()
                if not args:
                    args = "~"
                cd_result = handle_cd(
                    args, current_dir, sandbox_path)
                if cd_result["error"]:
                    console.print(f"[red]{cd_result['error']}[/]")
                else:
                    current_dir = cd_result["new_dir"]
                    new_rel = os.path.relpath(
                        current_dir, sandbox_path)
                    show = "~" if new_rel == "." else f"~/{new_rel}"
                    console.print(f"[dim]{show}[/]")
                last_stdout = ""
            else:
                result = execute_command(
                    user_input, current_dir, sandbox_path)
                if result["stdout"]:
                    out = result["stdout"]
                    console.print(
                        out, end="" if out.endswith("\n") else "\n")
                if result["stderr"]:
                    err = result["stderr"]
                    console.print(
                        f"[red]{err}[/]",
                        end="" if err.endswith("\n") else "\n")
                last_stdout = result["stdout"]

            # Validate after every command
            check = validate_challenge(
                challenge["validation"],
                sandbox_path, current_dir,
                last_stdout=last_stdout)

            if check["passed"]:
                points_earned = challenge["points"]
                if hint_used:
                    points_earned = int(points_earned * 0.8)
                total_score += points_earned
                console.print(
                    f"[bold green]✓ "
                    f"{challenge['success_message']}[/]")
                console.print(f"[green]+{points_earned} pts[/]")
                time.sleep(0.3)
                break

        results.append(points_earned)

    elapsed = time.time() - start_time
    return total_score, max_score, elapsed


def _save_theme_result(player, theme, l1_score, l1_max,
                       l2_score, l2_max, total_time,
                       stars=""):
    """Save completed theme result to player state."""
    from datetime import datetime
    result = {
        "theme_id": theme["id"],
        "theme_name": theme["name"],
        "level_1_score": l1_score,
        "level_1_max": l1_max,
        "level_2_score": l2_score,
        "level_2_max": l2_max,
        "total_time_seconds": total_time,
        "stars": stars,
        "completed_at": datetime.now().isoformat()
    }
    # Update or add
    idx = next(
        (i for i, t in enumerate(player["completed_themes"])
         if t["theme_id"] == theme["id"]), None)
    if idx is not None:
        player["completed_themes"][idx] = result
    else:
        player["completed_themes"].append(result)
    player["total_score"] = sum(
        t["level_1_score"] + t["level_2_score"]
        for t in player["completed_themes"])

    with console.status("[dim]Saving progress...[/]"):
        save_player_state(player)
    console.print("[dim]Progress saved![/]")


def _fmt_time(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


if __name__ == "__main__":
    main()
```

**Acceptance criteria:**
- Game starts, shows welcome, prompts for name
- Theme selection shows all 5 themes
- After picking a theme, scraping happens with a spinner
- Level 1 plays through with real commands
- After Level 1, prompt asks about Level 2
- Level 2 challenges validate based on player's actual stdout
- `last_stdout` is passed correctly to checker (empty for cd, populated for real commands)
- Level complete shows score breakdown for both levels
- Player state saves after completion
- Ctrl+C cleans up sandbox
- Game works with stubs (no Box, no Apify)

---

## TICKET-8: Integration wiring + playtest

**Owner:** A and B together
**Depends on:** TICKET-4, TICKET-5, TICKET-6, TICKET-7

**Prompt:**

```
Run the full game end to end and fix any integration issues.

Common problems to check for and fix:

1. Theme builder file paths don't match what seed_sandbox creates
   - After seeding, run os.walk on the sandbox and print the tree
   - Verify every challenge target file actually exists

2. Level 2 validation values don't match actual file content
   - After building challenges, for each player_output_contains
     challenge, manually run the expected command and verify the
     expected string appears in the output

3. Apify timeout issues
   - If scraping takes > 30 seconds, the status spinner should
     stay visible (not hang silently)
   - If it fails, the fallback should kick in automatically

4. Box save/load round-trip
   - Save a player state, then load it back
   - Verify completed_themes array survives the round-trip
   - Verify the file appears in Box web UI

5. last_stdout reset
   - After a "cd" command, last_stdout should be "" (empty)
   - After a failed command, last_stdout should still be the
     stderr? No — only stdout. Verify this.
   - After "hint", "skip", "status" — last_stdout should NOT
     change (these are meta-commands, not shell commands)

6. Challenge 1 of Level 1 (ls) uses player_output_contains
   - Verify it passes when the player types "ls" and the
     expected filename appears in stdout
   - Verify it does NOT pass when the player types something
     else like "echo hello"

Fix all issues found. Run through ocean theme completely,
then space theme completely.
```

**Acceptance criteria:**
- Two full playthroughs completed without crashes
- Both levels of at least 2 different themes are completable
- Box shows saved state in web UI
- Apify scrape works (or fallback works seamlessly)
- All 5 themes can be selected and produce playable content

---

## TICKET-9: Demo prep + README

**Owner:** Person B
**Depends on:** TICKET-8

**Prompt:**

```
Create DEMO.md and README.md.

=== DEMO.md ===
A 3-minute demo script for hackathon judges:

OPENING (15 sec):
"ShellQuest teaches Linux commands by dropping you into a themed
adventure built from real web content. Pick a theme, and the
game builds itself."

LIVE DEMO (2 min):
- Start game, enter name + GitHub username
- "Apify just scraped my GitHub profile"
- Show theme selection — "5 themes, each scrapes different content"
- Select "Deep Ocean Explorer"
- Watch scraping spinner
- "Apify just scraped 3 Wikipedia articles and built our game
  from them"
- Level 1: play challenges 1-3
  * "ls" — themed filenames appear
  * "cat ocean_overview.txt" — real Wikipedia content
  * "mkdir reports" — challenge complete
- Type "hint" — show live scraped hint
- Skip ahead to Level 2 intro
- Level 2: show one pipe challenge
  * "grep ERROR station_log.txt | wc -l" — dynamic answer
  * "That answer was computed from the actual scraped content"

BOX DEMO (30 sec):
- Open Box web UI
- Show player state JSON
- "Progress syncs to Box across sessions"

CLOSING (15 sec):
- "5 themes, 2 difficulty levels, completely different every time.
  We built this in 8 hours."

Include exact commands to type during demo. Mark where to pause.
Note: run ocean theme once before demo to warm Apify cache.

=== README.md ===
- Title + one-liner
- How it works (3 bullets)
- Sponsor integrations:
  * Apify (3 uses): theme content scraping, command hints,
    GitHub profiles
  * Box: persistent player state
- Quick start (Python 3.10+, venv, pip install, .env, run)
- Adding themes (show themes.json shape)
- Architecture (one line per module)
- Team names (placeholder)
- MIT license
```

**Acceptance criteria:**
- DEMO.md has exact commands with expected outputs
- README.md quick start works from a clean clone
- Both files are clear enough for a teammate to present from

---

## TICKET-10: Hardening (if time permits)

**Owner:** Person A
**Depends on:** TICKET-8

**Prompt:**

```
Harden edge cases:

1. runner.py:
   - Binary output: catch UnicodeDecodeError, print
     "[dim](binary output)[/]"
   - Empty pipe result: "echo '' | wc -l" should work without
     error

2. theme_builder.py:
   - If scraped content is too short (<100 chars), pad with
     "Data collection in progress..."
   - If fewer than 3 files produced, generate placeholders
   - In build_level_2_challenges: if computed values are 0
     (no errors in log), adjust the challenge text or skip it
   - Verify no challenge references a file that doesn't exist

3. checker.py:
   - player_output_equals: handle "wc -l" output format where
     some systems print "  25 file.txt" (leading spaces)
   - player_output_contains: handle multi-line output where
     expected appears on any line

4. main.py:
   - Handle KeyboardInterrupt during questionary prompts
   - Handle case where theme selection returns None
   - If sandbox creation fails (disk full), show friendly error
```

**Acceptance criteria:**
- No crashes on any input
- Edge cases handled gracefully with user-friendly messages
- Game works on macOS and Linux

---

## Dependency graph

```
TICKET-0 (scaffold)
  ├── TICKET-1 (themes)
  ├── TICKET-2 (sandbox + runner)  →  TICKET-3 (checker)
  │                                        ↓
  │                                   TICKET-6 (theme builder)
  │                                        ↓
  │                                   TICKET-7 (game loop)
  ├── TICKET-4 (apify)                    ↓
  └── TICKET-5 (box)              →  TICKET-8 (integration)
                                       ├── TICKET-9 (demo/README)
                                       └── TICKET-10 (hardening)
```

**Person A path:** 0 → 2 → 3 → 6 → 7 → 8 → 10
**Person B path:** 0 → 1 → 4 → 5 → 8 → 9

Both converge at TICKET-8 for integration testing.

---

## If things go wrong

**Apify scraping is slow or failing:**
Wikipedia REST API fallback works without Apify and is fast. The game is still themed and dynamic. Mention Apify in the pitch, show the code.

**Box auth won't work:**
Local file fallback is automatic. Demo the game, show the Box code, say auth was a time constraint.

**Theme builder produces broken challenges:**
Hardcode the exact commands for the demo. Test one theme thoroughly before presenting. Don't improvise on stage.

**Level 2 validation is unreliable:**
If `player_output_contains` is too flaky, fall back to simpler checks. Even "just run grep and see the output" is a learning moment — you can make the validation more lenient (just check that stdout is non-empty after they type a grep command).

**Nuclear option:**
Hardcode scraped content in the level files. Remove Apify calls. Demo a working game with themed content. A working game always beats a broken integration.
