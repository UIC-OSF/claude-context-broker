import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

BENCH = Path(__file__).parents[1] / "plugins" / "context-broker" / "bench"
STUB = r'''#!/usr/bin/env bash
# Stub claude: echo a JSON result; emit a worker usage line on stderr in broker mode.
if [[ "${CONTEXT_BROKER_DISABLE:-0}" == "0" ]]; then
  echo '{"context_broker_worker":{"model":"haiku","total_cost_usd":0.002}}' >&2
fi
printf '%s' '{"result":"done","usage":{"input_tokens":100,"cache_read_input_tokens":50,"output_tokens":20},"total_cost_usd":0.01,"num_turns":3}'
'''


class BenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.stub = self.root / "claude"
        self.stub.write_text(STUB)
        self.stub.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def run_py(self, *args):
        return subprocess.run(["python3", str(BENCH / "run.py"), *args], cwd=self.root, text=True, capture_output=True, env={**os.environ, "CONTEXT_BROKER_DISABLE": "0"})

    def test_init_then_refuses_placeholders(self):
        self.assertEqual(self.run_py("--init").returncode, 0)
        self.assertTrue((self.root / ".context-broker" / "bench" / "tasks.json").is_file())
        result = self.run_py("--condition", "baseline", "--claude", str(self.stub))
        self.assertEqual(result.returncode, 1)
        self.assertIn("REPLACE ME", result.stderr)

    def test_both_conditions_record_cost_and_score(self):
        tasks = self.root / "tasks.json"
        tasks.write_text(json.dumps([{"id": "t1", "prompt": "do it", "reset": ["true"], "checks": ["true"]}]))
        for condition in ("baseline", "broker"):
            result = self.run_py("--tasks", str(tasks), "--condition", condition, "--runs", "2", "--claude", str(self.stub))
            self.assertEqual(result.returncode, 0, result.stderr)
        rows = [json.loads(l) for l in (self.root / ".context-broker" / "bench" / "results.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 4)
        baseline = [r for r in rows if r["condition"] == "baseline"]
        broker = [r for r in rows if r["condition"] == "broker"]
        self.assertEqual(baseline[0]["worker_usage"], [])
        self.assertEqual(broker[0]["worker_usage"][0]["total_cost_usd"], 0.002)
        self.assertTrue(all(r["checks_passed"] for r in rows))
        score = subprocess.run(["python3", str(BENCH / "score.py")], cwd=self.root, text=True, capture_output=True)
        self.assertEqual(score.returncode, 0, score.stderr)
        self.assertIn("t1\tbroker\t2\t100%", score.stdout)
        self.assertIn("0.0120", score.stdout)  # 0.01 primary + 0.002 worker

    def test_failed_check_recorded(self):
        tasks = self.root / "tasks.json"
        tasks.write_text(json.dumps([{"id": "t1", "prompt": "do it", "checks": ["false"]}]))
        self.run_py("--tasks", str(tasks), "--condition", "baseline", "--runs", "1", "--claude", str(self.stub))
        row = json.loads((self.root / ".context-broker" / "bench" / "results.jsonl").read_text())
        self.assertFalse(row["checks_passed"])


if __name__ == "__main__":
    unittest.main()
