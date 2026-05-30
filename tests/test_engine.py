"""Tests for sandbox.py and runner.py (TICKET-2)."""

import os
import pytest

from src.engine.sandbox import create_sandbox, seed_sandbox
from src.engine.runner import execute_command, handle_cd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_seeded_sandbox():
    path, cleanup = create_sandbox()
    seed_sandbox(path, [
        {"path": "hello.txt", "content": "hello world\n"},
        {"path": "subdir/nested.txt", "content": "nested content\n"},
    ])
    return path, cleanup


# ---------------------------------------------------------------------------
# sandbox.py
# ---------------------------------------------------------------------------

def test_create_sandbox():
    path, cleanup = create_sandbox()
    assert os.path.isdir(path)
    assert path.startswith("/tmp/shellquest-")
    cleanup()
    assert not os.path.exists(path)


def test_seed_sandbox():
    path, cleanup = create_sandbox()
    try:
        seed_sandbox(path, [
            {"path": "data.txt", "content": "ocean data\n"},
            {"path": "logs/run.log", "content": "LOG\n"},
        ])
        assert open(os.path.join(path, "data.txt")).read() == "ocean data\n"
        assert open(os.path.join(path, "logs/run.log")).read() == "LOG\n"
        assert os.path.isdir(os.path.join(path, "archive"))
    finally:
        cleanup()


# ---------------------------------------------------------------------------
# runner.py — normal execution
# ---------------------------------------------------------------------------

def test_execute_ls():
    path, cleanup = make_seeded_sandbox()
    try:
        result = execute_command("ls", path, path)
        assert result["exit_code"] == 0
        assert "hello.txt" in result["stdout"]
    finally:
        cleanup()


def test_execute_pipe():
    path, cleanup = make_seeded_sandbox()
    try:
        result = execute_command("echo hello | wc -w", path, path)
        assert result["exit_code"] == 0
        assert "1" in result["stdout"]
    finally:
        cleanup()


# ---------------------------------------------------------------------------
# runner.py — blocked commands
# ---------------------------------------------------------------------------

def test_block_sudo():
    path, cleanup = make_seeded_sandbox()
    try:
        result = execute_command("sudo rm -rf /", path, path)
        assert result["exit_code"] == 1
        assert "not available" in result["stderr"]
    finally:
        cleanup()


def test_block_curl():
    path, cleanup = make_seeded_sandbox()
    try:
        result = execute_command("curl https://example.com", path, path)
        assert result["exit_code"] == 1
        assert "not available" in result["stderr"]
    finally:
        cleanup()


def test_block_interactive_vim():
    path, cleanup = make_seeded_sandbox()
    try:
        result = execute_command("vim hello.txt", path, path)
        assert result["exit_code"] == 1
        assert "Interactive" in result["stderr"]
    finally:
        cleanup()


def test_block_path_escape():
    path, cleanup = make_seeded_sandbox()
    try:
        result = execute_command("cat ../../etc/passwd", path, path)
        assert result["exit_code"] == 1
        assert "outside the sandbox" in result["stderr"]
    finally:
        cleanup()


# ---------------------------------------------------------------------------
# runner.py — timeout
# ---------------------------------------------------------------------------

def test_timeout():
    path, cleanup = make_seeded_sandbox()
    try:
        result = execute_command("sleep 10", path, path)
        assert result["exit_code"] == 1
        assert "timed out" in result["stderr"]
    finally:
        cleanup()


# ---------------------------------------------------------------------------
# handle_cd
# ---------------------------------------------------------------------------

def test_cd_into_subdir():
    path, cleanup = make_seeded_sandbox()
    try:
        result = handle_cd("subdir", path, path)
        assert result["error"] is None
        assert result["new_dir"] == os.path.realpath(os.path.join(path, "subdir"))
    finally:
        cleanup()


def test_cd_escape_blocked():
    path, cleanup = make_seeded_sandbox()
    try:
        result = handle_cd("../../..", path, path)
        assert result["new_dir"] is None
        assert "outside the sandbox" in result["error"]
    finally:
        cleanup()


def test_cd_nonexistent():
    path, cleanup = make_seeded_sandbox()
    try:
        result = handle_cd("doesnotexist", path, path)
        assert result["new_dir"] is None
        assert result["error"] is not None
    finally:
        cleanup()


def test_cd_home_returns_sandbox_root():
    path, cleanup = make_seeded_sandbox()
    try:
        result = handle_cd("~", path, path)
        assert result["error"] is None
        assert result["new_dir"] == path
    finally:
        cleanup()


def test_cd_empty_returns_sandbox_root():
    path, cleanup = make_seeded_sandbox()
    try:
        result = handle_cd("", path, path)
        assert result["error"] is None
        assert result["new_dir"] == path
    finally:
        cleanup()
