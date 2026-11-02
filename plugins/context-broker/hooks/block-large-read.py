#!/usr/bin/env python3
"""Deny Read calls whose effective line span exceeds the threshold.

A call is bounded only if the number of lines it can return is within the
threshold. offset without limit, or a limit larger than the threshold, is not a
bounded read and is treated like a full read.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _hooklib as lib  # noqa: E402


def to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def main(payload: dict) -> int:
    tool_input = payload.get("tool_input") or {}
    raw_path = tool_input.get("file_path")
    if not raw_path:
        return 0
    path = Path(raw_path)
    if not path.is_absolute():
        path = lib.base_dir(payload) / path
    if not path.is_file():
        return 0
    limit = lib.threshold()
    total = lib.line_count(path)
    if total <= limit:
        return 0
    offset = max(to_int(tool_input.get("offset"), 0), 0)
    requested = to_int(tool_input.get("limit"), lib.READ_TOOL_DEFAULT_LIMIT)
    span = min(max(requested, 0), max(total - offset, 0))
    if span <= limit:
        return 0
    lib.deny(
        f"Read of {path.name} spans {span} lines (file has {total}; threshold {limit}). "
        f"Search first, then use the Context Broker bulk-reader skill for exploration, "
        f"and request at most {limit} lines per Read (offset + limit) for exact source."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(lib.run(main))
