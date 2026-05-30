"""Tests for the challenge checker.

Placeholder — real tests are added in TICKET-3. For now this just confirms the
module imports cleanly and exposes the expected entry point.
"""

from src.engine import checker  # noqa: F401


def test_checker_module_imports():
    assert hasattr(checker, "validate_challenge")
