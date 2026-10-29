#!/usr/bin/env python3
"""PreToolUse hook (Bash|PowerShell): route raw commands to the project's wrappers.

A raw build, a full log read or a repo-wide grep floods the context with output a wrapper would cut
to the errors or the matching slice; a rule line saying "use the wrapper" is ignored often enough to
matter. Routes live in `.claude/rulekit/shell-routes.json` (adapted per project; empty = no effect):

    {"routes": [{"match": "<regex>", "unless": "<regex, optional>", "say": "<what to run instead>"}]}

A command matching `match` and not `unless` is blocked (exit 2) with `say` on stderr. Heredoc bodies
are ignored, so text written into a file does not trigger a route. Escape hatch: put RULEKIT_RAW in
the command (e.g. `RULEKIT_RAW=1 make build`) when the raw output is really needed.
Disable: env RULEKIT_SHELL_GUARD_OFF=1. Fails open (exit 0) on malformed input or config.
"""
import json
import os
import re
import sys

HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?^\s*\1\s*$", re.S | re.M)


def load_routes(project_dir: str) -> list:
    path = os.path.join(project_dir, ".claude", "rulekit", "shell-routes.json")
    try:
        with open(path, encoding="utf-8") as f:
            routes = json.load(f).get("routes") or []
    except (OSError, ValueError, AttributeError):
        return []
    compiled = []
    for r in routes:
        try:
            compiled.append((re.compile(r["match"], re.I | re.M),
                             re.compile(r["unless"], re.I | re.M) if r.get("unless") else None,
                             r.get("say") or "use the project's wrapper (see CLAUDE.md)"))
        except (KeyError, TypeError, re.error):  # one bad route must not disable the others
            continue
    return compiled


def main() -> int:
    if os.environ.get("RULEKIT_SHELL_GUARD_OFF"):
        return 0
    try:
        ev = json.load(sys.stdin)
        command = (ev.get("tool_input") or {}).get("command") or ""
    except (ValueError, AttributeError):
        return 0
    if not command or "RULEKIT_RAW" in command:
        return 0
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or ev.get("cwd") or os.getcwd()
    text = HEREDOC_RE.sub("", command)
    for match, unless, say in load_routes(project_dir):
        if match.search(text) and not (unless and unless.search(text)):
            sys.stderr.write(f"[SHELL-GUARD] {say} (RULEKIT_RAW in the command bypasses this route)\n")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
