"""Shared helpers for Context Broker PreToolUse hooks.

Hooks fail open: any unexpected error exits 0 so a broken hook never blocks
work. Set CONTEXT_BROKER_DISABLE=1 to turn the hooks off (used by the paired
benchmark's baseline condition).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_THRESHOLD = 750
READ_TOOL_DEFAULT_LIMIT = 2000  # Claude Code's Read tool caps a call at this many lines.


def disabled() -> bool:
    return os.environ.get("CONTEXT_BROKER_DISABLE", "") not in ("", "0", "false")


def threshold() -> int:
    try:
        return int(os.environ.get("CONTEXT_BROKER_MIN_LINES", DEFAULT_THRESHOLD))
    except ValueError:
        return DEFAULT_THRESHOLD


def read_input() -> dict:
    return json.loads(sys.stdin.read() or "{}")


def base_dir(payload: dict) -> Path:
    for candidate in (payload.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if candidate:
            return Path(candidate)
    return Path.cwd()


def line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def deny(reason: str) -> None:
    json.dump(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}},
        sys.stdout,
    )
    sys.stdout.write("\n")


def run(main) -> int:
    if disabled():
        return 0
    try:
        return main(read_input()) or 0
    except Exception:  # noqa: BLE001 - fail open by design
        return 0
