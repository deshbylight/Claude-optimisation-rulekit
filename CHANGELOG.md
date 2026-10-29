# Changelog

Format: newest first; one line per user-visible change.

## Unreleased

- New on-demand rules: `architecture.md` (code decomposition from scratch: pure core vs boundary,
  Config/Output/Transient, dense ids and O(1) indexes, phases, determinism, per-system docs) and
  `decomposition.md` (large work split into one-session stages with a map file); template trigger lines.
- `Docs/plans/_TEMPLATE.md` (installed); `Docs/Guide/WritingRules.md`: rules by code module.
- `Docs/Guide/ThirdParty.md`: what the kit ships vs. third-party skills used alongside it
  (`mattpocock/skills`, `obra/superpowers`), how to adopt them, and Graft (Trail-code) as an
  optional code-graph layer for new projects with its points of contact with the kit.

## 0.4.0 — 2026-10-29

- `install.py --uninstall`: removes kit files unchanged since install (manifest now stores hashes)
  and the kit's hooks; lists what it leaves for review.
- Hook commands use `python3` when `python` is missing or not Python 3 (macOS/Linux); an existing
  hook for the same script with another interpreter is not duplicated.
- Template moved to `template/CLAUDE.md`; the root `CLAUDE.md` is now for developing the kit.
- README: quick start from a clone, teams, update, uninstall, developing the kit.

## 0.3.0 — 2026-10-29

- `install.py`: one-command, re-runnable install into any repo (settings merge, stack and command
  detection, PowerShell deny on Windows with Git Bash, `.gitignore`, optional user settings merge,
  manifest). `.claude/rulekit/ADAPT.md`: the one prompt that finishes the adaptation in Claude Code.
- `Tools/tests/test_install.py`: fresh install, idempotent re-run, merge into an existing config,
  invalid settings abort.

## 0.2.0 — 2026-10-29

- `disableClaudeAiConnectors: true` in `.claude/settings.json`: claude.ai connectors cost ~1.7k tokens
  per call; measured baselines per configuration in [Cost](Docs/Guide/Cost.md).
- Rules: `RR/git.md` (detailed git policy), `RR/review.md` (review coverage), `RR/shared-workspace.md`;
  `CLAUDE.md` names them.
- Guides: [Writing rules](Docs/Guide/WritingRules.md), [Cost](Docs/Guide/Cost.md) (with a measured
  clean-repo baseline), [Tools](Docs/Guide/Tools.md) (disabled vs available), [Fix log](Docs/Guide/Fixes.md).
- Examples: `examples/CLAUDE.md` (filled for a fictional project), `.claude/settings.local.json.example`.
- `Tools/ctx_stats.py --min-calls N`: short sessions were silently hidden (fixed threshold 10).
- `Tools/check_kit.py` and `Tools/tests/test_hooks.py`; GitHub Actions CI on Linux and Windows.
- MIT license.

## 0.1.0 — 2026-10-29

- Initial kit: `CLAUDE.md` template, lean output style, settings and deny list, user settings,
  on-demand rules (no-masking, planning, search, rule-authoring), hooks (read guard, topic gate,
  session length, reply language), skill `handoff`, `ctx_stats.py`, `claude_session_grep.py`, guides.
