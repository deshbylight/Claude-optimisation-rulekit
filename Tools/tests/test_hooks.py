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


class StatusLineTest(TempDirCase):
    SCRIPT = "ctx_usage.py"

    def status(self, lines) -> str:
        return run_hook(self.SCRIPT, {"transcript_path": self.transcript(lines)}).stdout.strip()

    def test_shows_last_main_turn(self):
        self.assertEqual(self.status([assistant_line(1, 10_000), assistant_line(2, 50_000)]),
                         "ctx 50.0k/250k (20%)")

    def test_compaction_resets_to_post_tokens(self):
        boundary = compact({"type": "system", "subtype": "compact_boundary", "isSidechain": False,
                            "compactMetadata": {"trigger": "manual", "preTokens": 200_000, "postTokens": 12_000}})
        self.assertEqual(self.status([assistant_line(1, 200_000), boundary]), "ctx 12.0k/250k (4%)")
        self.assertEqual(self.status([assistant_line(1, 200_000), boundary, assistant_line(2, 30_000)]),
                         "ctx 30.0k/250k (12%)")


def tool_use(n: int, name: str, **tool_input) -> str:
    return assistant_line(n, 20_000, [{"type": "tool_use", "id": f"toolu_{n}", "name": name, "input": tool_input}])


def tool_result(n: int, error: bool = False) -> str:
    return compact({"parentUuid": None, "isSidechain": False, "type": "user",
                    "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"toolu_{n}",
                                                             "content": "ok", "is_error": error}]}})


class VerifyGateTest(TempDirCase):
    SCRIPT = "claude_verify_gate.py"
    ENV = {"RULEKIT_VERIFY_RE": r"make\ test"}

    def stop(self, lines, env=None):
        payload = {"session_id": str(uuid.uuid4()), "transcript_path": self.transcript(lines)}
        return run_hook(self.SCRIPT, payload, self.ENV if env is None else env)

    def test_blocks_edit_without_test(self):
        r = self.stop([tool_use(1, "Edit", file_path="src/app.py", old_string="a", new_string="b")])
        self.assertEqual(json.loads(r.stdout)["decision"], "block")
        self.assertIn("app.py", r.stdout)

    def test_passes_after_successful_test(self):
        lines = [tool_use(1, "Edit", file_path="src/app.py"), tool_use(2, "Bash", command="make test"), tool_result(2)]
        self.assertEqual(self.stop(lines).stdout, "")

    def test_failed_test_does_not_count(self):
        lines = [tool_use(1, "Edit", file_path="src/app.py"), tool_use(2, "Bash", command="make test"),
                 tool_result(2, error=True)]
        self.assertIn("block", self.stop(lines).stdout)

    def test_docs_edit_and_unset_regex_pass(self):
        self.assertEqual(self.stop([tool_use(1, "Edit", file_path="README.md")]).stdout, "")
        self.assertEqual(self.stop([tool_use(1, "Edit", file_path="src/app.py")], env={}).stdout, "")


class ShellGuardTest(TempDirCase):
    SCRIPT = "claude_shell_guard.py"

    def run_cmd(self, command: str):
        os.makedirs(os.path.join(self.dir, ".claude", "rulekit"), exist_ok=True)
        self.write(os.path.join(".claude", "rulekit", "shell-routes.json"), json.dumps(
            {"routes": [{"match": r"\bmake\s+build\b", "unless": "--quiet", "say": "run scripts/build.py"}]}))
        return run_hook(self.SCRIPT, {"tool_name": "Bash", "tool_input": {"command": command}},
                        {"CLAUDE_PROJECT_DIR": self.dir})

    def test_route_blocks(self):
        r = self.run_cmd("make build")
        self.assertEqual(r.returncode, 2)
        self.assertIn("scripts/build.py", r.stderr)

    def test_unless_bypass_and_heredoc_pass(self):
        self.assertEqual(self.run_cmd("make build --quiet").returncode, 0)
        self.assertEqual(self.run_cmd("RULEKIT_RAW=1 make build").returncode, 0)
        self.assertEqual(self.run_cmd("cat > n.md <<'EOF'\nmake build\nEOF").returncode, 0)


class LanguageGuardTest(TempDirCase):
    SCRIPT = "claude_language_guard.py"
    WORD = "".join(map(chr, (0x442, 0x435, 0x441, 0x442)))  # a Cyrillic word, built so this file stays ASCII

    def edit(self, path: str, old: str, new: str, env=None):
        return run_hook(self.SCRIPT, {"tool_name": "Edit", "tool_input": {
            "file_path": path, "old_string": old, "new_string": new}}, env)

    def test_added_foreign_line_blocked(self):
        r = self.edit("src/app.py", "x = 1", f"x = 1  # {self.WORD}")
        self.assertEqual(r.returncode, 2)
        self.assertIn("[LANGUAGE-GUARD]", r.stderr)

    def test_translation_code_span_and_locale_pass(self):
        self.assertEqual(self.edit("src/app.py", f"# {self.WORD}", "# test").returncode, 0)
        self.assertEqual(self.edit("README.md", "", f"Use `{self.WORD}` here.").returncode, 0)
        self.assertEqual(self.edit("app/locales/ru.json", "", self.WORD).returncode, 0)
        self.assertEqual(self.edit("src/app.py", "", self.WORD, {"RULEKIT_FILE_LANG_GUARD": "off"}).returncode, 0)


class CommitReminderTest(TempDirCase):
    SCRIPT = "claude_commit_reminder.py"

    def commit(self, subject: str, name: str) -> str:
        if not os.path.isdir(os.path.join(self.dir, ".git")):
            subprocess.run(["git", "init", "-q", self.dir], check=True)
        self.write(name, "x = 1\n")
        git = ["git", "-C", self.dir, "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run(git + ["add", name], check=True)
        subprocess.run(git + ["commit", "-q", "-m", subject], check=True)
        r = run_hook(self.SCRIPT, {"tool_name": "Bash", "cwd": self.dir,
                                   "tool_input": {"command": f'git commit -m "{subject}"'}})
        return r.stdout

    def test_fix_commit_asks_for_rule_gap_check(self):
        self.assertIn("rule-authoring", self.commit("fix: off-by-one in pager", "a.py"))

    def test_code_commit_asks_for_knowledge(self):
        self.assertIn("system entry", self.commit("feat: pager", "a.py"))

    def test_docs_commit_silent(self):
        self.assertEqual(self.commit("docs: readme", "notes.md"), "")


if __name__ == "__main__":
    unittest.main()
