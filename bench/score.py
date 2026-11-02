#!/usr/bin/env python3
"""Summarize matched runs; add blinded quality scores separately before deciding."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from statistics import mean


def primary_cost(row: dict) -> float:
    return float(row.get("usage", {}).get("total_cost_usd") or 0.0)


def worker_cost(row: dict) -> float:
    return sum(float(w.get("total_cost_usd") or 0.0) for w in row.get("worker_usage", []))


def uncached_input(usage: dict) -> int:
    # Cache reads are billed at a fraction of input; do not add them to input tokens.
    return int(usage.get("input_tokens") or 0) + int(usage.get("cache_creation_input_tokens") or 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    groups = defaultdict(list)
    with open(args.results) as source:
        for line in source:
            row = json.loads(line)
            groups[(row["task"], row["condition"])].append(row)
    print("task\tcondition\truns\tcheck-pass\tmean-sec\tuncached-in\tcache-read\tout\tprimary-usd\tworker-usd\ttotal-usd")
    for (task, condition), rows in sorted(groups.items()):
        usages = [r.get("usage", {}) for r in rows]
        primary = mean(primary_cost(r) for r in rows)
        worker = mean(worker_cost(r) for r in rows)
        print(
            f"{task}\t{condition}\t{len(rows)}\t{mean(r['checks_passed'] for r in rows):.0%}\t{mean(r['elapsed_seconds'] for r in rows):.1f}"
            f"\t{mean(uncached_input(u) for u in usages):.0f}\t{mean(int(u.get('cache_read_input_tokens') or 0) for u in usages):.0f}"
            f"\t{mean(int(u.get('output_tokens') or 0) for u in usages):.0f}\t{primary:.4f}\t{worker:.4f}\t{primary + worker:.4f}"
        )
    print("\nDecision rule: compare blinded quality scores first; reject the broker if quality falls beyond the preset margin.")
    print("Then compare total-usd (primary + worker). Token columns are informational; cost is the comparable figure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
