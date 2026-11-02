import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).parents[1] / "plugins" / "context-broker" / "hooks"
THRESHOLD = 750


def decision(hook, payload, **env):
    result = subprocess.run(["python3", str(HOOKS / hook)], input=json.dumps(payload), text=True, capture_output=True, env={**os.environ, **env})
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] if result.stdout.strip() else "allow"


class HookFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name).resolve()
        self.big = self.dir / "big.txt"
        self.big.write_text("".join(f"line {i}\n" for i in range(3000)))
        self.small = self.dir / "small.txt"
        self.small.write_text("".join(f"line {i}\n" for i in range(100)))
        (self.dir / "sub").mkdir()
        self.nested = self.dir / "sub" / "deep.txt"
        self.nested.write_text("".join(f"line {i}\n" for i in range(3000)))

    def tearDown(self):
        self.tmp.cleanup()


class ReadHookTests(HookFixture):
    def read(self, **tool_input):
        return decision("block-large-read.py", {"cwd": str(self.dir), "tool_input": tool_input})

    def test_full_read_denied(self):
        self.assertEqual(self.read(file_path=str(self.big)), "deny")

    def test_small_file_allowed(self):
        self.assertEqual(self.read(file_path=str(self.small)), "allow")

    def test_offset_without_limit_denied(self):
        self.assertEqual(self.read(file_path=str(self.big), offset=0), "deny")
        self.assertEqual(self.read(file_path=str(self.big), offset=1), "deny")

    def test_oversized_limit_denied(self):
        self.assertEqual(self.read(file_path=str(self.big), limit=999999), "deny")
        self.assertEqual(self.read(file_path=str(self.big), limit=2000), "deny")

    def test_bounded_read_allowed(self):
        self.assertEqual(self.read(file_path=str(self.big), offset=100, limit=THRESHOLD), "allow")
        self.assertEqual(self.read(file_path=str(self.big), limit=50), "allow")

    def test_offset_near_end_allowed(self):
        self.assertEqual(self.read(file_path=str(self.big), offset=2800), "allow")

    def test_relative_path_resolved_against_cwd(self):
        self.assertEqual(self.read(file_path="big.txt"), "deny")

    def test_disable_switch(self):
        self.assertEqual(decision("block-large-read.py", {"tool_input": {"file_path": str(self.big)}}, CONTEXT_BROKER_DISABLE="1"), "allow")

    def test_fails_open_on_garbage(self):
        result = subprocess.run(["python3", str(HOOKS / "block-large-read.py")], input="not json", text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")


class BashHookTests(HookFixture):
    def bash(self, command):
        return decision("block-large-bash-read.py", {"cwd": str(self.dir), "tool_input": {"command": command}})

    def test_denied_variants(self):
        for cmd in (
            f"cat {self.big}", f"cat -n {self.big}", f"cat {self.small} {self.big}", f"cat '{self.big}'", f'cat "{self.big}"',
            f"cat {self.big};", f"cat < {self.big}", f"head -n 100000 {self.big}", f"tail -n +1 {self.big}", f"head -2500 {self.big}",
            f"nl {self.big}", f"bat {self.big}", f"tac {self.big}", f"less {self.big}",
            "cat big.txt", "cat ./big.txt", "cd sub && cat deep.txt", f"cd {self.dir}/sub; cat deep.txt", "ls && cat big.txt",
        ):
            self.assertEqual(self.bash(cmd), "deny", cmd)

    def test_allowed_variants(self):
        for cmd in (
            f"cat {self.small}", f"head -n 50 {self.big}", f"head {self.big}", f"tail -n 20 {self.big}", f"head -c 4000 {self.big}",
            f"sed -n '10,40p' {self.big}", f"grep -n foo {self.big}", f"rg foo {self.big}", f"wc -l {self.big}",
            f"cat {self.big} | head -n 20", "cat missing.txt", "ls -la", "git status",
        ):
            self.assertEqual(self.bash(cmd), "allow", cmd)

    def test_disable_switch(self):
        self.assertEqual(decision("block-large-bash-read.py", {"cwd": str(self.dir), "tool_input": {"command": "cat big.txt"}}, CONTEXT_BROKER_DISABLE="1"), "allow")


if __name__ == "__main__":
    unittest.main()
