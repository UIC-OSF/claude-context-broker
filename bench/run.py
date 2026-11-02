#!/usr/bin/env python3
"""Run matched Claude Code benchmark conditions and append machine-readable records.

Each task may declare `reset` commands that run before every repetition so run N+1
does not see run N's edits. The baseline condition runs with CONTEXT_BROKER_DISABLE=1.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def usage_from(stdout: str) -> dict:
    """Pull usage and cost out of `claude -p --output-format json` output."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    usage = dict(payload.get("usage") or {})
    if payload.get("total_cost_usd") is not None:
        usage["total_cost_usd"] = payload["total_cost_usd"]
    return usage


def worker_usage_from(stderr: str) -> list:
    """Collect the per-call worker usage lines that repo-read writes to stderr."""
    found = []
    for line in stderr.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and "context_broker_worker" in record:
            found.append(record["context_broker_worker"])
    return found


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
            # The baseline condition must run with the hook disabled; both conditions
            # otherwise share the same working tree and .claude/settings.json.
            env = {**os.environ, "CONTEXT_BROKER_DISABLE": "1" if args.condition == "baseline" else "0"}
            for repetition in range(1, args.runs + 1):
                for reset in task.get("reset", []):
                    subprocess.run(reset, shell=True, check=True)
                began = time.monotonic()
                completed = subprocess.run(command, shell=True, text=True, capture_output=True, env=env)
                checks = [subprocess.run(c, shell=True).returncode == 0 for c in task.get("checks", [])]
                record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "task": task["id"], "condition": args.condition, "run": repetition,
                    "exit_code": completed.returncode,
                    "elapsed_seconds": round(time.monotonic() - began, 3),
                    "checks_passed": all(checks), "usage": usage_from(completed.stdout),
                    "worker_usage": worker_usage_from(completed.stderr),
                    "stdout": completed.stdout, "stderr": completed.stderr,
                }
                out.write(json.dumps(record) + "\n")
                print(f"{task['id']} {args.condition} #{repetition}: {record['elapsed_seconds']}s, exit={completed.returncode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
