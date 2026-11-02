import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
COMMAND = [str(ROOT / "bin" / "repo-read")]


class RepoReadTests(unittest.TestCase):
    def test_dry_run_builds_bounded_request(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "example.py"
            path.write_text("def hello():\n    return 'hi'\n")
            result = subprocess.run(COMMAND + ["--question", "What does it do?", "--paths", str(path), "--dry-run"], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["request"]["files"][0]["path"], str(path))

    def test_refuses_secret_named_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("SECRET=value\n")
            result = subprocess.run(COMMAND + ["--question", "Read it", "--paths", str(path), "--dry-run"], text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("potentially sensitive", result.stderr)

    def test_worker_response_is_printed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "example.py"
            path.write_text("x = 1\n")
            worker = Path(folder) / "worker.sh"
            worker.write_text("#!/usr/bin/env bash\ncat >/dev/null\nprintf '%s\\n' '{\"answer\":\"- example.py:1 â x is one\",\"model\":\"test\"}'\n")
            worker.chmod(0o755)
            env = {**os.environ, "CONTEXT_BROKER_WORKER": str(worker)}
            result = subprocess.run(COMMAND + ["--question", "What is x?", "--paths", str(path)], text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("x is one", result.stdout)


if __name__ == "__main__":
    unittest.main()
