# rulekit (kit development)

This file is for working on the kit itself. The template users get is `template/CLAUDE.md`;
`install.py` copies it into their project. Do not put project-template text here.

- Layout: `template/CLAUDE.md` (L1 template), `.claude/reference-rules/` (on-demand rules),
  `.claude/rulekit/ADAPT.md` (adaptation prompt), `Tools/` (hooks, measurement, checks),
  `install.py`, `Docs/Guide/` (guides), `examples/`.
- Every file text in English. No names, paths or vendors of private projects:
  `python Tools/check_kit.py` scans for them (`.claude/kit-scan-terms.txt`, git-ignored).
- Python 3.9+, standard library only. Hooks fail open (exit 0) on malformed input; a block is
  exit 2 with a reason that says what to do instead.
- New or changed kit file → add it to `install.py` `FILES` if users need it; `CHANGELOG.md` line.
- Rules follow `.claude/reference-rules/rule-authoring.md`; guides follow `Docs/Guide/WritingRules.md`.
- Before "done": `python Tools/check_kit.py` and `python -m unittest discover -s Tools/tests -v`.
- Measure claims about cost (`Tools/ctx_stats.py`, `claude -p … --output-format json`); state
  the configuration a number was measured with.
- Git: scoped commits of task-owned paths; `push`, tags and releases only on the owner's request.
