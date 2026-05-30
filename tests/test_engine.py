"""Tests for the sandbox and runner engine.

Placeholder — real tests are added in TICKET-2 (sandbox/runner) and TICKET-6
(theme_builder). For now this just confirms the modules import cleanly.
"""

from src.engine import sandbox, runner, theme_builder  # noqa: F401


def test_engine_modules_import():
    assert hasattr(sandbox, "create_sandbox")
    assert hasattr(runner, "execute_command")
    assert hasattr(theme_builder, "build_level_from_theme")
