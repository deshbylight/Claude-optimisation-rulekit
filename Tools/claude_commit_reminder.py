#!/usr/bin/env python3
"""PostToolUse hook (Bash): after a commit, remind the model to capture what the change taught.

The rule-gap check (`RR/rule-authoring.md`) and the per-system docs (`RR/architecture.md`) depend on
the model remembering a CLAUDE.md line at the end of a long task; it often does not. Two reminders:
  * fix commit (subject `fix:`/`fix(scope):` or naming fix/bug/regression/crash) -> rule-gap check;
  * other commit touching source files (RULEKIT_SOURCE_RE; `docs:` subjects excluded) -> knowledge
    capture: system entry, ADR, failure log, only if the change taught something the code does not show.
Fires only when the command ran `git commit` (not `--dry-run`) and HEAD is younger than 5 minutes.
Output: hookSpecificOutput.additionalContext. Never blocks; silent on any error.
Disable: env RULEKIT_COMMIT_REMINDER_OFF=1.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time

COMMIT_RE = re.compile(r"(?:^|[;&|\n(])\s*git\s+(?:-C\s+(\"[^\"]+\"|'[^']+'|\S+)\s+)?commit\b")
FIX_SUBJECT_RE = re.compile(r"^fix(\([^)]*\))?!?:")
FIX_WORDS_RE = re.compile(r"\b(fix|fixes|fixed|bugs?|regression|crash(es)?)\b", re.I)
CONVENTIONAL_RE = re.compile(r"^[a-z]+(\([^)]*\))?!?:")
DOC_SUBJECT_RE = re.compile(r"^(docs|knowledge)(\([^)]*\))?!?:")
DEFAULT_SOURCE_RE = r"\.(c|cc|cpp|cxx|h|hh|hpp|inl|cs|go|rs|java|kt|kts|scala|swift|m|mm|py|js|jsx|mjs|ts|tsx|vue|svelte|rb|php|lua|dart|sql)$"
MAX_AGE_S = 300


def git(cwd: str, *args: str) -> str:
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=10)
    return r.stdout if r.returncode == 0 else ""


def classify(subject: str, files: list, source_re) -> str:
    if FIX_SUBJECT_RE.search(subject) or (not CONVENTIONAL_RE.search(subject) and FIX_WORDS_RE.search(subject)):
        return "fix"
    if not DOC_SUBJECT_RE.search(subject) and any(source_re.search(f) for f in files):
        return "code"
    return ""


def reminder(kind: str, sha: str) -> str:
    if kind == "fix":
        return (f"[COMMIT-REMINDER] {sha} fixes a defect. Before the final report, Read RR/rule-authoring.md "
                "and decide: is the root cause a reusable class of bug that no loaded rule covers? Then add or "
                "propose the rule, or write 'no rule gap: <why>' in one report line.")
    return (f"[COMMIT-REMINDER] {sha} changes source. If the change taught something the code does not show "
            "(an invariant, a trap, a decision with rejected alternatives), update the system entry, an ADR or "
            "the failure log in this task (RR/architecture.md, per-system docs); otherwise nothing to do. "
            "One report line either way.")


def main() -> int:
    if os.environ.get("RULEKIT_COMMIT_REMINDER_OFF"):
        return 0
    try:
        ev = json.load(sys.stdin)
        command = (ev.get("tool_input") or {}).get("command") or ""
        m = COMMIT_RE.search(command)
        if not m or "--dry-run" in command:
            return 0
        cwd = ev.get("cwd") or os.getcwd()
        if m.group(1):
            cwd = os.path.join(cwd, shlex.split(m.group(1))[0])
        head = git(cwd, "log", "-1", "--format=%ct%x00%h%x00%s").strip().split("\x00")
        if len(head) != 3 or time.time() - int(head[0]) > MAX_AGE_S:
            return 0
        files = git(cwd, "show", "--name-only", "--format=", "HEAD").split()
        try:
            source_re = re.compile(os.environ.get("RULEKIT_SOURCE_RE") or DEFAULT_SOURCE_RE, re.I)
        except re.error:
            source_re = re.compile(DEFAULT_SOURCE_RE, re.I)
        kind = classify(head[2], files, source_re)
        if kind:
            json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                              "additionalContext": reminder(kind, head[1])}}, sys.stdout)
    except Exception:  # noqa: BLE001 - a reminder must never fail a tool call
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
