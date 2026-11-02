#!/usr/bin/env python3
"""Summarize matched runs; add blinded quality scores separately before deciding."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from statistics import mean


def primary_tokens(usage: dict) -> int:
    return sum(v for k, v in usage.items() if isinstance(v, int) and "token" in k)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    groups = defaultdict(list)
    with open(args.results) as source:
        for line in source:
            row = json.loads(line)
            groups[(row["task"], row["condition"])].append(row)
    print("task\tcondition\truns\tcheck-pass-rate\tmean-seconds\tmean-primary-tokens")
    for (task, condition), rows in sorted(groups.items()):
        print(f"{task}\t{condition}\t{len(rows)}\t{mean(r['checks_passed'] for r in rows):.2%}\t{mean(r['elapsed_seconds'] for r in rows):.2f}\t{mean(primary_tokens(r['usage']) for r in rows):.0f}")
    print("\nDecision rule: compare blinded quality scores first; reject the broker if quality falls beyond the preset margin. Then add worker-model cost to primary-model cost before evaluating savings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
