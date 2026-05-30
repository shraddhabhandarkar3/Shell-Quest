"""Challenge checker.

Validates whether a challenge has been solved. Level 1 uses state-based checks
(inspecting the sandbox filesystem); Level 2 uses output-based checks (inspecting
the player's most recent stdout). Implemented in TICKET-3.
"""

import os


def validate_challenge(
    validation: dict,
    sandbox_path: str,
    current_dir: str,
    last_stdout: str = "",
) -> dict:
    """Check whether a challenge's success condition is met.

    Args:
        validation: dict with "type" and optional "target"/"expected".
        sandbox_path: root of the sandbox directory.
        current_dir: the player's current working directory.
        last_stdout: stdout from the player's most recent command
            (used by player_output_* validation types).

    Returns:
        {"passed": bool, "message": str}
    """
    vtype = validation["type"]
    target = validation.get("target", "")
    expected = validation.get("expected", "")

    try:
        # === STATE-BASED CHECKS (Level 1) ===
        # Inspect the filesystem — don't care what command the player ran.

        if vtype == "file_exists":
            path = os.path.join(sandbox_path, target)
            if os.path.exists(path):
                return {"passed": True, "message": "File found!"}
            return {"passed": False, "message": f"File not found at {target}"}

        elif vtype == "file_not_exists":
            path = os.path.join(sandbox_path, target)
            if not os.path.exists(path):
                return {"passed": True, "message": "File successfully removed!"}
            return {"passed": False, "message": f"File still exists at {target}"}

        elif vtype == "dir_exists":
            path = os.path.join(sandbox_path, target)
            if os.path.isdir(path):
                return {"passed": True, "message": "Directory created!"}
            return {"passed": False, "message": "Directory not found"}

        elif vtype == "file_content_contains":
            path = os.path.join(sandbox_path, target)
            if not os.path.exists(path):
                return {"passed": False, "message": f"File {target} not found"}
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if str(expected) in content:
                return {"passed": True, "message": "Content verified!"}
            return {"passed": False, "message": "Expected content not found in file"}

        # === OUTPUT-BASED CHECKS (Level 2) ===
        # Check what the player's last command printed to stdout.

        elif vtype == "player_output_contains":
            if not last_stdout.strip():
                return {"passed": False, "message": "Run a command to produce output"}
            if expected.lower() in last_stdout.lower():
                return {"passed": True, "message": "Correct output!"}
            return {"passed": False, "message": "Not quite — check your command"}

        elif vtype == "player_output_equals":
            if not last_stdout.strip():
                return {"passed": False, "message": "Run a command to produce output"}
            actual = last_stdout.strip()
            exp = str(expected).strip()
            if not exp:
                return {"passed": False, "message": "Challenge answer not computed yet"}
            if actual == exp:
                return {"passed": True, "message": "Correct!"}
            # Single-value outputs (e.g. wc -l): "25 file.txt" should match "25"
            if "\n" not in exp and exp in actual.split():
                return {"passed": True, "message": "Correct!"}
            return {"passed": False, "message": "Not quite — check your command"}

        elif vtype == "player_output_all_lines_contain":
            # Every non-empty output line must contain `expected`.
            # Catches: grep passes (all lines are matches), cat fails (has non-matching lines).
            if not last_stdout.strip():
                return {"passed": False, "message": "Run a command to produce output"}
            non_empty = [l for l in last_stdout.splitlines() if l.strip()]
            if not non_empty:
                return {"passed": False, "message": "Run a command to produce output"}
            if all(expected.lower() in line.lower() for line in non_empty):
                return {"passed": True, "message": "Correct output!"}
            return {"passed": False, "message": "Not quite — your output contains lines that don't match"}

        elif vtype == "player_output_first_line_contains":
            # The first non-empty output line must contain `expected`.
            # Catches: sort passes (ERROR sorts first alphabetically), cat fails (random first line).
            if not last_stdout.strip():
                return {"passed": False, "message": "Run a command to produce output"}
            non_empty = [l for l in last_stdout.splitlines() if l.strip()]
            if not non_empty:
                return {"passed": False, "message": "Run a command to produce output"}
            if expected.lower() in non_empty[0].lower():
                return {"passed": True, "message": "Correct output!"}
            return {"passed": False, "message": "Not quite — check the order of your output"}

        else:
            return {"passed": False, "message": f"Unknown validation type: {vtype}"}

    except Exception as e:
        return {"passed": False, "message": f"Validation error: {str(e)}"}
