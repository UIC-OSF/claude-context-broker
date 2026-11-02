import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
PLUGIN = ROOT / "plugins" / "context-broker"
REPO_READ = [str(PLUGIN / "scripts" / "repo-read")]
ECHO_WORKER = 'cat >/dev/null; printf \'%s\\n\' \'{"answer":"- example.py:1 x is one","model":"test","usage":{"input_tokens":5,"output_tokens":2},"total_cost_usd":0.001}\''


def run(args, cwd, **env):
    return subprocess.run(args, text=True, capture_output=True, cwd=cwd, env={**os.environ, "CLAUDE_PROJECT_DIR": str(cwd), **env})


class RepoReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_dry_run_builds_bounded_request_with_relative_paths_and_nonce(self):
        self.write("example.py", "def hello():\n    return 'hi'\n")
        result = run(REPO_READ + ["--question", "What does it do?", "--paths", "example.py", "--dry-run"], self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        request = json.loads(result.stdout)["request"]
        self.assertEqual(request["files"][0]["path"], "example.py")
        self.assertEqual(request["files"][0]["content"], "1| def hello():\n2|     return 'hi'")
        self.assertEqual(request["files"][0]["lines"], 2)
        self.assertTrue(request["line_numbered"])
        self.assertEqual(len(request["nonce"]), 16)

    def test_line_numbers_are_width_padded(self):
        self.write("long.py", "".join(f"x{i} = {i}\n" for i in range(1, 13)))
        result = run(REPO_READ + ["--question", "q", "--paths", "long.py", "--dry-run"], self.root)
        content = json.loads(result.stdout)["request"]["files"][0]["content"].splitlines()
        self.assertEqual(content[0], " 1| x1 = 1")
        self.assertEqual(content[11], "12| x12 = 12")

    def test_refuses_secret_named_files(self):
        for name in (".env", ".env.local", "credentials.json", "service-account-prod.json", "terraform.tfstate", "prod.tfvars", ".npmrc", ".netrc", "id_ecdsa", "server.pem"):
            path = self.write(name, "x=1\n")
            result = run(REPO_READ + ["--question", "q", "--paths", str(path), "--dry-run"], self.root)
            self.assertEqual(result.returncode, 2, name)
            self.assertIn("potentially sensitive", result.stderr, name)

    def test_refuses_secret_like_content(self):
        path = self.write("config.py", "x = 1\nAWS = 'AKIAABCDEFGHIJKLMNOP'\n")
        result = run(REPO_READ + ["--question", "q", "--paths", str(path), "--dry-run"], self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("secret-like content at line 2", result.stderr)

    def test_refuses_paths_outside_project_root(self):
        outside = Path(tempfile.mkdtemp()) / "hosts.txt"
        outside.write_text("127.0.0.1 localhost\n")
        result = run(REPO_READ + ["--question", "q", "--paths", str(outside), "--dry-run"], self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside project root", result.stderr)

    def test_refuses_symlink_escaping_root(self):
        outside = Path(tempfile.mkdtemp()) / "secret.txt"
        outside.write_text("hello\n")
        (self.root / "link.txt").symlink_to(outside)
        result = run(REPO_READ + ["--question", "q", "--paths", "link.txt", "--dry-run"], self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside project root", result.stderr)

    def test_refuses_git_ignored_files(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write(".gitignore", "generated/\n")
        self.write("generated/out.txt", "data\n")
        result = run(REPO_READ + ["--question", "q", "--paths", "generated/out.txt", "--dry-run"], self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("git-ignored", result.stderr)

    def test_aggregate_ceiling(self):
        for i in range(3):
            self.write(f"f{i}.txt", "a" * 400_000 + "\n")
        result = run(REPO_READ + ["--question", "q", "--paths", "f0.txt", "f1.txt", "f2.txt", "--dry-run"], self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("aggregate ceiling", result.stderr)

    def test_worker_response_is_wrapped_and_usage_reported(self):
        self.write("example.py", "x = 1\n")
        result = run(REPO_READ + ["--question", "What is x?", "--paths", "example.py"], self.root, CONTEXT_BROKER_WORKER=ECHO_WORKER)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("UNTRUSTED WORKER OUTPUT", result.stdout)
        self.assertIn("----- begin worker output -----", result.stdout)
        self.assertIn("x is one", result.stdout)
        meta = json.loads(result.stderr.strip().splitlines()[-1])["context_broker_worker"]
        self.assertEqual(meta["total_cost_usd"], 0.001)

    def test_disabled_refuses_to_run(self):
        self.write("example.py", "x = 1\n")
        result = run(REPO_READ + ["--question", "q", "--paths", "example.py", "--dry-run"], self.root, CONTEXT_BROKER_DISABLE="1")
        self.assertEqual(result.returncode, 3)
        self.assertIn("disabled", result.stderr)

    def test_usage_log_written_when_requested(self):
        self.write("example.py", "x = 1\n")
        log = self.root / "usage.jsonl"
        result = run(REPO_READ + ["--question", "q", "--paths", "example.py"], self.root, CONTEXT_BROKER_WORKER=ECHO_WORKER, CONTEXT_BROKER_USAGE_LOG=str(log))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(log.read_text())["context_broker_worker"]["total_cost_usd"], 0.001)

    def test_works_without_claude_plugin_root(self):
        self.write("example.py", "x = 1\n")
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
        result = subprocess.run(REPO_READ + ["--question", "q", "--paths", "example.py", "--dry-run"], text=True, capture_output=True, cwd=self.root, env={**env, "CLAUDE_PROJECT_DIR": str(self.root)})
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
