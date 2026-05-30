"""Command runner.

Executes the player's shell commands inside the sandbox with safety guards:
blocks dangerous/privileged commands, interactive programs, and path escapes,
and enforces a timeout. Also handles `cd` navigation. Implemented in TICKET-2.
"""

import os
import re
import subprocess


BLOCKED_PREFIXES = [
    "sudo", "su ", "apt", "yum", "pip", "python", "python3",
    "node", "curl", "wget", "ssh", "nc", "dd", "mkfs", "fdisk",
    "mount", "umount", "reboot", "shutdown", "systemctl",
    "service", "chmod 777", "chown",
]

INTERACTIVE_COMMANDS = [
    "nano", "vim", "vi", "less", "more", "top", "htop", "man",
    "emacs", "pico",
]


def execute_command(command: str, cwd: str, sandbox_root: str) -> dict:
    """Run a single shell command inside the sandbox.

    Args:
        command: the raw command string typed by the player.
        cwd: the player's current working directory.
        sandbox_root: root of the sandbox (used to confine path access).

    Returns:
        {"stdout": str, "stderr": str, "exit_code": int}
    """
    command = command.strip()
    if not command:
        return {"stdout": "", "stderr": "", "exit_code": 0}

    base_cmd = command.split("|")[0].strip().split()[0] if command.strip() else ""

    if base_cmd in INTERACTIVE_COMMANDS:
        return {
            "stdout": "",
            "stderr": "Interactive programs aren't supported in ShellQuest. Try cat, grep, or echo instead.",
            "exit_code": 1,
        }

    for prefix in BLOCKED_PREFIXES:
        if command.startswith(prefix) or command.startswith(f"/{prefix}"):
            return {
                "stdout": "",
                "stderr": f"'{base_cmd}' is not available in ShellQuest. Stick to file and text commands!",
                "exit_code": 1,
            }

    tokens = command.split()
    for token in tokens:
        if ".." in token:
            resolved = os.path.realpath(os.path.join(cwd, token))
            sandbox_real = os.path.realpath(sandbox_root)
            if not resolved.startswith(sandbox_real):
                return {
                    "stdout": "",
                    "stderr": "Can't access paths outside the sandbox!",
                    "exit_code": 1,
                }

    if re.match(r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?(/|\*|/\*)", command):
        return {
            "stdout": "",
            "stderr": "Nice try — but we're protecting the filesystem here!",
            "exit_code": 1,
        }

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
            env={**os.environ, "HOME": sandbox_root},
        )
        stdout = result.stdout
        lines = stdout.split("\n")
        if len(lines) > 80:
            stdout = "\n".join(lines[:40]) + f"\n... ({len(lines) - 40} more lines)\n"
        return {
            "stdout": stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "Command timed out (5s limit). Try a simpler command.",
            "exit_code": 1,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": 1,
        }


def handle_cd(args: str, current_dir: str, sandbox_root: str) -> dict:
    """Resolve a `cd` request, keeping the player inside the sandbox.

    Args:
        args: the argument to `cd` (e.g. "subdir", "..", "~", or "").
        current_dir: the player's current working directory.
        sandbox_root: root of the sandbox.

    Returns:
        {"new_dir": str | None, "error": str | None}
    """
    if not args or args == "~":
        return {"new_dir": sandbox_root, "error": None}

    target = os.path.realpath(os.path.join(current_dir, args))
    sandbox_real = os.path.realpath(sandbox_root)

    if not target.startswith(sandbox_real):
        return {"new_dir": None, "error": "Can't navigate outside the sandbox"}
    if not os.path.isdir(target):
        return {"new_dir": None, "error": f"Not a directory: {args}"}
    return {"new_dir": target, "error": None}
