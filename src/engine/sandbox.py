"""Sandbox management.

Creates an isolated, disposable filesystem under /tmp/shellquest-{uuid} where the
player runs real shell commands, and seeds it with the themed files produced by
theme_builder. Implemented in TICKET-2.
"""

import os
import shutil
import uuid


def create_sandbox() -> tuple[str, callable]:
    """Create a fresh sandbox directory.

    Returns:
        (sandbox_path, cleanup_fn) where cleanup_fn() safely removes the sandbox.
    """
    sandbox_path = f"/tmp/shellquest-{uuid.uuid4().hex[:8]}"
    os.makedirs(sandbox_path, exist_ok=True)

    def cleanup_fn():
        if sandbox_path.startswith("/tmp/shellquest-"):
            shutil.rmtree(sandbox_path, ignore_errors=True)

    return sandbox_path, cleanup_fn


def seed_sandbox(sandbox_path: str, files: list[dict]) -> None:
    """Write the given files into the sandbox.

    Args:
        sandbox_path: root of the sandbox directory.
        files: list of {"path": "relative/path.txt", "content": "..."} dicts.
    """
    for file in files:
        full_path = os.path.join(sandbox_path, file["path"])
        parent = os.path.dirname(full_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(file["content"])

    # Pre-create archive/ as a pre-existing empty directory
    os.makedirs(os.path.join(sandbox_path, "archive"), exist_ok=True)
