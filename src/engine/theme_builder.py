"""Theme builder.

After building a level, call compute_challenge_answers(level["level_2_challenges"],
sandbox_path) to run each solution_command against the real seeded files and fill
in the exact expected output. This makes validation ground-truth accurate regardless
of file content.


Bridges scraped web content and a playable game: turns raw scraped pages into
themed sandbox files (articles, a CSV, a log, notes) and generates the Level 1
(state-based) and Level 2 (output-based) challenges, with Level 2 expected values
computed from the actual file content. Implemented in TICKET-6.
"""

import re
import random
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Answer computation
# ---------------------------------------------------------------------------

def compute_challenge_answers(challenges: list[dict], sandbox_path: str) -> list[dict]:
    """Run each challenge's solution_command in the sandbox and store the output
    as the validation expected value.

    Call this after seed_sandbox() so the files actually exist.
    Challenges without a solution_command are left unchanged.
    """
    from src.engine.runner import execute_command

    for challenge in challenges:
        cmd = challenge.get("solution_command")
        if not cmd:
            continue
        result = execute_command(cmd, sandbox_path, sandbox_path)
        if result["exit_code"] == 0 and result["stdout"].strip():
            challenge["validation"]["expected"] = result["stdout"].strip()
        else:
            # Solution command failed — fall back to a loose contains check
            # so the challenge still works rather than being impossible.
            challenge["validation"]["type"] = "player_output_contains"
            challenge["validation"]["expected"] = challenge.get(
                "validation", {}).get("expected", "")

    return challenges


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_level_from_theme(theme: dict, scraped_pages: list[dict]) -> dict:
    """Assemble a complete game level (files + both challenge sets) from a theme."""
    files = process_scraped_content(scraped_pages, theme)
    l1 = build_level_1_challenges(files, theme)
    l2 = build_level_2_challenges(files, theme)

    return {
        "title": theme["name"],
        "story_level_1": theme["story_level_1"],
        "story_level_2": theme["story_level_2"],
        "commands_taught_l1": ["ls", "cat", "mkdir", "mv", "cp"],
        "commands_taught_l2": ["wc", "grep", "sort", "uniq", "head", "|"],
        "files": files,
        "level_1_challenges": l1,
        "level_2_challenges": l2,
        "par_time_l1": 180,
        "par_time_l2": 300,
    }


# ---------------------------------------------------------------------------
# File generation
# ---------------------------------------------------------------------------

def process_scraped_content(raw_pages: list[dict], theme: dict) -> list[dict]:
    """Transform scraped pages into sandbox files.

    Args:
        raw_pages: list of {"url", "filename", "content"} dicts.
        theme: theme dict from themes.json.

    Returns:
        list of {"path": str, "content": str} ready for seed_sandbox().
    """
    files = []

    # Pad any article that is too short
    for page in raw_pages:
        content = page["content"].strip()
        if len(content) < 100:
            content += (
                f"\n\nData collection in progress. "
                f"Additional observations from the {theme['setting_name']} "
                f"are pending review.\n"
            ) * 3
        files.append({"path": page["filename"], "content": content})

    # Ensure we always have at least 3 article files
    while len(files) < 3:
        idx = len(files) + 1
        files.append({
            "path": f"data_file_{idx}.txt",
            "content": (
                f"Research data file for {theme['name']}.\n"
                f"This document contains observations collected at the "
                f"{theme['setting_name']}.\n"
                f"Data collection is ongoing.\n"
            ) * 5,
        })

    all_text = " ".join(f["content"] for f in files)
    terms = _extract_terms(all_text)

    # CSV data file
    csv_header = "id,term,category,occurrences,status"
    categories = ["primary", "secondary", "unclassified", "archived", "active"]
    statuses = ["verified", "pending", "needs_review", "confirmed", "unverified"]
    csv_rows = [csv_header]
    for i, term in enumerate(terms[:20], 1):
        count = all_text.lower().count(term.lower())
        cat = categories[i % len(categories)]
        status = statuses[i % len(statuses)]
        csv_rows.append(f"{i},{term},{cat},{count},{status}")
    files.append({"path": "field_data.csv", "content": "\n".join(csv_rows) + "\n"})

    # Log file — inject a seed ERROR that explicitly names field_data.csv
    log_lines = _generate_log(terms, setting=theme["setting_name"])
    seed_error = (
        f"[2024-03-15 17:42] ERROR: Data corruption detected in field_data.csv "
        f"— anomalous entries found across multiple categories. Investigate immediately."
    )
    # Insert the seed near the end so it feels like the last thing that happened
    log_lines.insert(max(0, len(log_lines) - 2), seed_error)
    files.append({"path": "station_log.txt", "content": "\n".join(log_lines) + "\n"})

    # READ_ME_FIRST.txt — narrative entry point with unambiguous clues
    log_file = next(f for f in files if f["path"] == "station_log.txt")
    csv_file = next(f for f in files if f["path"].endswith(".csv"))
    files.append({
        "path": "READ_ME_FIRST.txt",
        "content": _generate_briefing(theme, files[:3], log_file, csv_file),
    })

    return files


def _extract_terms(text: str) -> list[str]:
    words = re.findall(r'\b[A-Z][a-z]{3,}\b', text)
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    sorted_terms = sorted(freq.items(), key=lambda x: -x[1])
    return [t[0] for t in sorted_terms[:25]]


def _generate_log(terms: list[str], setting: str, num_lines: int = 25) -> list[str]:
    levels = ["INFO"] * 15 + ["WARNING"] * 6 + ["ERROR"] * 4
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
    safe_terms = terms if terms else ["data"]

    for i in range(min(num_lines, len(levels))):
        level = levels[i]
        term = safe_terms[i % len(safe_terms)]
        delta = timedelta(minutes=random.randint(5, 45) * (i + 1))
        timestamp = (base_time + delta).strftime("%Y-%m-%d %H:%M")

        if level == "INFO":
            msg = random.choice(messages_info)
        elif level == "WARNING":
            msg = random.choice(messages_warning)
        else:
            msg = random.choice(messages_error)

        lines.append(f"[{timestamp}] {level}: {msg.format(term=term)}")

    return lines


def _generate_briefing(
    theme: dict,
    article_files: list[dict],
    log_file: dict,
    csv_file: dict,
) -> str:
    """Generate READ_ME_FIRST.txt — the in-world narrative entry point.

    Contains unambiguous, step-by-step clues pointing to specific files
    so the player always knows exactly what to do next.
    """
    setting = theme["setting_name"]
    name = theme["name"]
    log_path = log_file["path"]
    csv_path = csv_file["path"]
    article_names = ", ".join(f["path"] for f in article_files[:3])

    return f"""{name} — Situation Report
{"=" * 52}

You have just arrived at the {setting}. The previous team
evacuated without warning and left the systems in disarray.

WHAT WE KNOW
------------
The team's last communications mentioned critical system failures
in the data infrastructure. Something went wrong — badly enough
that they left everything behind.

WHAT TO INVESTIGATE
-------------------
The station log ({log_path}) recorded every system event up
until the moment the team went dark. It holds the answer.
Focus on the ERROR entries — they will tell you what triggered
the emergency. At least one of those errors names a specific
data file that may be compromised.

The data file ({csv_path}) tracks all collected observations
by category. If records have been corrupted, the incident
report needs to know exactly how many categories were affected.

Store all your findings in a reports/ directory as you work.
The background research files left by the previous team are
also here: {article_names}

Good luck.
"""


# ---------------------------------------------------------------------------
# Challenge builders
# ---------------------------------------------------------------------------

def build_level_1_challenges(files: list[dict], theme: dict) -> list[dict]:
    """Build beginner (ls, cat, mkdir, mv, cp) state-based challenges."""
    briefing_file = next((f for f in files if f["path"] == "READ_ME_FIRST.txt"), None)
    csv_file = next((f for f in files if f["path"].endswith(".csv")), None)
    setting = theme["setting_name"]

    challenges = []

    # 1. ls — discover the scene
    challenges.append({
        "id": "l1_explore",
        "instruction": (
            f"You've just arrived at the {setting}. "
            "The place is deserted. Run ls to see what was left behind."
        ),
        "hint_command": "ls",
        "validation": {
            "type": "player_output_contains",
            "expected": "READ_ME_FIRST.txt",
        },
        "success_message": "There's a file here — READ_ME_FIRST.txt. You should open it.",
        "points": 10,
    })

    # 2. cat — read the briefing
    if briefing_file:
        challenges.append({
            "id": "l1_read",
            "instruction": (
                "There's a file called READ_ME_FIRST.txt. "
                "Open it — it should explain what happened here."
            ),
            "hint_command": "cat",
            "validation": {
                "type": "player_output_contains",
                "expected": "Situation Report",
            },
            "success_message": "Now you know what you're looking for. Time to get to work.",
            "points": 10,
        })

    # 3. mkdir — set up reports dir (briefing mentions it)
    challenges.append({
        "id": "l1_mkdir",
        "instruction": (
            "The situation report mentions storing findings in a reports/ directory. "
            "Create it before you start digging."
        ),
        "hint_command": "mkdir",
        "validation": {"type": "dir_exists", "target": "reports"},
        "success_message": "Good. You have somewhere to put your findings now.",
        "points": 15,
    })

    # 4. mv — secure the briefing as evidence
    if briefing_file:
        challenges.append({
            "id": "l1_move",
            "instruction": (
                "Move READ_ME_FIRST.txt into reports/ — "
                "it's the first piece of evidence for your incident report."
            ),
            "hint_command": "mv",
            "validation": {
                "type": "file_exists",
                "target": "reports/READ_ME_FIRST.txt",
            },
            "success_message": "Evidence secured. The reports directory is taking shape.",
            "points": 15,
        })

    # 5. cp — back up the data file before touching it
    if csv_file:
        challenges.append({
            "id": "l1_backup",
            "instruction": (
                f"The situation report flags {csv_file['path']} as potentially compromised. "
                f"Back it up as {csv_file['path']}.bak before you touch it."
            ),
            "hint_command": "cp",
            "validation": {
                "type": "file_exists",
                "target": f"{csv_file['path']}.bak",
            },
            "success_message": "Smart. Never analyze original data without a backup.",
            "points": 15,
        })

    return challenges


def build_level_2_challenges(files: list[dict], theme: dict) -> list[dict]:
    """Build intermediate (wc, grep, sort, uniq, pipes) output-based challenges."""
    log_file = next(
        (f for f in files if "log" in f["path"] and f["path"].endswith(".txt")), None
    )
    csv_file = next((f for f in files if f["path"].endswith(".csv")), None)

    challenges = []

    if not log_file:
        return challenges

    log_content = log_file["content"]
    log_lines = log_content.strip().split("\n")
    log_path = log_file["path"]

    total_lines = len(log_lines)
    error_lines = [l for l in log_lines if "ERROR" in l]
    error_count = len(error_lines)

    setting = theme["setting_name"]

    # 1. wc — count log entries
    challenges.append({
        "id": "l2_count",
        "instruction": (
            f"The briefing told you to start with {log_path}. "
            f"How many entries does it have in total? "
            f"You need the exact count for the incident report."
        ),
        "hint_command": "wc",
        "solution_command": f"cat {log_path} | wc -l",
        "validation": {"type": "player_output_equals", "expected": ""},
        "success_message": f"{total_lines} log entries — now find out what went wrong.",
        "points": 15,
    })

    # 2. grep — surface the errors
    if error_count > 0:
        challenges.append({
            "id": "l2_grep",
            "instruction": (
                f"The briefing said to look for ERROR entries in {log_path}. "
                "Show all of them — one of those errors is the key to this investigation."
            ),
            "hint_command": "grep",
            "solution_command": f"grep ERROR {log_path}",
            "validation": {"type": "player_output_equals", "expected": ""},
            "success_message": (
                f"There it is — {error_count} errors. "
                "One of them names field_data.csv. Keep going."
            ),
            "points": 15,
        })

        # 3. pipe — get the exact error count
        challenges.append({
            "id": "l2_pipe_count",
            "instruction": (
                f"The incident report needs an exact error count from {log_path}. "
                "Filter for ERROR lines and count them in a single pipeline."
            ),
            "hint_command": "wc",
            "solution_command": f"grep ERROR {log_path} | wc -l",
            "validation": {"type": "player_output_equals", "expected": ""},
            "success_message": f"{error_count} errors confirmed and logged.",
            "points": 20,
        })
    else:
        warning_count = len([l for l in log_lines if "WARNING" in l])
        challenges.append({
            "id": "l2_grep",
            "instruction": (
                f"There are no ERROR entries but the {setting} was still abandoned. "
                f"Show all WARNING entries in {log_path} — something in there triggered it."
            ),
            "hint_command": "grep",
            "solution_command": f"grep WARNING {log_path}",
            "validation": {"type": "player_output_equals", "expected": ""},
            "success_message": f"{warning_count} warnings — that explains the evacuation.",
            "points": 15,
        })

    # 4. sort — read the full timeline
    challenges.append({
        "id": "l2_sort",
        "instruction": (
            f"Sort {log_path} so all entries of the same type are grouped. "
            "This makes the full sequence of events readable at a glance."
        ),
        "hint_command": "sort",
        "solution_command": f"sort {log_path}",
        "validation": {"type": "player_output_equals", "expected": ""},
        "success_message": "Timeline reconstructed. The ERROR entries name field_data.csv — investigate it next.",
        "points": 15,
    })

    # 5. uniq — count affected categories in the corrupted CSV
    if csv_file:
        csv_path = csv_file["path"]
        challenges.append({
            "id": "l2_uniq",
            "instruction": (
                f"The ERROR log named {csv_path} as corrupted. "
                f"Its 3rd column is the data category. "
                "Find out how many unique categories were affected — "
                "chain cut, sort, and uniq to get the answer."
            ),
            "hint_command": "uniq",
            "solution_command": f"cut -d',' -f3 {csv_path} | sort | uniq | wc -l",
            "validation": {"type": "player_output_equals", "expected": ""},
            "success_message": "Investigation complete. You have everything you need for the report.",
            "points": 25,
        })

    return challenges
