#!/usr/bin/env python3
"""Statusline: current context size from the session transcript, zero chat tokens.

Claude Code pipes statusline JSON (with ``transcript_path``) to stdin; the script reads the
last main-chain assistant ``usage`` record and prints one line, e.g. ``ctx 20.5k/250k (8%)``.
Context = input_tokens + cache_creation_input_tokens + cache_read_input_tokens. The value
lags by one turn: the prompt being typed is not counted yet. Right after a compaction (no
assistant turn since) the size is the ``postTokens`` of the ``compact_boundary`` record.

Wired in .claude/settings.json -> statusLine. Manual use:
    python Tools/ctx_usage.py --transcript <session>.jsonl
"""
import argparse
import json
import os
import sys
from typing import Optional

# Context window shown as the denominator; set it to your model's autoCompactWindow.
DEFAULT_WINDOW = 250_000
# Tail read size; doubled until a usage record is found or the file start is reached.
TAIL_CHUNK_BYTES = 256 * 1024


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--transcript", help="Transcript .jsonl path (default: from stdin JSON).")
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW,
                        help=f"Context window in tokens (default {DEFAULT_WINDOW}).")
    return parser.parse_args()


def _context_tokens(line: str) -> Optional[int]:
    """Returns the context size of one transcript line, or None if it has no main usage."""
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        # The first line of a tail chunk is usually cut mid-record; it is not data.
        return None
    if entry.get("isSidechain"):
        return None
    if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
        # Newer than every assistant usage before it: the context is the compacted size.
        return (entry.get("compactMetadata") or {}).get("postTokens")
    if entry.get("type") != "assistant":
        return None
    usage = (entry.get("message") or {}).get("usage")
    if not usage:
        return None
    return (usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0))


def last_context_tokens(path: str) -> Optional[int]:
    """Scans the transcript from the end for the latest assistant usage record.

    Args:
        path: Session transcript .jsonl.

    Returns:
        Token count of the latest main-chain assistant turn, or None if there is none yet.
    """
    size = os.path.getsize(path)
    chunk = TAIL_CHUNK_BYTES
    with open(path, "rb") as stream:
        while True:
            start = max(0, size - chunk)
            stream.seek(start)
            lines = stream.read().decode("utf-8", errors="replace").splitlines()
            for line in reversed(lines):
                tokens = _context_tokens(line)
                if tokens is not None:
                    return tokens
            if start == 0:
                return None
            chunk *= 2


def main() -> int:
    args = _parse_args()
    if args.window <= 0:
        print("ctx: --window must be positive", file=sys.stderr)
        return 2
    path = args.transcript
    if not path:
        try:
            path = json.load(sys.stdin).get("transcript_path")
        except json.JSONDecodeError as error:
            print(f"ctx: invalid statusline JSON on stdin ({error})")
            return 1
    if not path or not os.path.isfile(path):
        print(f"ctx: transcript not found ({path})")
        return 1
    tokens = last_context_tokens(path)
    if tokens is None:
        print("ctx: no assistant turn yet")
        return 0
    print(f"ctx {tokens / 1000:.1f}k/{args.window // 1000}k ({tokens * 100 // args.window}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
