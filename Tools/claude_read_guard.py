#!/usr/bin/env python3
"""PreToolUse hook (Read|Write|Bash|PowerShell): keep whole large files out of the agent context.

Full Reads of 1000+ line source files (several times per session), full Reads of persisted tool
outputs and whole-file Write rewrites are the largest controllable sources of context growth
(measure your own sessions with Tools/ctx_stats.py).

Blocks (exit 2, reason on stderr):
  * Read of a text file over READ_MAX_LINES lines / READ_MAX_CHARS chars without `limit`.
  * Read of a persisted tool output (`.../tool-results/...`) over PERSISTED_MAX_CHARS without `limit`.
  * Write that overwrites an existing text file over WRITE_MAX_LINES lines (use Edit).
  * Shell read (cat / head / tail / sed -n A,Bp / Get-Content) that prints a whole file over
    READ_MAX_LINES, more than SHELL_MAX_WINDOW lines of such a file, or more than SHELL_MAX_WINDOW
    lines / PERSISTED_MAX_CHARS of a persisted tool output. Piped/redirected readers and
    scratchpad/temp paths pass.
Escape hatch: pass an explicit `limit` to Read; for Write, delete/rename first or use Edit;
for shell reads, put RULEKIT_FULL_READ in the command.

Wired in .claude/settings.json -> hooks.PreToolUse.
"""
import json
import os
import re
import shlex
import sys

READ_MAX_LINES = 300
READ_MAX_CHARS = 40000
PERSISTED_MAX_CHARS = 8000  # outputs over bashOutputMaxChars (.claude/settings.json) persist; smaller dumps still read whole
WRITE_MAX_LINES = 300
# Reads of these are rendered by the tool (images/PDF/notebooks), not dumped as text.
NON_TEXT_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf", ".ipynb"}


def _file_stats(path: str):
    """Returns (lines, chars) of a text file, or None if it is missing/unreadable."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:  # missing / locked file: let the tool report it itself
        return None
    return text.count("\n") + 1, len(text)


def _check_read(tool_input: dict) -> str:
    path = str(tool_input.get("file_path", ""))
    if not path or tool_input.get("limit") or os.path.splitext(path)[1].lower() in NON_TEXT_EXT:
        return ""
    stats = _file_stats(path)
    if stats is None:
        return ""
    lines, chars = stats
    norm = path.replace("\\", "/")
    if "/tool-results/" in norm and chars > PERSISTED_MAX_CHARS:
        return (f"Persisted tool output is {chars} chars: Grep it for the lines you need, or Read with "
                f"offset+limit. Do not load the whole dump.")
    if lines > READ_MAX_LINES or chars > READ_MAX_CHARS:
        return (f"{os.path.basename(path)} is {lines} lines / {chars} chars: Grep first, then Read with "
                f"offset+limit (40-120 lines). Do not re-read ranges already in context. Genuinely need it "
                f"all? pass an explicit limit.")
    return ""


def _check_write(tool_input: dict) -> str:
    path = str(tool_input.get("file_path", ""))
    if not path or not os.path.isfile(path):
        return ""
    stats = _file_stats(path)
    if stats is None or stats[0] <= WRITE_MAX_LINES:
        return ""
    return (f"{os.path.basename(path)} exists ({stats[0]} lines): rewriting it with Write puts the whole "
            f"file into context. Use Edit for the changed parts.")


# --- Shell reads (Bash|PowerShell) ------------------------------------------------------------
# cat/head/tail/sed -n/Get-Content print straight into context and would bypass the Read checks
# above. Only an unfiltered reader stage is checked: anything piped
# onward (grep, wc, Select-Object) or redirected to a file passes.
SHELL_MAX_WINDOW = 120
HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\s*(?:\n|$)", re.S)
HERESTRING_RE = re.compile(r"@(['\"])\n.*?\n\1@", re.S)
SED_RANGE_RE = re.compile(r"^(\d+)(?:,(\d+|\$))?p$")
SEPARATORS = {";", "&&", "||", "&", "|", "|&", ";;"}
PS_READERS = {"get-content", "gc", "type", "cat"}
PS_COUNT_FLAGS = {"-totalcount", "-head", "-first", "-tail", "-last"}
EXEMPT_PATH_PARTS = ("/scratchpad/", "/temp/", "/tmp/")
FULL_READ_MARKER = "RULEKIT_FULL_READ"  # escape hatch for shell reads


def _resolve(token: str, cwd: str) -> str:
    """Shell path token -> absolute OS path ('' when it cannot be a plain file argument)."""
    path = token.strip("'\"")
    proj = os.environ.get("CLAUDE_PROJECT_DIR", cwd)
    for var in ("$env:CLAUDE_PROJECT_DIR", "${CLAUDE_PROJECT_DIR}", "$CLAUDE_PROJECT_DIR"):
        path = path.replace(var, proj)
    if not path or any(c in path for c in "$*?<>`(){}") or path.startswith("-"):
        return ""
    m = re.match(r"^/([a-zA-Z])(/.*)?$", path)  # Git Bash /<drive>/dir -> <drive>:/dir
    if m:
        path = f"{m.group(1).upper()}:{m.group(2) or '/'}"
    path = os.path.expanduser(path)
    return path if os.path.isabs(path) else os.path.join(cwd, path)


def _shell_stages(command: str):
    """Yields (tokens, piped_or_redirected) per simple command; heredoc/here-string bodies dropped."""
    command = HERESTRING_RE.sub("", HEREDOC_RE.sub("\n", command))
    command = re.sub(r"[\\`]\r?\n", " ", command)  # line continuations
    for line in command.splitlines():
        line = re.sub(r"\d?>&\d", " ", line)  # 2>&1: keep '&' from reading as a separator
        lexer = shlex.shlex(line, posix=False, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        try:
            tokens = list(lexer)
        except ValueError:  # unbalanced quotes: do not guess
            continue
        stage = []
        for tok in tokens + [";"]:
            if tok not in SEPARATORS:
                stage.append(tok)
                continue
            if stage:  # output piped onward or redirected to a file never reaches the context
                yield stage, tok in ("|", "|&") or any(t.startswith((">", "1>")) for t in stage)
            stage = []


def _int(token: str):
    token = token.strip("'\"")
    return int(token) if token.lstrip("+-").isdigit() else None


def _reader_window(tokens):
    """(files, window) for a reader stage: window None = whole file, int = max lines printed,
    ('from', K) = tail -n +K. Returns None for non-reader commands."""
    cmd = os.path.basename(tokens[0].strip("'\"")).lower()
    if cmd.endswith(".exe"):
        cmd = cmd[:-4]
    args = tokens[1:]
    files, window = [], None
    if cmd in ("head", "tail"):
        window, i = 10, 0
        while i < len(args):
            a = args[i]
            if a in ("-n", "--lines") and i + 1 < len(args):
                val = args[i + 1].strip("'\"")
                window = ("from", int(val[1:])) if cmd == "tail" and val.startswith("+") and val[1:].isdigit() \
                    else _int(val) or window
                i += 1
            elif re.match(r"^-n?\d+$", a):
                window = int(a.lstrip("-n"))
            elif a.startswith("--lines="):
                window = _int(a.split("=", 1)[1]) or window
            elif a in ("-f", "-F", "--follow"):
                return None
            elif not a.startswith("-"):
                files.append(a)
            i += 1
        return files, window
    if cmd == "sed":
        if "-n" not in args and "--quiet" not in args:
            return None
        script = next((a for a in args if not a.startswith("-")), "")
        total = 0
        for part in script.strip("'\"").split(";"):
            m = SED_RANGE_RE.match(part.strip())
            if not m:
                return None  # /regex/ addresses, substitutions: not a plain slice
            lo = int(m.group(1))
            hi = m.group(2)
            total += 1 if hi is None else (10 ** 9 if hi == "$" else max(0, int(hi) - lo + 1))
        files = [a for a in args if not a.startswith("-") and a is not script]
        return files, total
    if cmd in PS_READERS:
        i = 0
        while i < len(args):
            a = args[i]
            low = a.lower()
            if low in PS_COUNT_FLAGS and i + 1 < len(args):
                window = _int(args[i + 1]) or window
                i += 1
            elif low in ("-path", "-literalpath") and i + 1 < len(args):
                files.append(args[i + 1])
                i += 1
            elif low in ("-encoding", "-delimiter", "-readcount", "-stream") and i + 1 < len(args):
                i += 1
            elif not a.startswith("-"):
                files.append(a)
            i += 1
        return files, window
    return None


def _file_lines(path: str):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    return data.count(b"\n") + 1, len(data)


def _check_shell(command: str, cwd: str) -> str:
    if FULL_READ_MARKER in command:
        return ""
    for tokens, piped in _shell_stages(command):
        if tokens[0].lower() in ("cd", "set-location", "sl", "pushd") and len(tokens) > 1:
            target = _resolve(tokens[-1], cwd)
            cwd = target if target and os.path.isdir(target) else cwd
            continue
        if piped:
            continue
        parsed = _reader_window(tokens)
        if not parsed:
            continue
        files, window = parsed
        for token in files:
            path = _resolve(token, cwd)
            norm = path.replace("\\", "/").lower()
            if not path or any(p in norm for p in EXEMPT_PATH_PARTS) or not os.path.isfile(path) \
                    or os.path.splitext(path)[1].lower() in NON_TEXT_EXT:
                continue
            stats = _file_lines(path)
            if stats is None:
                continue
            lines, chars = stats
            shown = lines if window is None else max(0, lines - window[1] + 1) if isinstance(window, tuple) \
                else min(window, lines)
            name = os.path.basename(path)
            if "/tool-results/" in norm:
                if shown > SHELL_MAX_WINDOW or (window is None and chars > PERSISTED_MAX_CHARS):
                    return (f"Persisted tool output {name} is {lines} lines / {chars} chars and this command "
                            f"prints {shown} of them: Grep it for the lines you need, or slice <= "
                            f"{SHELL_MAX_WINDOW} lines. Do not load the whole dump.")
                continue
            if lines <= READ_MAX_LINES and chars <= READ_MAX_CHARS:
                continue
            if window is None:
                return (f"`{tokens[0]}` of the whole {name} ({lines} lines / {chars} chars) bypasses the Read "
                        f"guard: Grep first, then Read with offset+limit (40-120 lines) or pipe through "
                        f"grep. Genuinely need it all? add {FULL_READ_MARKER} to the command.")
            if shown > SHELL_MAX_WINDOW:
                return (f"This `{tokens[0]}` prints {shown} lines of {name} ({lines} lines): keep shell slices "
                        f"<= {SHELL_MAX_WINDOW} lines (or Read with offset+limit), Grep first. Do not re-read "
                        f"ranges already in context. Genuinely need it? add {FULL_READ_MARKER} to the command.")
    return ""


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:  # malformed hook payload: never block the tool call
        return 0
    tool_input = data.get("tool_input") or {}
    tool = data.get("tool_name", "")
    if tool in ("Bash", "PowerShell"):
        reason = _check_shell(str(tool_input.get("command", "")), data.get("cwd") or os.getcwd())
    else:
        reason = _check_read(tool_input) if tool == "Read" else _check_write(tool_input) if tool == "Write" else ""
    if reason:
        sys.stderr.write(reason + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
