"""Centralised subprocess helper.

P0-1 fix (2026-10-26 upgrade report):
All subprocess.run calls across the codebase were previously opening
child processes with implicit locale-dependent stdout/stderr decoding
(GBK on Chinese Windows, cp1252 on US Windows, UTF-8 on Linux/macOS).
When a child process emitted a character the local codec could not
decode, `p.stdout` was either mojibake or raised UnicodeDecodeError,
and gates 61/64 crashed with `None` participating in string ops.

Rule enforced here: **every** subprocess.run call in this project MUST
use `text=True, encoding='utf-8', errors='replace'` so that a child
process's output is always decoded deterministically, independent of
the caller's locale.

Public API:
  run_capture(args, *, cwd=None, timeout=None, env=None, check=False)
      -> RunResult

  RunResult has:
    - returncode: int
    - stdout: str    (never None)
    - stderr: str    (never None)
    - ok: bool       (returncode == 0)
    - timeout: bool  (True if timed out)
    - error: str     ("" on success, exception message on unexpected
                     failure such as FileNotFoundError)
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    timeout: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timeout and not self.error


def run_capture(
    args: Sequence[str] | str,
    *,
    cwd: str | Path | None = None,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
    check: bool = False,
) -> RunResult:
    """Run a command with guaranteed UTF-8 decoding on stdout/stderr.

    Never raises for the *child* failing to exit 0 — use `.ok` /
    `.returncode` to check. Only raises when the process cannot be
    launched at all (FileNotFoundError etc.), and even then returns
    a RunResult with `.error` set instead of raising, unless
    `check=True` is passed.
    """
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            timeout=timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=check,
        )
        return RunResult(
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )
    except subprocess.TimeoutExpired:
        return RunResult(
            returncode=-1,
            stdout="",
            stderr="TIMEOUT after %ss" % timeout,
            timeout=True,
        )
    except FileNotFoundError as e:
        return RunResult(returncode=-1, stdout="", stderr=str(e), error=str(e))
    except OSError as e:
        return RunResult(returncode=-1, stdout="", stderr=str(e), error=str(e))


def run_bytes(args: Sequence[str] | str, **kwargs: Any) -> tuple[int, bytes, bytes]:
    """Binary-safe variant for callers that need raw bytes.

    Returns (returncode, stdout_bytes, stderr_bytes). Never raises.
    """
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            timeout=kwargs.get("timeout"),
            env=kwargs.get("env"),
        )
        return proc.returncode, proc.stdout or b"", proc.stderr or b""
    except subprocess.TimeoutExpired:
        return -1, b"", b"TIMEOUT"
    except (FileNotFoundError, OSError) as e:
        return -1, b"", str(e).encode("utf-8", "replace")
