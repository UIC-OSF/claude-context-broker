#!/usr/bin/env python3
"""Deny shell commands that dump a whole large file into context.

Covers the common dump commands (cat, less, more, nl, bat, tac, pr, head, tail),
multiple file arguments, flags, quoting, trailing separators, `cd dir && cat f`,
and relative paths. It does not try to be a security boundary: a pipeline that
filters the output, or an arbitrary interpreter, is allowed. See README.
"""
from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _hooklib as lib  # noqa: E402

DUMPERS = {"cat", "less", "more", "nl", "bat", "tac", "pr", "head", "tail"}
SEPARATORS = re.compile(r"\s*(?:&&|\|\||;|\n)\s*")


def bounded_head_tail(argv: list[str], limit: int) -> bool:
    """head/tail with an explicit line count within the threshold, or a byte count."""
    for index, arg in enumerate(argv[1:], start=1):
        if arg in ("-c", "--bytes") or arg.startswith(("-c", "--bytes=")):
            return True
        if arg in ("-n", "--lines") and index + 1 < len(argv):
            value = argv[index + 1]
        elif arg.startswith("--lines="):
            value = arg.split("=", 1)[1]
        elif arg.startswith("-n"):
            value = arg[2:]
        elif re.fullmatch(r"-\d+", arg):
            value = arg[1:]
        else:
            continue
        if value.startswith("+"):
            return False  # tail -n +N streams from line N to the end
        digits = re.sub(r"\D", "", value)
        return bool(digits) and int(digits) <= limit
    return False  # bare head/tail default to 10 lines, handled by caller


def main(payload: dict) -> int:
    command = (payload.get("tool_input") or {}).get("command") or ""
    if "|" in command:
        return 0  # a pipeline filters; let it through
    limit = lib.threshold()
    cwd = lib.base_dir(payload)
    for segment in SEPARATORS.split(command):
        try:
            argv = shlex.split(segment, comments=False, posix=True)
        except ValueError:
            continue
        if not argv:
            continue
        name = Path(argv[0]).name
        if name == "cd" and len(argv) > 1:
            cwd = (cwd / Path(argv[1]).expanduser()).resolve()
            continue
        if name not in DUMPERS:
            continue
        if name in ("head", "tail"):
            if bounded_head_tail(argv, limit):
                continue
            if not any(a.startswith("-") for a in argv[1:]):
                continue  # default 10 lines
        files = []
        skip_next = False
        for arg in argv[1:]:
            if skip_next:
                skip_next = False
                continue
            if arg in ("<", ">", ">>"):
                continue
            if arg.startswith("-"):
                skip_next = name in ("head", "tail") and arg in ("-n", "--lines", "-c", "--bytes")
                continue
            candidate = Path(arg).expanduser()
            if not candidate.is_absolute():
                candidate = cwd / candidate
            if candidate.is_file():
                files.append(candidate)
        for path in files:
            total = lib.line_count(path)
            if total > limit:
                lib.deny(
                    f"`{name} {path.name}` would dump {total} lines (threshold {limit}). "
                    f"Use the Context Broker bulk-reader skill for exploration, or a bounded "
                    f"range (e.g. sed -n 'START,ENDp', head -n {limit}) for exact source."
                )
                return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(lib.run(main))
