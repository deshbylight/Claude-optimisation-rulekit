#!/usr/bin/env python3
"""UserPromptSubmit hook: nudge very long chats toward a fresh chat (skill `handoff`).

Every model call re-sends the whole context, so in a very long chat (hundreds of calls, several
compactions) a fresh chat with a small handoff file is cheaper than continuing. Measured on
real sessions: the ~25% of sessions with >= 200 calls consumed ~75% of input tokens.

Counts main-chain model calls (unique assistant message ids, as Tools/ctx_stats.py does) and
compactions (`compact_boundary`) in the current transcript with one byte-regex pass (~40 ms on a
40 MB transcript). Injects a note when calls >= RULEKIT_LONG_SESSION_CALLS (default 200) or
compactions >= RULEKIT_LONG_SESSION_COMPACTS (default 2); repeats only every REPEAT_EVERY_CALLS more
calls or after a new compaction (state in the OS temp dir, per session).

Task boundary: a chat that runs several tasks back to back pays the whole earlier context on
every call of each later task. The note also fires on the first prompt after a new `git commit`
(non --dry-run, attempts counted)
when the last main-chain request carried >= RULEKIT_LONG_SESSION_CTX (default 100000) context tokens
(input + cache write + cache read).
Skips slash commands and prompts starting with '+' (user keeps the chat).
Disable: env RULEKIT_LONG_SESSION_OFF=1.

Wired in .claude/settings.json -> hooks.UserPromptSubmit.
"""
import json
import os
import re
import sys
import tempfile

CALLS_THRESHOLD = int(os.environ.get("RULEKIT_LONG_SESSION_CALLS", "200"))
COMPACTS_THRESHOLD = int(os.environ.get("RULEKIT_LONG_SESSION_COMPACTS", "2"))
CTX_THRESHOLD = int(os.environ.get("RULEKIT_LONG_SESSION_CTX", "100000"))
REPEAT_EVERY_CALLS = 100
NUDGE_OFF = bool(os.environ.get("RULEKIT_LONG_SESSION_OFF"))
STATE_DIR = os.path.join(tempfile.gettempdir(), "rulekit_long_session")
MSG_ID_RE = re.compile(rb'"isSidechain":false,"message":\{"model":"[^"]*","id":"(msg_[^"]+)"')
COMPACT_MARK = b'"subtype":"compact_boundary"'
MAIN_CHAIN_MARK = b'"isSidechain":false'
COMMIT_MARK = b"git commit"
COMMIT_RE = re.compile(r"\bgit\s+commit\b")
USAGE_RE = re.compile(rb'"usage":\{"input_tokens":(\d+),"cache_creation_input_tokens":(\d+),'
                      rb'"cache_read_input_tokens":(\d+)')


def _commit_ids(data: bytes) -> set:
    """Ids of main-chain Bash calls that run `git commit` without --dry-run."""
    ids = set()
    for line in data.splitlines():
        if COMMIT_MARK not in line or MAIN_CHAIN_MARK not in line:
            continue
        try:
            content = (json.loads(line).get("message") or {}).get("content")
        except ValueError:  # truncated last line while the transcript is being written
            continue
        for block in content if isinstance(content, list) else ():
            if block.get("type") != "tool_use" or block.get("name") != "Bash":
                continue
            command = str((block.get("input") or {}).get("command", ""))
            if COMMIT_RE.search(command) and "--dry-run" not in command:
                ids.add(block.get("id"))
    return ids


def _last_context(data: bytes) -> int:
    """Context tokens of the last main-chain request (0 when none is recorded yet)."""
    for line in reversed(data.splitlines()):
        if MAIN_CHAIN_MARK in line:
            m = USAGE_RE.search(line)
            if m:
                return sum(int(g) for g in m.groups())
    return 0


def session_counts(transcript_path: str):
    """Returns (model_calls, compactions, task_commits, last_context) of the main chain, or None."""
    try:
        with open(transcript_path, "rb") as f:
            data = f.read()
    except OSError:  # missing transcript (fresh session): stay silent
        return None
    return (len(set(MSG_ID_RE.findall(data))), data.count(COMPACT_MARK),
            len(_commit_ids(data)), _last_context(data))


def _state_path(session_id: str) -> str:
    return os.path.join(STATE_DIR, re.sub(r"[^\w-]", "_", session_id or "unknown") + ".json")


def should_nudge(session_id: str, calls: int, compacts: int, commits: int = 0, context: int = 0) -> str:
    """Nudge reason: "length" (over a call/compaction threshold, last nudge REPEAT_EVERY_CALLS calls or
    a compaction ago), "task" (a new task commit since the last nudge at >= CTX_THRESHOLD context), or ""."""
    long_chat = calls >= CALLS_THRESHOLD or compacts >= COMPACTS_THRESHOLD
    big_context = context >= CTX_THRESHOLD
    if not long_chat and not (big_context and commits):
        return ""
    path = _state_path(session_id)
    try:
        with open(path, encoding="utf-8") as f:
            last = json.load(f)
    except (OSError, ValueError):  # first nudge for this session / corrupt state
        last = None
    last = last or {}
    if long_chat and (not last or calls - last.get("calls", 0) >= REPEAT_EVERY_CALLS
                      or compacts > last.get("compacts", 0)):
        reason = "length"
    elif big_context and commits > last.get("commits", 0):
        reason = "task"
    else:
        return ""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"calls": calls, "compacts": compacts, "commits": commits}, f)
    except OSError:  # unwritable temp: nudge anyway, at worst it repeats
        pass
    return reason


def main() -> int:
    if NUDGE_OFF:
        return 0
    try:
        data = json.load(sys.stdin)
    except ValueError:  # malformed hook payload: never block the user's prompt
        return 0
    prompt = (data.get("prompt") or "").strip()
    if prompt.startswith(("/", "+")):
        return 0
    counts = session_counts(data.get("transcript_path") or "")
    if not counts:
        return 0
    calls, compacts, commits, context = counts
    session_id = data.get("session_id") or ""
    reason = should_nudge(session_id, calls, compacts, commits, context)
    if not reason:
        return 0
    if reason == "task":
        state = (f"A task was just committed and the context is already ~{context // 1000}k tokens; every "
                 "call re-sends it, so the next task costs several times more here than in a fresh chat.")
    else:
        state = (f"This chat already has {calls} model calls and {compacts} compactions; every "
                 "call re-sends the whole context, so continuing here costs several times more than a fresh chat.")
    note = (
        f"[LONG-SESSION] {state} "
        "Handle this prompt, but if it starts a new step or topic, first recommend to the user "
        "(one line, in the chat language) moving on via skill `handoff` "
        f"(session_id={session_id or '?'}, transcript={data.get('transcript_path', '?')}). "
        "Do not hand off in the middle of an edit/build/commit. A '+' prefix on the user's prompt "
        "means: stay in this chat."
    )
    json.dump({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                      "additionalContext": note}},
              sys.stdout)  # ASCII-escaped: safe under any console code page
    return 0


if __name__ == "__main__":
    sys.exit(main())
