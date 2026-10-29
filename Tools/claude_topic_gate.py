#!/usr/bin/env python3
"""UserPromptSubmit hook: before a new request touches files in an already-big chat,
make the model decide whether it belongs here or should move to a fresh chat (skill `handoff`).

No LLM call of its own -- it only injects a short instruction, and only when it matters:
  * chat context >= RULEKIT_TOPIC_GATE_KTOK (default 100k tokens, from the last usage record);
  * prompt is not a slash command, shorter than MIN_PROMPT_CHARS (a go-ahead like "ok", "continue");
  * prompt does not start with '+' (user forces "same chat").
Disable entirely: env RULEKIT_TOPIC_GATE_OFF=1.

Wired in .claude/settings.json -> hooks.UserPromptSubmit.
"""
import json
import os
import sys

TAIL_BYTES = 4 * 1024 * 1024
MIN_PROMPT_CHARS = 40
THRESHOLD_TOKENS = int(os.environ.get("RULEKIT_TOPIC_GATE_KTOK", "100")) * 1000
GATE_OFF = bool(os.environ.get("RULEKIT_TOPIC_GATE_OFF"))


def last_context_tokens(transcript_path: str) -> int:
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as f:
            f.seek(max(0, size - TAIL_BYTES))
            lines = f.read().decode("utf-8", errors="ignore").splitlines()
    except OSError:  # unreadable transcript: gate stays silent, never blocks the prompt
        return 0
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:  # tail starts mid-line / partial write
            continue
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        usage = (entry.get("message") or {}).get("usage") or {}
        total = sum(usage.get(k) or 0 for k in
                    ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        if total:
            return total
    return 0


def main() -> int:
    if GATE_OFF:
        return 0
    try:
        data = json.load(sys.stdin)
    except ValueError:  # malformed hook payload: never block the user's prompt
        return 0
    prompt = (data.get("prompt") or "").strip()
    if not prompt or prompt.startswith(("/", "+")) or len(prompt) < MIN_PROMPT_CHARS:
        return 0

    transcript = data.get("transcript_path") or ""
    ctx = last_context_tokens(transcript)
    if ctx < THRESHOLD_TOKENS:
        return 0

    note = (
        f"[TOPIC-GATE] This chat's context is ≈{ctx // 1000}k tokens. Before ANY tool call decide: "
        "does the new request belong to the chat's current task (same subsystem/bug/feature or a direct continuation)? "
        "Yes → work as usual, do not mention the gate. "
        "No → read and run nothing; run skill `handoff` "
        f"(session_id={data.get('session_id', '?')}, transcript={transcript}). "
        "Unsure → one question to the user, no tools. "
        "A '+' prefix on the user's prompt = stay in this chat."
    )
    json.dump({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                      "additionalContext": note}},
              sys.stdout)  # ASCII-escaped: safe under any console code page
    return 0


if __name__ == "__main__":
    sys.exit(main())
