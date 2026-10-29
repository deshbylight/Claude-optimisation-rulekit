#!/usr/bin/env python3
"""Cheap look-back into an old Claude Code chat without loading it into the new one.

Usage:
    python Tools/claude_session_grep.py <session-id-or-prefix|path.jsonl> --prompts
    python Tools/claude_session_grep.py <session> "regex" [--max 20] [--width 300]

--prompts      list the user's requests in that chat (what was worked on, in order)
regex          search user/assistant text, tool inputs (commands, file paths) and tool results;
               prints `#entry role: snippet` around each match.
Used by the `handoff` skill; transcripts live in ~/.claude/projects/<project>/<session>.jsonl.
"""
import argparse
import glob
import json
import os
import re
import sys

# Claude Code stores transcripts under the project path with every non-alphanumeric char -> '-'.
PROJECT_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects",
                           re.sub(r"[^A-Za-z0-9]", "-",
                                  os.path.abspath(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))))


def resolve(session: str) -> str:
    if session.endswith(".jsonl") and os.path.isfile(session):
        return session
    hits = glob.glob(os.path.join(PROJECT_DIR, session + "*.jsonl"))
    if len(hits) != 1:
        sys.exit(f"session '{session}': {len(hits)} matches in {PROJECT_DIR}")
    return hits[0]


def pieces(entry):
    """Yield (role, text) for every searchable part of a transcript entry."""
    if entry.get("isSidechain"):
        return
    kind = entry.get("type")
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        yield kind, content
        return
    for part in content or []:
        if not isinstance(part, dict):
            continue
        t = part.get("type")
        if t == "text":
            yield kind, part.get("text", "")
        elif t == "tool_use":
            yield f"tool:{part.get('name')}", json.dumps(part.get("input"), ensure_ascii=False)
        elif t == "tool_result":
            c = part.get("content")
            if isinstance(c, list):
                c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
            yield "result", c if isinstance(c, str) else ""


def is_user_request(entry, text: str) -> bool:
    return (entry.get("type") == "user" and not entry.get("isMeta")
            and not entry.get("isCompactSummary") and not text.lstrip().startswith("<"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session")
    ap.add_argument("pattern", nargs="?")
    ap.add_argument("--prompts", action="store_true")
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--width", type=int, default=300)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if not a.prompts and not a.pattern:
        ap.error("give a regex or --prompts")

    rx = re.compile(a.pattern, re.I) if a.pattern else None
    shown = 0
    with open(resolve(a.session), encoding="utf-8", errors="ignore") as f:
        for n, line in enumerate(f):
            try:
                entry = json.loads(line)
            except ValueError:  # partial line in a live transcript
                continue
            for role, text in pieces(entry):
                if a.prompts:
                    if role == "user" and is_user_request(entry, text):
                        print(f"#{n} " + " ".join(text.split())[:a.width])
                    continue
                m = rx.search(text)
                if not m:
                    continue
                lo = max(0, m.start() - a.width // 2)
                snippet = text[lo:lo + a.width].replace("\n", " ")
                print(f"#{n} {role}: {snippet}")
                shown += 1
                if shown >= a.max:
                    return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
