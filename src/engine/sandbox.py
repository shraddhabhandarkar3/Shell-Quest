"""Sandbox management.

Creates an isolated, disposable filesystem under /tmp/shellquest-{uuid} where the
player runs real shell commands, and seeds it with the themed files produced by
theme_builder. Implemented in TICKET-2.
"""


def create_sandbox() -> tuple[str, callable]:
    """Create a fresh sandbox directory.

    Returns:
        (sandbox_path, cleanup_fn) where cleanup_fn() safely removes the sandbox.
    """
    raise NotImplementedError


def seed_sandbox(sandbox_path: str, files: list[dict]) -> None:
    """Write the given files into the sandbox.

    Args:
        sandbox_path: root of the sandbox directory.
        files: list of {"path": "relative/path.txt", "content": "..."} dicts.
    """
    raise NotImplementedError
