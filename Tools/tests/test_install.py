"""Installer tests: fresh install, re-run idempotency, merge into an existing project config.

    python -m unittest discover -s Tools/tests -v
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
INSTALL = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "install.py")


def install(target: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, HOME=target, USERPROFILE=target)  # --user never touches the real home
    return subprocess.run([sys.executable, INSTALL, target, "--keep-powershell", *args],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)


def settings(target: str) -> dict:
    with open(os.path.join(target, ".claude", "settings.json"), encoding="utf-8") as f:
        return json.load(f)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=TESTS, prefix="_work_")
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_fresh_install_then_rerun_is_noop(self):
        with open(os.path.join(self.dir, "Makefile"), "w", encoding="utf-8") as f:
            f.write("build:\n\tcc x.c\ntest:\n\t./t\n")
        r = install(self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        for rel in ("CLAUDE.md", ".claude/rulekit/ADAPT.md", ".claude/rulekit/manifest.json",
                    "Tools/claude_read_guard.py", ".claude/reference-rules/git.md"):
            self.assertTrue(os.path.isfile(os.path.join(self.dir, rel)), rel)
        self.assertEqual(settings(self.dir)["env"]["RULEKIT_VERIFY_RE"], r"make\ build|make\ test")
        self.assertIn("Stop", settings(self.dir)["hooks"])
        again = install(self.dir)
        self.assertIn("already up to date", again.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "CLAUDE.rulekit.md")))

    def test_merge_keeps_existing_config(self):
        os.makedirs(os.path.join(self.dir, ".claude"))
        own = {"outputStyle": "custom", "permissions": {"deny": ["WebFetch"], "allow": ["Bash(make:*)"]},
               "hooks": {"PreToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "own"}]}]}}
        with open(os.path.join(self.dir, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump(own, f)
        with open(os.path.join(self.dir, "CLAUDE.md"), "w", encoding="utf-8") as f:
            f.write("# Old\n")
        with open(os.path.join(self.dir, "Makefile"), "w", encoding="utf-8") as f:
            f.write("build:\n\tcc x.c\ntest:\n\t./t\n")
        r = install(self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        s = settings(self.dir)
        self.assertEqual(s["outputStyle"], "custom")
        self.assertIn("kept outputStyle", r.stdout)
        self.assertIn("WebFetch", s["permissions"]["deny"])
        self.assertIn("Agent", s["permissions"]["deny"])
        self.assertEqual(s["permissions"]["allow"], ["Bash(make:*)"])
        commands = [h["command"] for g in s["hooks"]["PreToolUse"] for h in g["hooks"]]
        self.assertEqual(commands[0], "own")
        self.assertEqual(sum("claude_read_guard" in c for c in commands), 1)
        with open(os.path.join(self.dir, "CLAUDE.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "# Old\n")
        with open(os.path.join(self.dir, "CLAUDE.rulekit.md"), encoding="utf-8") as f:
            self.assertIn("`make build`", f.read())
        self.assertTrue(os.path.isfile(os.path.join(self.dir, ".claude", "settings.json.rulekit-bak")))
        install(self.dir)
        s2 = settings(self.dir)
        self.assertEqual(sum("claude_read_guard" in h["command"] for g in s2["hooks"]["PreToolUse"]
                             for h in g["hooks"]), 1)

    def test_uninstall_removes_unchanged_files_and_kit_hooks(self):
        os.makedirs(os.path.join(self.dir, ".claude"))
        own = {"hooks": {"PreToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "own"}]}]}}
        with open(os.path.join(self.dir, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump(own, f)
        self.assertEqual(install(self.dir).returncode, 0)
        edited = os.path.join(self.dir, ".claude", "reference-rules", "git.md")
        with open(edited, "a", encoding="utf-8") as f:
            f.write("- local addition\n")
        r = install(self.dir, "--uninstall")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "Tools", "claude_read_guard.py")))
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".claude", "rulekit")))
        self.assertTrue(os.path.isfile(edited))
        self.assertIn("changed since install", r.stdout)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "CLAUDE.md")))
        commands = [h["command"] for g in settings(self.dir)["hooks"]["PreToolUse"] for h in g["hooks"]]
        self.assertEqual(commands, ["own"])
        self.assertNotIn("UserPromptSubmit", settings(self.dir)["hooks"])

    def test_hook_with_other_interpreter_not_duplicated(self):
        os.makedirs(os.path.join(self.dir, ".claude"))
        cmd = 'python3 "$CLAUDE_PROJECT_DIR/Tools/claude_read_guard.py"'
        own = {"hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": cmd}]}]}}
        with open(os.path.join(self.dir, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump(own, f)
        install(self.dir)
        commands = [h["command"] for g in settings(self.dir)["hooks"]["PreToolUse"] for h in g["hooks"]
                    if "claude_read_guard" in h["command"]]
        self.assertEqual(commands, [cmd])

    def test_rerun_retires_files_dropped_from_the_kit(self):
        self.assertEqual(install(self.dir).returncode, 0)
        old = os.path.join(self.dir, "Tools", "claude_old_hook.py")
        with open(old, "w", encoding="utf-8", newline="\n") as f:
            f.write("print()\n")
        manifest = os.path.join(self.dir, ".claude", "rulekit", "manifest.json")
        with open(manifest, encoding="utf-8") as f:
            m = json.load(f)
        m["files"]["Tools/claude_old_hook.py"] = hashlib.sha256(b"print()\n").hexdigest()
        with open(manifest, "w", encoding="utf-8") as f:
            json.dump(m, f)
        s = settings(self.dir)
        s["hooks"]["UserPromptSubmit"][0]["hooks"].append(
            {"type": "command", "command": 'python "$CLAUDE_PROJECT_DIR/Tools/claude_old_hook.py"'})
        with open(os.path.join(self.dir, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump(s, f)
        r = install(self.dir)
        self.assertIn("no longer part of the kit", r.stdout)
        self.assertFalse(os.path.exists(old))
        self.assertNotIn("claude_old_hook", json.dumps(settings(self.dir)))

    def test_invalid_settings_aborts_without_writing(self):
        os.makedirs(os.path.join(self.dir, ".claude"))
        with open(os.path.join(self.dir, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            f.write("{ // comment\n}")
        r = install(self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "CLAUDE.md")))

    def test_user_merge_writes_only_into_given_home(self):
        r = install(self.dir, "--user")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, ".claude", "settings.json")))
        self.assertIn("promptCacheTtl", settings(self.dir))  # home == target in this test


if __name__ == "__main__":
    unittest.main()
