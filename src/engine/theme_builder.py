"""Theme builder.

Bridges scraped web content and a playable game: turns raw scraped pages into
themed sandbox files (articles, a CSV, a log, notes) and generates the Level 1
(state-based) and Level 2 (output-based) challenges, with Level 2 expected values
computed from the actual file content. Implemented in TICKET-6.
"""

import re
import random
from datetime import datetime, timedelta


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

    # Log file
    log_lines = _generate_log(terms, setting=theme["setting_name"])
    files.append({"path": "station_log.txt", "content": "\n".join(log_lines) + "\n"})

    # Notes file
    files.append({"path": "notes.txt", "content": _generate_notes(files[:3])})

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


def _generate_notes(article_files: list[dict]) -> str:
    notes = []
    for f in article_files:
        sentences = re.split(r'(?<=[.!?])\s+', f["content"])
        if len(sentences) >= 6:
            picks = [sentences[0], sentences[len(sentences) // 2], sentences[-2]]
        else:
            picks = sentences[:3]
        for s in picks:
            s = s.strip()
            if len(s) > 20:
                notes.append(f"- {s}")

    return "Field Notes\n" + "=" * 40 + "\n\n" + "\n\n".join(notes) + "\n"


# ---------------------------------------------------------------------------
# Challenge builders
# ---------------------------------------------------------------------------

def build_level_1_challenges(files: list[dict], theme: dict) -> list[dict]:
    """Build beginner (ls, cat, mkdir, mv, cp) state-based challenges."""
    main_file = files[0] if files else None
    notes_file = next((f for f in files if f["path"] == "notes.txt"), None)
    csv_file = next((f for f in files if f["path"].endswith(".csv")), None)

    challenges = []

    # 1. ls — explore
    challenges.append({
        "id": "l1_explore",
        "instruction": (
            f"Welcome to the {theme['setting_name']}! "
            "Start by listing all files and directories to see what's here."
        ),
        "hint_command": "ls",
        "validation": {
            "type": "player_output_contains",
            "expected": main_file["path"] if main_file else "notes",
        },
        "success_message": "Good — now you can see what you're working with!",
        "points": 10,
    })

    # 2. cat — read a file
    if main_file:
        content_words = [
            w for w in main_file["content"].split() if len(w) > 5 and w.isalpha()
        ]
        verify_word = content_words[10] if len(content_words) > 10 else "data"
        challenges.append({
            "id": "l1_read",
            "instruction": (
                f"Read {main_file['path']} to learn about this {theme['setting_name']}."
            ),
            "hint_command": "cat",
            "validation": {
                "type": "player_output_contains",
                "expected": verify_word,
            },
            "success_message": "Now you know what this place is about!",
            "points": 10,
        })

    # 3. mkdir — create a directory
    challenges.append({
        "id": "l1_mkdir",
        "instruction": (
            "This place needs organizing. Create a 'reports' directory to store your findings."
        ),
        "hint_command": "mkdir",
        "validation": {"type": "dir_exists", "target": "reports"},
        "success_message": "Nice — a place for everything!",
        "points": 15,
    })

    # 4. mv — move a file
    if notes_file:
        challenges.append({
            "id": "l1_move",
            "instruction": (
                f"Move {notes_file['path']} into the reports/ directory to keep things tidy."
            ),
            "hint_command": "mv",
            "validation": {
                "type": "file_exists",
                "target": f"reports/{notes_file['path']}",
            },
            "success_message": (
                f"File relocated — the {theme['setting_name']} is getting tidier!"
            ),
            "points": 15,
        })

    # 5. cp — backup a file
    if csv_file:
        challenges.append({
            "id": "l1_backup",
            "instruction": (
                f"Make a backup copy of {csv_file['path']} "
                f"called {csv_file['path']}.bak — never work without backups!"
            ),
            "hint_command": "cp",
            "validation": {
                "type": "file_exists",
                "target": f"{csv_file['path']}.bak",
            },
            "success_message": "Smart — always keep backups!",
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

    # 1. wc — count lines
    challenges.append({
        "id": "l2_count",
        "instruction": (
            f"How many entries are in {log_path}? Use a command to count the lines."
        ),
        "hint_command": "wc",
        "validation": {
            "type": "player_output_contains",
            "expected": str(total_lines),
        },
        "success_message": (
            f"Exactly {total_lines} entries — you're getting the hang of this!"
        ),
        "points": 15,
    })

    # 2. grep — find errors (only if there are errors)
    if error_count > 0:
        challenges.append({
            "id": "l2_grep",
            "instruction": (
                f"Something went wrong at the {theme['setting_name']}. "
                f"Search for all 'ERROR' entries in {log_path}."
            ),
            "hint_command": "grep",
            "validation": {
                "type": "player_output_contains",
                "expected": "ERROR",
            },
            "success_message": f"Found {error_count} errors — good detective work!",
            "points": 15,
        })

        # 3. grep + wc pipe — count errors
        challenges.append({
            "id": "l2_pipe_count",
            "instruction": (
                f"Now count exactly how many ERROR lines there are in {log_path}. "
                "Chain two commands together with a pipe."
            ),
            "hint_command": "wc",
            "validation": {
                "type": "player_output_contains",
                "expected": str(error_count),
            },
            "success_message": (
                f"{error_count} errors confirmed. Piping commands is a superpower!"
            ),
            "points": 20,
        })
    else:
        # Fallback when no ERROR lines: count WARNING lines instead
        warning_count = len([l for l in log_lines if "WARNING" in l])
        challenges.append({
            "id": "l2_grep",
            "instruction": (
                f"Find all 'WARNING' entries in {log_path} to spot potential issues."
            ),
            "hint_command": "grep",
            "validation": {
                "type": "player_output_contains",
                "expected": "WARNING",
            },
            "success_message": f"Found {warning_count} warnings — stay alert!",
            "points": 15,
        })

    # 4. sort — sort the log
    challenges.append({
        "id": "l2_sort",
        "instruction": (
            f"Sort {log_path} alphabetically so entries of the same type group together."
        ),
        "hint_command": "sort",
        "validation": {
            "type": "player_output_contains",
            "expected": "INFO",
        },
        "success_message": "Sorted! Notice how the entries group by type now.",
        "points": 15,
    })

    # 5. cut + sort + uniq — unique categories in CSV
    if csv_file:
        csv_lines = csv_file["content"].strip().split("\n")
        categories = set()
        for line in csv_lines[1:]:  # skip header
            parts = line.split(",")
            if len(parts) >= 3:
                categories.add(parts[2].strip())
        unique_count = len(categories)

        challenges.append({
            "id": "l2_uniq",
            "instruction": (
                f"The file {csv_file['path']} has a 'category' column (3rd column). "
                "Find out how many unique categories there are. "
                "Chain cut, sort, and uniq together."
            ),
            "hint_command": "uniq",
            "validation": {
                "type": "player_output_contains",
                "expected": str(unique_count),
            },
            "success_message": (
                f"{unique_count} unique categories — you just built a real data pipeline!"
            ),
            "points": 25,
        })

    return challenges
