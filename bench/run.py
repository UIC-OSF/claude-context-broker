#!/usr/bin/env python3
"""Run matched Claude Code benchmark conditions and append machine-readable records."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def usage_from(stdout: str) -> dict:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    # Claude output fields can evolve; preserve any recognized usage object.
    return payload.get("usage") or payload.get("result", {}).get("usage") or {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--condition", choices=("baseline", "broker"), required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--results", default="bench/results.jsonl")
    args = parser.parse_args()
    tasks = json.loads(Path(args.tasks).read_text())
    results = Path(args.results)
    results.parent.mkdir(parents=True, exist_ok=True)

    with results.open("a") as out:
        for task in tasks:
            command = task[f"{args.condition}_command"]
            for repetition in range(1, args.runs + 1):
                began = time.monotonic()
                completed = subprocess.run(command, shell=True, text=True, capture_output=True)
                checks = [subprocess.run(c, shell=True).returncode == 0 for c in task.get("checks", [])]
                record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "task": task["id"], "condition": args.condition, "run": repetition,
                    "exit_code": completed.returncode,
                    "elapsed_seconds": round(time.monotonic() - began, 3),
                    "checks_passed": all(checks), "usage": usage_from(completed.stdout),
                    "stdout": completed.stdout, "stderr": completed.stderr,
                }
                out.write(json.dumps(record) + "\n")
                print(f"{task['id']} {args.condition} #{repetition}: {record['elapsed_seconds']}s, exit={completed.returncode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
