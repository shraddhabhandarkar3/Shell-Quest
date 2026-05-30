"""Tests for the challenge checker (TICKET-3)."""

import os
import pytest

from src.engine.checker import validate_challenge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _val(vtype, target="", expected=""):
    return {"type": vtype, "target": target, "expected": expected}


# ---------------------------------------------------------------------------
# STATE-BASED: file_exists
# ---------------------------------------------------------------------------

def test_file_exists_pass(tmp_path):
    f = tmp_path / "report.txt"
    f.write_text("data")
    result = validate_challenge(_val("file_exists", "report.txt"), str(tmp_path), str(tmp_path))
    assert result["passed"] is True


def test_file_exists_fail(tmp_path):
    result = validate_challenge(_val("file_exists", "missing.txt"), str(tmp_path), str(tmp_path))
    assert result["passed"] is False
    assert "missing.txt" in result["message"]


# ---------------------------------------------------------------------------
# STATE-BASED: file_not_exists
# ---------------------------------------------------------------------------

def test_file_not_exists_pass(tmp_path):
    result = validate_challenge(_val("file_not_exists", "gone.txt"), str(tmp_path), str(tmp_path))
    assert result["passed"] is True


def test_file_not_exists_fail(tmp_path):
    f = tmp_path / "still_here.txt"
    f.write_text("oops")
    result = validate_challenge(_val("file_not_exists", "still_here.txt"), str(tmp_path), str(tmp_path))
    assert result["passed"] is False


# ---------------------------------------------------------------------------
# STATE-BASED: dir_exists
# ---------------------------------------------------------------------------

def test_dir_exists_pass(tmp_path):
    (tmp_path / "reports").mkdir()
    result = validate_challenge(_val("dir_exists", "reports"), str(tmp_path), str(tmp_path))
    assert result["passed"] is True


def test_dir_exists_fail(tmp_path):
    result = validate_challenge(_val("dir_exists", "reports"), str(tmp_path), str(tmp_path))
    assert result["passed"] is False


# ---------------------------------------------------------------------------
# STATE-BASED: file_content_contains
# ---------------------------------------------------------------------------

def test_file_content_pass(tmp_path):
    f = tmp_path / "log.txt"
    f.write_text("2024-03-15 ERROR: disk full\n")
    result = validate_challenge(
        _val("file_content_contains", "log.txt", "ERROR"),
        str(tmp_path), str(tmp_path)
    )
    assert result["passed"] is True


def test_file_content_fail(tmp_path):
    f = tmp_path / "log.txt"
    f.write_text("2024-03-15 INFO: all good\n")
    result = validate_challenge(
        _val("file_content_contains", "log.txt", "ERROR"),
        str(tmp_path), str(tmp_path)
    )
    assert result["passed"] is False


def test_file_content_missing_file(tmp_path):
    result = validate_challenge(
        _val("file_content_contains", "nofile.txt", "ERROR"),
        str(tmp_path), str(tmp_path)
    )
    assert result["passed"] is False
    assert "not found" in result["message"]


# ---------------------------------------------------------------------------
# OUTPUT-BASED: player_output_contains
# ---------------------------------------------------------------------------

def test_player_output_contains_pass(tmp_path):
    stdout = "ERROR: connection lost\nERROR: timeout\n"
    result = validate_challenge(
        _val("player_output_contains", expected="ERROR"),
        str(tmp_path), str(tmp_path),
        last_stdout=stdout
    )
    assert result["passed"] is True


def test_player_output_contains_fail(tmp_path):
    result = validate_challenge(
        _val("player_output_contains", expected="ERROR"),
        str(tmp_path), str(tmp_path),
        last_stdout="INFO: all good\n"
    )
    assert result["passed"] is False


def test_player_output_contains_empty(tmp_path):
    result = validate_challenge(
        _val("player_output_contains", expected="ERROR"),
        str(tmp_path), str(tmp_path),
        last_stdout=""
    )
    assert result["passed"] is False
    assert "Run a command" in result["message"]


def test_player_output_contains_case_insensitive(tmp_path):
    result = validate_challenge(
        _val("player_output_contains", expected="error"),
        str(tmp_path), str(tmp_path),
        last_stdout="Error Found\n"
    )
    assert result["passed"] is True


# ---------------------------------------------------------------------------
# OUTPUT-BASED: player_output_equals
# ---------------------------------------------------------------------------

def test_player_output_equals_pass(tmp_path):
    result = validate_challenge(
        _val("player_output_equals", expected="25"),
        str(tmp_path), str(tmp_path),
        last_stdout="25\n"
    )
    assert result["passed"] is True


def test_player_output_equals_with_filename(tmp_path):
    # wc -l prints "25 log.txt" on some systems — "25" should still pass
    result = validate_challenge(
        _val("player_output_equals", expected="25"),
        str(tmp_path), str(tmp_path),
        last_stdout="25 log.txt\n"
    )
    assert result["passed"] is True


def test_player_output_equals_fail(tmp_path):
    result = validate_challenge(
        _val("player_output_equals", expected="25"),
        str(tmp_path), str(tmp_path),
        last_stdout="30\n"
    )
    assert result["passed"] is False


def test_player_output_equals_empty(tmp_path):
    result = validate_challenge(
        _val("player_output_equals", expected="25"),
        str(tmp_path), str(tmp_path),
        last_stdout=""
    )
    assert result["passed"] is False
    assert "Run a command" in result["message"]


# ---------------------------------------------------------------------------
# Unknown type
# ---------------------------------------------------------------------------

def test_unknown_type(tmp_path):
    result = validate_challenge(
        {"type": "nonexistent_check"},
        str(tmp_path), str(tmp_path)
    )
    assert result["passed"] is False
    assert "Unknown" in result["message"]


# ---------------------------------------------------------------------------
# State-based checks ignore last_stdout
# ---------------------------------------------------------------------------

def test_state_check_ignores_stdout(tmp_path):
    (tmp_path / "reports").mkdir()
    # Even with garbage stdout, dir_exists should pass purely on filesystem state
    result = validate_challenge(
        _val("dir_exists", "reports"),
        str(tmp_path), str(tmp_path),
        last_stdout="some unrelated output"
    )
    assert result["passed"] is True


# ---------------------------------------------------------------------------
# Never raises — always returns a dict
# ---------------------------------------------------------------------------

def test_no_exception_on_bad_input(tmp_path):
    result = validate_challenge(
        {"type": "file_exists"},  # missing "target" key → defaults to ""
        str(tmp_path), str(tmp_path)
    )
    assert isinstance(result, dict)
    assert "passed" in result
