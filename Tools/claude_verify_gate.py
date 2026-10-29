#!/usr/bin/env python3
"""Stop hook: source edited after the last successful build/test -> ask for one, or an explicit "not built".

CLAUDE.md says "green build = built, unverified", but that line lives only in prose: a turn could end
with "done" after a source edit and no build or test at all. This gate reads the session transcript
in order: Edit/Write/MultiEdit/NotebookEdit calls on files matching RULEKIT_SOURCE_RE vs Bash/PowerShell
calls matching RULEKIT_VERIFY_RE whose tool_result is not an error. If an edit comes after the last
successful verify command, the stop is blocked once per last edit, with a reason telling the model to
run the check, or to say "not built" plus the blocker, or that the task is still in progress.

Not seen: edits made by subagents (separate transcript) or by shell commands (sed, heredocs).
Config (`.claude/settings.json` -> env):
  RULEKIT_SOURCE_RE   regex on the edited path (forward slashes); default: common source extensions
  RULEKIT_VERIFY_RE   regex on shell commands that count as build/test; empty = gate off
  RULEKIT_VERIFY_GATE_OFF=1 disables the gate.
Fails open (exit 0) on malformed input or an unreadable transcript.

    python Tools/claude_verify_gate.py --transcript <path.jsonl>   # dry check, prints the verdict
"""
import argparse
import json
import os
import re
import sys
import tempfile

DEFAULT_SOURCE_RE = r"\.(c|cc|cpp|cxx|h|hh|hpp|inl|cs|go|rs|java|kt|kts|scala|swift|m|mm|py|js|jsx|mjs|ts|tsx|vue|svelte|rb|php|lua|dart|sql)$"
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
STATE_DIR = os.path.join(tempfile.gettempdir(), "rulekit_verify_gate")
LISTED_MAX = 5


def compile_env(name: str, default: str = ""):
    pattern = os.environ.get(name, default).strip()
    try:
        return re.compile(pattern, re.I) if pattern else None
    except re.error:  # a broken regex in settings must not block every stop
        return None


def scan(path: str, source_re, verify_re):
    """(edited paths since the last good verify, tool_use id of the last such edit) or None."""
    try:
        with open(path, "rb") as f:
            lines = f.readlines()
    except OSError:
        return None
    events, verify_ids, good = [], set(), set()
    for raw in lines:
        if b'"isSidechain":false' not in raw or (b'"tool_use"' not in raw and b'"tool_result"' not in raw):
            continue
        try:
            content = (json.loads(raw).get("message") or {}).get("content")
        except ValueError:  # partially written last line
            continue
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                name, inp = block.get("name"), block.get("input") or {}
                if name in EDIT_TOOLS:
                    fp = (inp.get("file_path") or inp.get("notebook_path") or "").replace("\\", "/")
                    if source_re.search(fp):
                        events.append(("edit", block.get("id"), fp))
                elif name in SHELL_TOOLS and verify_re.search(inp.get("command") or ""):
                    verify_ids.add(block.get("id"))
                    events.append(("verify", block.get("id"), ""))
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in verify_ids:
                if not block.get("is_error"):
                    good.add(block["tool_use_id"])
    pending, last_id = [], None
    for kind, use_id, fp in events:
        if kind == "verify" and use_id in good:
            pending, last_id = [], None
        elif kind == "edit":
            if fp not in pending:
                pending.append(fp)
            last_id = use_id
    return pending, last_id


def already_gated(session_id: str, last_id: str) -> bool:
    """True if this exact last edit was already gated; otherwise records it."""
    path = os.path.join(STATE_DIR, re.sub(r"[^\w-]", "_", session_id or "unknown") + ".txt")
    try:
        with open(path, encoding="utf-8") as f:
            if f.read().strip() == last_id:
                return True
    except OSError:
        pass
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(last_id)
    except OSError:  # unwritable temp: gate anyway; stop_hook_active still prevents a loop
        pass
    return False


def reason(pending) -> str:
    names = [os.path.basename(p) for p in pending]
    listed = ", ".join(names[:LISTED_MAX]) + (f" (+{len(names) - LISTED_MAX})" if len(names) > LISTED_MAX else "")
    return (f"[VERIFY-GATE] {len(names)} source file(s) edited after the last successful build/test in "
            f"this session: {listed}. If the task is done, run the build/test command from CLAUDE.md now "
            "and report the result (green = 'built, unverified' until a runtime check). If it cannot run, "
            "state 'not built' and the blocker in one line. If the task is still in progress or waits for "
            "the user, say so in one line and stop. Do not repeat the task report.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--transcript", help="dry check of a transcript; prints the verdict, keeps no state")
    args = ap.parse_args()
    source_re = compile_env("RULEKIT_SOURCE_RE", DEFAULT_SOURCE_RE)
    verify_re = compile_env("RULEKIT_VERIFY_RE")
    if args.transcript:
        if not (source_re and verify_re):
            print("gate off: RULEKIT_VERIFY_RE is empty")
            return 0
        result = scan(args.transcript, source_re, verify_re)
        print(reason(result[0]) if result and result[0] else "pass: no source edits after the last good build/test")
        return 0
    if os.environ.get("RULEKIT_VERIFY_GATE_OFF") or not (source_re and verify_re):
        return 0
    try:
        ev = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(ev, dict) or ev.get("stop_hook_active"):
        return 0
    result = scan(ev.get("transcript_path") or "", source_re, verify_re)
    if result and result[0] and result[1] and not already_gated(ev.get("session_id") or "", result[1]):
        json.dump({"decision": "block", "reason": reason(result[0])}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
