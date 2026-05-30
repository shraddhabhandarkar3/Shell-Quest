"""Command runner.

Executes the player's shell commands inside the sandbox with safety guards:
blocks dangerous/privileged commands, interactive programs, and path escapes,
and enforces a timeout. Also handles `cd` navigation. Implemented in TICKET-2.
"""


def execute_command(command: str, cwd: str, sandbox_root: str) -> dict:
    """Run a single shell command inside the sandbox.

    Args:
        command: the raw command string typed by the player.
        cwd: the player's current working directory.
        sandbox_root: root of the sandbox (used to confine path access).

    Returns:
        {"stdout": str, "stderr": str, "exit_code": int}
    """
    raise NotImplementedError


def handle_cd(args: str, current_dir: str, sandbox_root: str) -> dict:
    """Resolve a `cd` request, keeping the player inside the sandbox.

    Args:
        args: the argument to `cd` (e.g. "subdir", "..", "~", or "").
        current_dir: the player's current working directory.
        sandbox_root: root of the sandbox.

    Returns:
        {"new_dir": str | None, "error": str | None}
    """
    raise NotImplementedError
