#!/usr/bin/env python3
"""Statusline: current context size from the session transcript, zero chat tokens.

Claude Code pipes statusline JSON (with ``transcript_path``) to stdin; the script reads the
last main-chain assistant ``usage`` record and prints one line, e.g. ``ctx 20.5k/250k (8%)``.
Context = input_tokens + cache_creation_input_tokens + cache_read_input_tokens. The value
lags by one turn: the prompt being typed is not counted yet. Right after a compaction (no
assistant turn since) the size is the ``postTokens`` of the ``compact_boundary`` record.
The denominator is the auto-compact window of the session model (``model.id`` from stdin):
``modelSettings.<id>.autoCompactWindow``, else top-level ``autoCompactWindow``, read from
user, project and project-local settings (later wins). ``*`` marks the built-in default.

Wired in .claude/settings.json -> statusLine. Manual use:
    python Tools/ctx_usage.py --transcript <session>.jsonl
"""
import argparse
import json
import os
import sys
from typing import Optional

# Denominator when no settings file configures an auto-compact window for the model.
DEFAULT_WINDOW = 250_000
# Tail read size; doubled until a usage record is found or the file start is reached.
TAIL_CHUNK_BYTES = 256 * 1024


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--transcript", help="Transcript .jsonl path (default: from stdin JSON).")
    parser.add_argument("--window", type=int,
                        help="Context window in tokens (default: autoCompactWindow from settings).")
    parser.add_argument("--model", help="Model id for the settings lookup (default: from stdin JSON).")
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


def _settings_paths(project_dir: Optional[str]) -> list:
    """Returns settings files in increasing precedence: user, project, project-local."""
    paths = [os.path.join(os.path.expanduser("~"), ".claude", "settings.json")]
    if project_dir:
        paths.append(os.path.join(project_dir, ".claude", "settings.json"))
        paths.append(os.path.join(project_dir, ".claude", "settings.local.json"))
    return paths


def configured_window(model_id: Optional[str], project_dir: Optional[str]) -> Optional[int]:
    """Resolves the auto-compact window for the model from Claude Code settings.

    Args:
        model_id: Session model id, e.g. ``claude-opus-5-5``; a ``[...]`` suffix is ignored.
        project_dir: Project root holding ``.claude/settings*.json``.

    Returns:
        Window in tokens, or None if no settings file configures one.
    """
    base_id = model_id.split("[", 1)[0] if model_id else None
    window = None
    for path in _settings_paths(project_dir):
        try:
            with open(path, encoding="utf-8") as stream:
                settings = json.load(stream)
        except (OSError, json.JSONDecodeError):
            continue
        model_settings = (settings.get("modelSettings") or {}).get(base_id) or {}
        value = model_settings.get("autoCompactWindow", settings.get("autoCompactWindow"))
        if isinstance(value, int) and value > 0:
            window = value
    return window


def main() -> int:
    args = _parse_args()
    if args.window is not None and args.window <= 0:
        print("ctx: --window must be positive", file=sys.stderr)
        return 2
    path = args.transcript
    model_id = args.model
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if not path:
        try:
            status = json.load(sys.stdin)
        except json.JSONDecodeError as error:
            print(f"ctx: invalid statusline JSON on stdin ({error})")
            return 1
        path = status.get("transcript_path")
        model_id = model_id or (status.get("model") or {}).get("id")
        project_dir = (status.get("workspace") or {}).get("project_dir") or project_dir
    window = args.window or configured_window(model_id, project_dir)
    marker = "" if window else "*"
    window = window or DEFAULT_WINDOW
    if not path or not os.path.isfile(path):
        print(f"ctx: transcript not found ({path})")
        return 1
    tokens = last_context_tokens(path)
    if tokens is None:
        print("ctx: no assistant turn yet")
        return 0
    print(f"ctx {tokens / 1000:.1f}k/{window // 1000}k{marker} ({tokens * 100 // window}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
