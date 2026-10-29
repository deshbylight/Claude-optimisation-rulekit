#!/usr/bin/env python3
"""Claude Code context-size statistics for this project's session transcripts.

Reads ~/.claude/projects/<project>/*.jsonl (main chain only, subagents excluded) and reports,
per session: model calls, start context (system prompt + tools + CLAUDE.md + memory),
mean / max context, growth per call and manual/auto compactions.
`--breakdown <id-prefix>` splits the live context at the session's peak by source
(tool results per tool, auto-loaded rules = nested_memory, assistant output, ...).

Context per call = input_tokens + cache_read_input_tokens + cache_creation_input_tokens.

Examples:
  python Tools/ctx_stats.py --last 15
  python Tools/ctx_stats.py --since 2026-10-01
  python Tools/ctx_stats.py --breakdown 4b96b54b
"""
import argparse
import glob
import json
import ntpath
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

PROJECT_DIR_NAME = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())))
TRANSCRIPTS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects", PROJECT_DIR_NAME)
MIN_CALLS = 10            # default --min-calls: shorter sessions are skipped in the table
IMAGE_CHARS = 6000        # rough char-equivalent of one image tool result (~1.6k tokens)
# Bookkeeping attachments that are not sent to the model as context.
NON_CONTEXT_ATTACHMENTS = {"prompt_snapshot", "hook_success"}


def _load(path: str):
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:  # partially written last line of a live session
                continue


def _context(usage: dict) -> int:
    return (usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0))


def session_stats(path: str):
    """Returns a dict of per-session context numbers, or None for empty sessions."""
    seen, ctx, date, model, compacts = set(), [], None, None, 0
    for o in _load(path):
        if o.get("isSidechain"):
            continue
        if o.get("type") == "system" and o.get("subtype") == "compact_boundary":
            compacts += 1
        if o.get("type") != "assistant":
            continue
        msg = o.get("message") or {}
        usage = msg.get("usage")
        if not usage or msg.get("id") in seen:
            continue
        seen.add(msg.get("id"))
        c = _context(usage)
        if c:
            date = date or (o.get("timestamp") or "")[:10]
            model = msg.get("model")
            ctx.append(c)
    if not ctx:
        return None
    growth = [b - a for a, b in zip(ctx, ctx[1:]) if b >= a]
    return {"id": os.path.basename(path)[:8], "date": date, "calls": len(ctx), "start": ctx[0],
            "mean": int(statistics.mean(ctx)), "max": max(ctx),
            "growth": int(statistics.mean(growth)) if growth else 0, "compacts": compacts,
            "model": model or "?"}


def breakdown(path: str) -> None:
    """Prints the live-context composition (chars since last compaction) at the peak call."""
    tools, cats, reads, read_n = {}, defaultdict(int), Counter(), Counter()
    best = (0, {}, [], {})
    for o in _load(path):
        if o.get("isSidechain"):
            continue
        kind = o.get("type")
        if kind == "system" and o.get("subtype") == "compact_boundary":
            cats, reads, read_n = defaultdict(int), Counter(), Counter()
        elif kind == "attachment":
            att = o.get("attachment") or {}
            if att.get("type") not in NON_CONTEXT_ATTACHMENTS:
                cats["att:" + str(att.get("type"))] += len(json.dumps(att, ensure_ascii=False))
        elif kind == "assistant":
            msg = o.get("message") or {}
            c = _context(msg.get("usage") or {})
            if c > best[0]:
                best = (c, dict(cats), reads.most_common(6), dict(read_n))
            for x in msg.get("content") or []:
                if x.get("type") == "tool_use":
                    tools[x["id"]] = (x["name"], str((x.get("input") or {}).get("file_path", "")))
                    cats["out:" + x["name"]] += len(json.dumps(x.get("input"), ensure_ascii=False))
                elif x.get("type") == "text":
                    cats["out:text"] += len(x.get("text", ""))
        elif kind == "user":
            content = (o.get("message") or {}).get("content")
            if isinstance(content, str):
                cats["user"] += len(content)
                continue
            for x in content or []:
                if x.get("type") != "tool_result":
                    cats["user"] += len(json.dumps(x, ensure_ascii=False))
                    continue
                name, fp = tools.get(x.get("tool_use_id"), ("?", ""))
                body = x.get("content")
                size = len(json.dumps(body, ensure_ascii=False))
                if isinstance(body, list) and any(isinstance(y, dict) and y.get("type") == "image" for y in body):
                    name, size = "IMAGE", IMAGE_CHARS
                if name.startswith("mcp__"):
                    name = "mcp:" + name.split("__")[1]
                cats["tool:" + name] += size
                if name == "Read":
                    reads[ntpath.basename(fp)] += size
                    read_n[ntpath.basename(fp)] += 1
    peak, live, top_reads, counts = best
    total = sum(live.values()) or 1
    print(f"peak context {peak} tokens; visible live context {total} chars "
          f"(gap to peak = system prompt + hidden thinking)")
    for k, v in sorted(live.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {k:28s} {100 * v / total:5.1f}%  {v:8d} ch")
    if top_reads:
        print("top Reads: " + ", ".join(f"{k} {v // 1000}k x{counts[k]}" for k, v in top_reads))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=TRANSCRIPTS_DIR, help="transcripts directory")
    ap.add_argument("--since", help="only sessions starting on/after YYYY-MM-DD")
    ap.add_argument("--last", type=int, help="only the N most recent sessions")
    ap.add_argument("--min-calls", type=int, default=MIN_CALLS,
                    help=f"skip sessions with fewer model calls (default {MIN_CALLS})")
    ap.add_argument("--breakdown", metavar="ID", help="session id prefix: context composition at peak")
    args = ap.parse_args()
    if not os.path.isdir(args.dir):
        print(f"error: transcripts dir not found: {args.dir}", file=sys.stderr)
        return 1
    files = glob.glob(os.path.join(args.dir, "*.jsonl"))
    if args.breakdown:
        match = [f for f in files if os.path.basename(f).startswith(args.breakdown)]
        if len(match) != 1:
            print(f"error: '{args.breakdown}' matches {len(match)} sessions", file=sys.stderr)
            return 1
        breakdown(match[0])
        return 0
    rows = [s for s in map(session_stats, files) if s and s["calls"] >= args.min_calls]
    if args.since:
        rows = [s for s in rows if s["date"] >= args.since]
    rows.sort(key=lambda s: s["date"])
    if args.last:
        rows = rows[-args.last:]
    if not rows:
        print(f"no sessions with >= {args.min_calls} calls (see --min-calls)")
        return 0
    print("date       id       calls  start   mean    max   +/call cmp model")
    for s in rows:
        print(f"{s['date']} {s['id']} {s['calls']:5d} {s['start']:6d} {s['mean']:6d} {s['max']:7d} "
              f"{s['growth']:6d} {s['compacts']:3d} {s['model']}")
    print(f"avg: start {int(statistics.mean(s['start'] for s in rows))}, "
          f"mean {int(statistics.mean(s['mean'] for s in rows))}, "
          f"max {int(statistics.mean(s['max'] for s in rows))}, "
          f"+/call {int(statistics.mean(s['growth'] for s in rows))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
