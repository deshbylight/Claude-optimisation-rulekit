#!/usr/bin/env python3
"""Static checks for the kit itself (CI and before publishing).

    python Tools/check_kit.py

Checks every tracked-looking text file under the repo root:
  * `*.json` / `*.json.example` parse as JSON;
  * no Cyrillic text (file language is English; chat language is a setting, not file content);
  * no absolute machine paths (drive letters, user home directories);
  * no private terms: one term per line in `.claude/kit-scan-terms.txt` (git-ignored, so the list
    of names you must not leak is not itself published) and/or `RULEKIT_SCAN_TERMS` (comma-separated,
    e.g. a CI secret); matching is case-insensitive;
  * relative Markdown links resolve to an existing file;
  * every `.claude/reference-rules/*.md` starts with frontmatter that has `description:` and `load:`.
Exit 1 with one line per finding.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", "node_modules"}
TEXT_EXT = {".md", ".py", ".json", ".example", ".yml", ".yaml", ".txt", ".gitignore", ""}
TERMS_FILE = os.path.join(ROOT, ".claude", "kit-scan-terms.txt")
CYRILLIC_RE = re.compile("[%s-%s]" % (chr(0x400), chr(0x4FF)))
ABS_PATH_RE = re.compile(r"(?<![\w$%])[A-Za-z]:[\\/](?!/)|/home/[a-z]|/Users/[A-Za-z]|\\Users\\[A-Za-z]")
LINK_RE = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
SELF = os.path.abspath(__file__)


def files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith("_work_")]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.splitext(name)[1] in TEXT_EXT or name == "LICENSE":
                yield path


def private_terms():
    """(term, label) pairs. Terms from RULEKIT_SCAN_TERMS are labelled by number only: CI logs of a
    public repo are public, and GitHub masks the whole secret string, not each comma-separated term."""
    env = [t.strip() for t in os.environ.get("RULEKIT_SCAN_TERMS", "").split(",") if t.strip()]
    terms = [(t.lower(), f"#{i} of RULEKIT_SCAN_TERMS") for i, t in enumerate(env, 1)]
    if os.path.isfile(TERMS_FILE):
        with open(TERMS_FILE, encoding="utf-8") as f:
            terms += [(line.strip().lower(), f"'{line.strip()}'") for line in f
                      if line.strip() and not line.startswith("#")]
    return terms


def main() -> int:
    findings, terms = [], private_terms()
    for path in files():
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
            findings.append(f"{rel}: not UTF-8")
            continue
        if path.endswith((".json", ".json.example")):
            try:
                json.loads(text)
            except ValueError as e:
                findings.append(f"{rel}: invalid JSON: {e}")
        if os.path.abspath(path) == TERMS_FILE:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if CYRILLIC_RE.search(line):
                findings.append(f"{rel}:{n}: Cyrillic text")
            if os.path.abspath(path) != SELF and ABS_PATH_RE.search(line):
                findings.append(f"{rel}:{n}: absolute machine path")
            low = line.lower()
            for term, label in terms:
                if term in low:
                    findings.append(f"{rel}:{n}: private term {label}")
            if rel.endswith(".md"):
                for target in LINK_RE.findall(line):
                    if "://" in target or target.startswith("mailto:"):
                        continue
                    if not os.path.exists(os.path.join(os.path.dirname(path), target)):
                        findings.append(f"{rel}:{n}: broken link {target}")
        if rel.startswith(".claude/reference-rules/") and rel.endswith(".md"):
            head = text.split("---", 2)
            if not text.startswith("---") or len(head) < 3 \
                    or "description:" not in head[1] or "load:" not in head[1]:
                findings.append(f"{rel}: frontmatter needs description: and load:")
    for f in findings:
        print(f)
    print(f"check_kit: {len(findings)} finding(s), {len(terms)} private term(s) scanned")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
