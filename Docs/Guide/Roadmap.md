# Gaps and possible additions

Status of the kit: the baseline (lean `CLAUDE.md`, output style, settings, on-demand rules) and the
context guards are in place. Below is what is missing, ordered by expected value. Each item has
been used in practice in a stack-specific form; "port" means generalize it, not copy it.

## P1 — closes a known hole

| Item | Gap today | Shape |
|------|-----------|-------|
| Verify gate (Stop hook) | "Built, unverified" is prose only; a turn can end with "done" after source edits and no build/test | Scan the transcript of the current turn: edits to files matching a configurable `SOURCE_RE` after the last command matching `VERIFY_RE` (build/test) → exit 2 with "run <command> or state 'not verified'" |
| Bash guard / output router | Raw build, test and log commands flood the context | PreToolUse Bash hook with a configurable table `raw command regex → wrapper`; block with the wrapper command; escape marker |
| Ownership ledger | Several agents in one working tree cannot prove which edits are theirs; work stays uncommitted | Pre/PostToolUse(Edit/Write) records `session → path`; `claim <paths>` for shell edits; `commit -m … [--dry-run]` stages only owned paths; Stop hook asks to commit or state the blocker |

## P2 — makes the improvement loop cheap

| Item | Purpose |
|------|---------|
| Corrections finder | Lists the user's pushback prompts ("wrong", "revert", "not what I asked") from recent transcripts with the answer they corrected → worklist for the rule gap check |
| Tool-gap finder | Ranks shell command families by total output size, raw calls that bypass an existing wrapper, files re-read across many chats → worklist for wrappers, hooks and code maps |
| Rule load profiler | For `.claude/rules/`: size per rule, dead `paths:` globs, rules without `paths:`, rules that always co-load, duplicates |
| L1 digest check | Hash snapshot of `CLAUDE.md` and the rules it summarizes; CI fails on unreviewed drift between them |
| Language guards | PreToolUse(Edit/Write) blocks file text in a non-file language; CI check with a reviewed legacy-debt list (for teams that chat in one language and keep files in English) |
| Fix-commit hook | After a commit whose message starts with `fix`, remind the agent to run the rule gap check |

## P3 — scale and multi-tool

| Item | Purpose |
|------|---------|
| Knowledge-base search | Keyword/alias index over `Docs/` and rules, so the agent finds the owning page with one call instead of a broad Grep |
| Symbol lookup wrapper | Definitions, writes, readers, callers and function bodies by name for the project's language; replaces grep + sed chains (largest re-read source in big codebases) |
| Code map | `Docs/code-map/` with one row per source folder and a curated symbol list; a CI check that every folder has a row |
| Rule catalog + CI | Generated index of all rules with descriptions; CI validates frontmatter, links and catalog freshness |
| Codex / other agents | `AGENTS.md` pointing to the same rules; a small script that prints the applicable rules for a path; Codex hooks mirroring the Claude ones |
| Path-scoped rule examples | One or two neutral examples in `.claude/rules/` (e.g. tests folder, migrations folder) |
| Planning template | `Docs/plans/_TEMPLATE.md` matching `RR/planning.md` steps |

## Deliberately left out

- Stack-specific rules (language idioms, framework lifecycles, engine APIs): add per project as
  path-scoped rules.
- Subagent workflows: denied in `settings.json` because they multiply cost; re-enable `Agent` only
  with a measured reason.
- Automatic memory: disabled; durable knowledge goes to rules and `Docs/` where it is reviewed.

## Open questions for adopters

- Thresholds (300-line read limit, 120-line shell slices, 100k topic gate, 200-call session nudge)
  were tuned on one project. Re-measure with `ctx_stats.py` and adjust the constants.
- `permissions.deny` contains tool names that change between Claude Code versions; unknown names
  are harmless, missing new ones are not removed automatically. Review after upgrades.
