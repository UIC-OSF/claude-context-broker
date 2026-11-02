#!/usr/bin/env python3
"""Paired Context Broker benchmark: run full Claude Code sessions in two conditions.

For every task and repetition this runs `claude -p` once in the chosen condition,
records exit state, elapsed time, Claude's usage and total_cost_usd, every worker
usage record repo-read emitted, and whether the task's acceptance checks passed.
The baseline condition runs with CONTEXT_BROKER_DISABLE=1 so the hooks are off.
Each task's `reset` commands run before every repetition so run N+1 never sees
run N's edits.

Usage:
  run.py --init                       write an example tasks file to .context-broker/bench/tasks.json
  run.py --condition baseline --runs 3
  run.py --condition broker   --runs 3
  score.py                            summarise .context-broker/bench/results.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = Path(".context-broker") / "bench"
DEFAULT_TASKS = BENCH_DIR / "tasks.json"
DEFAULT_RESULTS = BENCH_DIR / "results.jsonl"
PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parents[1])
BROKER_HINT = " For broad exploration of large files use the context-broker bulk-reader skill, then verify consequential findings with bounded reads."

EXAMPLE_TASKS = [
    {
        "id": "authorization-map",
        "prompt": "Trace authorization for course import. Identify the entry point, the checks, and any missing role check. Do not edit files.",
        "max_turns": 12,
        "reset": ["git checkout -- . && git clean -fdq -e .context-broker -e .claude"],
        "checks": ["git diff --quiet && test -z \"$(git status --porcelain)\""],
    },
    {
        "id": "small-fix",
        "prompt": "REPLACE ME: a small, well-specified change with a test that proves it, e.g. 'Make X return Y when Z; run the test suite.'",
        "max_turns": 25,
        "reset": ["git checkout -- . && git clean -fdq -e .context-broker -e .claude"],
        "checks": ["REPLACE ME: a command that exits 0 only if the change is correct, e.g. 'npm test -- --grep X'"],
    },
]


def usage_from(stdout: str) -> dict:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    usage = dict(payload.get("usage") or {})
    if payload.get("total_cost_usd") is not None:
        usage["total_cost_usd"] = payload["total_cost_usd"]
    if payload.get("num_turns") is not None:
        usage["num_turns"] = payload["num_turns"]
    return usage


def worker_usage_from(text: str) -> list:
    found = []
    for line in text.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and "context_broker_worker" in record:
            found.append(record["context_broker_worker"])
    return found


def build_command(task: dict, condition: str, claude: str) -> str:
    if f"{condition}_command" in task:  # full override, for unusual setups
        return task[f"{condition}_command"]
    prompt = task.get(f"{condition}_prompt") or task["prompt"]
    if condition == "broker" and not task.get("broker_prompt") and task.get("add_broker_hint", True):
        prompt += BROKER_HINT
    # The prompt goes right after -p: --allowedTools is variadic and would swallow
    # a trailing positional. stdin is /dev/null so claude does not wait on it.
    parts = [claude, "-p", prompt, "--output-format", "json", "--max-turns", str(task.get("max_turns", 20))]
    if task.get("model"):
        parts += ["--model", task["model"]]
    if task.get("permission_mode"):
        parts += ["--permission-mode", task["permission_mode"]]
    # A non-interactive session cannot answer a permission prompt, so unless the
    # task bypasses permissions the broker command must be pre-approved or the
    # "broker" condition silently never runs the broker. Allow it in both
    # conditions for symmetry; in the baseline repo-read refuses to run anyway.
    allowed = list(task.get("allowed_tools", []))
    if task.get("permission_mode") != "bypassPermissions":
        allowed.append(f"Bash({PLUGIN_ROOT}/scripts/repo-read:*)")
    if allowed:
        parts += ["--allowedTools", ",".join(allowed)]
    return " ".join(shlex.quote(p) for p in parts) + " < /dev/null"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--init", action="store_true", help="write an example tasks file and exit")
    parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    parser.add_argument("--condition", choices=("baseline", "broker"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--claude", default="claude", help="claude executable (tests point this at a stub)")
    parser.add_argument("--only", help="comma-separated task ids to run (default: all)")
    args = parser.parse_args()

    tasks_path = Path(args.tasks)
    if args.init:
        if tasks_path.exists():
            print(f"{tasks_path} already exists; edit it or delete it first", file=sys.stderr)
            return 1
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text(json.dumps(EXAMPLE_TASKS, indent=2) + "\n")
        print(f"wrote {tasks_path}; replace the REPLACE ME entries before running")
        return 0
    if not args.condition:
        parser.error("--condition is required unless --init is given")
    if not tasks_path.is_file():
        print(f"no tasks file at {tasks_path}; run with --init first", file=sys.stderr)
        return 1
    tasks = json.loads(tasks_path.read_text())
    if args.only:
        wanted = set(args.only.split(","))
        tasks = [t for t in tasks if t["id"] in wanted]
        if not tasks:
            print(f"no tasks matched --only {args.only}", file=sys.stderr)
            return 1
    unfilled = [t["id"] for t in tasks if "REPLACE ME" in json.dumps(t)]
    if unfilled:
        print(f"tasks still contain REPLACE ME placeholders: {', '.join(unfilled)}", file=sys.stderr)
        return 1

    results = Path(args.results)
    results.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "CONTEXT_BROKER_DISABLE": "1" if args.condition == "baseline" else "0"}
    total_cost = 0.0
    with results.open("a") as out:
        for task in tasks:
            command = build_command(task, args.condition, args.claude)
            for repetition in range(1, args.runs + 1):
                for reset in task.get("reset", []):
                    subprocess.run(reset, shell=True, check=True)
                # repo-read runs inside the session, so its stderr never reaches us;
                # it appends worker usage to this file instead.
                usage_log = results.parent / "worker-usage" / f"{task['id']}-{args.condition}-{repetition}.jsonl"
                usage_log.parent.mkdir(parents=True, exist_ok=True)
                usage_log.unlink(missing_ok=True)
                began = time.monotonic()
                completed = subprocess.run(command, shell=True, text=True, capture_output=True, env={**env, "CONTEXT_BROKER_USAGE_LOG": str(usage_log)})
                elapsed = round(time.monotonic() - began, 3)
                checks = [subprocess.run(c, shell=True, capture_output=True).returncode == 0 for c in task.get("checks", [])]
                usage = usage_from(completed.stdout)
                workers = worker_usage_from(usage_log.read_text() if usage_log.exists() else "") or worker_usage_from(completed.stderr)
                record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "task": task["id"], "condition": args.condition, "run": repetition,
                    "exit_code": completed.returncode, "elapsed_seconds": elapsed,
                    "checks_passed": bool(checks) and all(checks), "usage": usage, "worker_usage": workers,
                    "stdout": completed.stdout, "stderr": completed.stderr,
                }
                out.write(json.dumps(record) + "\n")
                cost = float(usage.get("total_cost_usd") or 0) + sum(float(w.get("total_cost_usd") or 0) for w in workers)
                total_cost += cost
                print(f"{task['id']} {args.condition} #{repetition}: {elapsed}s exit={completed.returncode} checks={'pass' if record['checks_passed'] else 'FAIL'} cost=${cost:.4f}")
    print(f"\n{args.condition}: {len(tasks) * args.runs} runs, ${total_cost:.4f} total. Results appended to {results}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
