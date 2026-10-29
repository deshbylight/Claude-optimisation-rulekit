"""Hook tests: run each hook script with a synthetic payload and check its exit code and output.

    python -m unittest discover -s Tools/tests -v

No Claude Code needed. Transcripts are written in the compact JSON shape Claude Code uses
(no spaces after separators, key order as below): claude_session_length.py matches raw bytes.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid

TESTS = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(TESTS)
# The read guard exempts scratchpad/temp paths, so fixtures live inside the repo, not in the OS temp dir.
EXEMPT_PARTS = ("/scratchpad/", "/temp/", "/tmp/")
REPO_IN_TEMP = any(p in TESTS.replace("\\", "/").lower() + "/" for p in EXEMPT_PARTS)


def run_hook(script: str, payload: dict, env: dict = None) -> subprocess.CompletedProcess:
    full_env = {k: v for k, v in os.environ.items() if not k.startswith("RULEKIT_")}
    full_env.update(env or {})
    return subprocess.run([sys.executable, os.path.join(TOOLS, script)], input=json.dumps(payload),
                          capture_output=True, text=True, encoding="utf-8", env=full_env, timeout=30)


def compact(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"))


def assistant_line(n: int, ctx: int, content=None) -> str:
    return compact({"parentUuid": None, "isSidechain": False,
                    "message": {"model": "test-model", "id": f"msg_{n:04d}", "role": "assistant",
                                "content": content or [{"type": "text", "text": "ok"}],
                                "usage": {"input_tokens": 1, "cache_creation_input_tokens": 0,
                                          "cache_read_input_tokens": ctx - 1, "output_tokens": 5}},
                    "type": "assistant", "timestamp": "2026-01-01T00:00:00Z"})


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=TESTS, prefix="_work_")
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name: str, text: str) -> str:
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return path

    def transcript(self, lines) -> str:
        return self.write(f"{uuid.uuid4()}.jsonl", "\n".join(lines) + "\n")


@unittest.skipIf(REPO_IN_TEMP, "repo sits under a temp/scratchpad path, which the read guard exempts")
class ReadGuardTest(TempDirCase):
    SCRIPT = "claude_read_guard.py"

    def setUp(self):
        super().setUp()
        self.big = self.write("big.py", "".join(f"x{i} = {i}\n" for i in range(400)))
        self.small = self.write("small.py", "x = 1\n")
        self.env = {"CLAUDE_PROJECT_DIR": self.dir}

    def read(self, **tool_input):
        return run_hook(self.SCRIPT, {"tool_name": "Read", "tool_input": tool_input, "cwd": self.dir}, self.env)

    def bash(self, command: str):
        return run_hook(self.SCRIPT, {"tool_name": "Bash", "tool_input": {"command": command},
                                      "cwd": self.dir}, self.env)

    def test_whole_read_of_large_file_blocked(self):
        r = self.read(file_path=self.big)
        self.assertEqual(r.returncode, 2)
        self.assertIn("offset", r.stderr)

    def test_read_with_limit_passes(self):
        self.assertEqual(self.read(file_path=self.big, offset=1, limit=80).returncode, 0)

    def test_small_file_passes(self):
        self.assertEqual(self.read(file_path=self.small).returncode, 0)

    def test_shell_cat_of_large_file_blocked(self):
        self.assertEqual(self.bash("cat big.py").returncode, 2)

    def test_shell_cat_piped_passes(self):
        self.assertEqual(self.bash("cat big.py | grep x39").returncode, 0)

    def test_shell_marker_bypasses(self):
        self.assertEqual(self.bash("RULEKIT_FULL_READ=1 cat big.py").returncode, 0)

    def test_shell_read_of_temp_path_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "big.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write("x = 1\n" * 400)
            self.assertEqual(self.bash(f"cat '{path}'").returncode, 0)

    def test_write_over_large_file_blocked(self):
        r = run_hook(self.SCRIPT, {"tool_name": "Write", "cwd": self.dir,
                                   "tool_input": {"file_path": self.big, "content": "x = 0\n"}}, self.env)
        self.assertEqual(r.returncode, 2)

    def test_malformed_payload_fails_open(self):
        r = subprocess.run([sys.executable, os.path.join(TOOLS, self.SCRIPT)], input="not json",
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0)


class TopicGateTest(TempDirCase):
    SCRIPT = "claude_topic_gate.py"
    PROMPT = "Please add a retry counter to the upload client and cover it with a test."

    def payload(self, ctx: int, prompt: str = PROMPT) -> dict:
        return {"prompt": prompt, "session_id": "s1", "transcript_path": self.transcript([assistant_line(1, ctx)])}

    def test_fires_above_threshold(self):
        r = run_hook(self.SCRIPT, self.payload(150_000))
        self.assertEqual(r.returncode, 0)
        self.assertIn("[TOPIC-GATE]", r.stdout)

    def test_silent_below_threshold(self):
        self.assertNotIn("[TOPIC-GATE]", run_hook(self.SCRIPT, self.payload(50_000)).stdout)

    def test_plus_prefix_stays(self):
        self.assertNotIn("[TOPIC-GATE]", run_hook(self.SCRIPT, self.payload(150_000, "+" + self.PROMPT)).stdout)

    def test_threshold_knob(self):
        r = run_hook(self.SCRIPT, self.payload(50_000), {"RULEKIT_TOPIC_GATE_KTOK": "40"})
        self.assertIn("[TOPIC-GATE]", r.stdout)

    def test_off_switch(self):
        r = run_hook(self.SCRIPT, self.payload(150_000), {"RULEKIT_TOPIC_GATE_OFF": "1"})
        self.assertEqual(r.stdout, "")


class SessionLengthTest(TempDirCase):
    SCRIPT = "claude_session_length.py"

    def payload(self, lines) -> dict:
        return {"prompt": "next step", "session_id": str(uuid.uuid4()), "transcript_path": self.transcript(lines)}

    def test_fires_after_many_calls(self):
        lines = [assistant_line(i, 20_000) for i in range(12)]
        r = run_hook(self.SCRIPT, self.payload(lines), {"RULEKIT_LONG_SESSION_CALLS": "10"})
        self.assertIn("[LONG-SESSION]", r.stdout)

    def test_silent_for_short_session(self):
        lines = [assistant_line(i, 20_000) for i in range(3)]
        self.assertNotIn("[LONG-SESSION]", run_hook(self.SCRIPT, self.payload(lines)).stdout)

    def test_fires_after_commit_at_large_context(self):
        commit = [{"type": "tool_use", "id": "toolu_1", "name": "Bash",
                   "input": {"command": "git commit -m \"feat: x\""}}]
        lines = [assistant_line(1, 120_000, commit), assistant_line(2, 120_000)]
        self.assertIn("[LONG-SESSION]", run_hook(self.SCRIPT, self.payload(lines)).stdout)

    def test_off_switch(self):
        lines = [assistant_line(i, 20_000) for i in range(12)]
        r = run_hook(self.SCRIPT, self.payload(lines),
                     {"RULEKIT_LONG_SESSION_CALLS": "10", "RULEKIT_LONG_SESSION_OFF": "1"})
        self.assertEqual(r.stdout, "")


class ReplyLanguageTest(unittest.TestCase):
    SCRIPT = "claude_reply_language.py"

    def test_silent_when_unset(self):
        self.assertEqual(run_hook(self.SCRIPT, {"prompt": "hi"}).stdout.strip(), "")

    def test_names_language(self):
        r = run_hook(self.SCRIPT, {"prompt": "hi"}, {"RULEKIT_REPLY_LANG": "German"})
        self.assertIn("German", r.stdout)


if __name__ == "__main__":
    unittest.main()
