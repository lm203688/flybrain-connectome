"""Unit tests for scripts/_subprocess_util.py.

P0-1 fix coverage: the helper must guarantee UTF-8 decoding of
subprocess output regardless of the caller's locale. Prior to the fix,
a Chinese-locale Windows environment would crash when a child process
emitted a non-ASCII byte (GBK cannot decode UTF-8 characters like
the → arrow in the audit CLI output).

These tests simulate that scenario by:
  1. Spawning a child that emits UTF-8 bytes including a non-ASCII char
  2. Verifying run_capture decodes them without raising UnicodeDecodeError
  3. Verifying errors='replace' substitutes U+FFFD for invalid sequences
  4. Verifying timeout and FileNotFoundError paths return, never raise
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from _subprocess_util import RunResult, run_capture, run_bytes  # noqa: E402


def test_run_capture_returns_result_object() -> None:
    r = run_capture([sys.executable, "-c", "print('hi')"])
    assert isinstance(r, RunResult)
    assert r.returncode == 0
    assert r.ok
    assert "hi" in r.stdout
    assert not r.timeout
    assert not r.error


def test_run_capture_utf8_survives_non_ascii() -> None:
    """P0-1 regression: a Chinese-locale caller must still decode UTF-8."""
    r = run_capture([sys.executable, "-c", "print('→ → → 果蝇脑连接组')"])
    assert r.ok
    assert "果蝇脑连接组" in r.stdout
    assert "→" in r.stdout


def test_run_capture_errors_replace_on_invalid_bytes() -> None:
    """Errors='replace' must not raise on malformed byte sequences."""
    # Emit a lone 0x80 byte which is invalid UTF-8.
    r = run_capture([sys.executable, "-c",
                     "import sys; sys.stdout.buffer.write(b'abc\\x80def')"])
    assert r.ok
    # The U+FFFD replacement character must appear in the decoded output.
    assert "\ufffd" in r.stdout


def test_run_capture_timeout_returns_timeout_result() -> None:
    r = run_capture([sys.executable, "-c", "import time; time.sleep(30)"],
                    timeout=0.5)
    assert r.timeout
    assert not r.ok
    assert r.returncode == -1
    assert "TIMEOUT" in r.stderr


def test_run_capture_file_not_found_returns_error() -> None:
    r = run_capture(["definitely-not-a-real-binary-xyz-12345"])
    assert r.error
    assert not r.ok


def test_run_bytes_returns_bytes_not_text() -> None:
    rc, out, err = run_bytes([sys.executable, "-c",
                              "import sys; sys.stdout.buffer.write(b'\\x80\\x81')"])
    assert rc == 0
    assert isinstance(out, bytes)
    assert len(out) == 2
