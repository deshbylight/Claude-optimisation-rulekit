#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write|MultiEdit): block edits that add non-English text to project files.

CLAUDE.md says file text is English whatever the chat language; when the chat is in another language
the model drifts and writes comments, docs and commit-bound text in it. A line counts as added when
its trimmed text is absent from the replaced text (Edit old_string, MultiEdit edits, the current file
for Write), so translating an existing line passes. "Non-English" = letters outside the Latin and
Greek scripts (Greek stays allowed for math). In Markdown, inline code spans and fenced blocks are
skipped. Localization files are skipped by path.

Config (`.claude/settings.json` -> env):
  RULEKIT_FILE_LANG_SKIP   regex on the path of files to skip; default: locale/i18n folders and
                           translation formats
  RULEKIT_FILE_LANG_GUARD=off   disables the guard (projects whose files are not in English)
Exit 2 with a reason on stderr blocks the call. Fails open (exit 0) on malformed input.
"""
import json
import os
import re
import sys
import unicodedata

DEFAULT_SKIP_RE = r"(^|/)(locales?|i18n|l10n|translations?|lang)/|\.(po|pot|resx|strings|stringsdict|xliff?|arb)$"
CODE_SPAN_RE = re.compile(r"`[^`]*`")
SHOWN_MAX = 3


def foreign(text: str) -> bool:
    for ch in text:
        if ord(ch) > 0x24F and ch.isalpha():
            if not unicodedata.name(ch, "").startswith(("LATIN", "GREEK")):
                return True
    return False


def prose_lines(text: str, markdown: bool) -> list:
    out, fenced = [], False
    for line in text.splitlines():
        if markdown and line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if not fenced:
            out.append(CODE_SPAN_RE.sub("", line) if markdown else line)
    return out


def pairs(tool: str, inp: dict) -> list:
    """(old text, new text) pairs the call writes."""
    if tool == "Edit":
        return [(inp.get("old_string") or "", inp.get("new_string") or "")]
    if tool == "MultiEdit":
        return [(e.get("old_string") or "", e.get("new_string") or "") for e in inp.get("edits") or []]
    if tool == "Write":
        old = ""
        try:
            with open(inp.get("file_path") or "", encoding="utf-8", errors="replace") as f:
                old = f.read()
        except OSError:  # new file
            pass
        return [(old, inp.get("content") or "")]
    return []


def main() -> int:
    if os.environ.get("RULEKIT_FILE_LANG_GUARD", "").strip().lower() == "off":
        return 0
    try:
        ev = json.load(sys.stdin)
        tool, inp = ev.get("tool_name"), ev.get("tool_input") or {}
        path = (inp.get("file_path") or "").replace("\\", "/")
    except (ValueError, AttributeError):
        return 0
    try:
        skip = re.compile(os.environ.get("RULEKIT_FILE_LANG_SKIP") or DEFAULT_SKIP_RE, re.I)
    except re.error:
        skip = re.compile(DEFAULT_SKIP_RE, re.I)
    if not path or skip.search(path):
        return 0
    markdown = path.lower().endswith((".md", ".mdx", ".markdown"))
    added = []
    for old, new in pairs(tool, inp):
        before = {line.strip() for line in old.splitlines()}
        added += [line.strip() for line in prose_lines(new, markdown)
                  if line.strip() not in before and foreign(line)]
    if not added:
        return 0
    shown = "; ".join(a[:80] for a in added[:SHOWN_MAX])
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.write(f"[LANGUAGE-GUARD] {len(added)} added line(s) in {os.path.basename(path)} are not in English "
                     f"(file text is English, CLAUDE.md): {shown}. Translate them and retry. Localization "
                     "files: RULEKIT_FILE_LANG_SKIP; non-English project: RULEKIT_FILE_LANG_GUARD=off.\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
