# <ProjectName>

<!-- Template. Replace every <placeholder>; delete lines that do not apply. Keep this file short:
     it is re-sent on every model call. Detail belongs in `.claude/reference-rules/` (read on demand)
     or path-scoped `.claude/rules/` (loaded only when a matching file is touched). -->

Chat language: <every reply to the user is in LANGUAGE; code, identifiers, commands and log text stay as-is>.

- Project: <one line: what it is, stack, main entry points>. Build: `<build command>`. Tests: `<test command>`.
- Architecture: <2-3 lines of invariants that no generic advice may override>.
- Path prefix: `RR/` = `.claude/reference-rules/`.

## Layer 1 — always-apply digest

- Contract: classify the task and ownership before editing. Never invent API, library behavior,
  modules, configs or paths: Grep/Read first. Project decisions beat generic advice. Code and comment
  disagree: believe the code, flag the stale comment. Stop and ask on high risk: <data formats, save
  files, public API, network protocol, migrations, mass rename, build-system changes>.
- Evidence: label claims Verified / Inferred / Unverified. Runtime state (database, running service,
  generated assets) is fact only after a command, script or log this session, else `unverified` plus
  the check that settles it. Green build = "built, unverified" until a test or the owner confirms.
  Owner contests a verified claim: re-check, don't just agree. Expensive runs (full test matrix,
  long benchmarks, release builds) only when the ask needs them; state aim and duration first.
- Code edits need explicit approval: propose briefly (files, what, why; no full patch in chat), get
  approval (any language or diff UI), then edit. A change spanning several modules or with
  non-trivial logic: first Read `RR/planning.md` and send a self-verified plan. Approval persists
  for the approved scope. `.md`, `Tools/` scripts and builds need no separate approval when part of the ask.
- No masking: each confirmed bug = own report line and own fix item; not fixed in the same commit →
  a row in `Docs/Review/OpenDefects.md` (deleted only by its verified fix). Warnings and unconfirmed
  suspicions = one report line with the confirming check. Never a fallback/default/skip/retry as the
  fix, nor a correct fix behind a default-off flag because some cases regressed (`RR/no-masking.md`).
- Before adding a module, a new mechanism or a non-trivial algorithm: search the project, then the
  framework/libraries in use, then public prior art (`RR/search.md`). Before "done", check where
  relevant: lifetime/ownership, concurrency, persistence, init/teardown order, perf (evidence).
- Rule gaps: a fix whose root cause is a reusable class of bug with no rule, or writing a rule:
  first Read `RR/rule-authoring.md`.
- Output: no preamble, no recaps, no basic lectures. Minimal scope: no drive-by
  refactors/renames/reformatting. Any question that needs the owner's answer goes through
  `AskUserQuestion` only, never as chat text; the full report is written in chat before it.
  Questions stand alone: concrete situation, plain options naming consequences, no rule IDs.
  Updates plain and short: what broke, what I do, why. Steps the task already names are run as
  given, not re-asked.
- Context: Grep before Read; Read with offset/limit (40–120 lines), never whole files over 300 lines
  or persisted tool output (`Tools/claude_read_guard.py` blocks it). Batch independent lookups
  (≤3 parallel calls or one shell command) when the combined output fits the result budget, else
  narrow or split. Do not re-read unchanged ranges. Logs: 3–5 lines around the error. Re-read before
  editing. A `[LONG-SESSION]` or `[TOPIC-GATE]` note → follow it (skill `handoff`).
- File language: new or edited file text in English (prose, comments, strings, configs) regardless
  of chat language. Identifiers, quotations and localization data stay as-is.
- Git: after an authorized task passes its checks, create a scoped local commit without asking again
  (unless told to leave it uncommitted); report hash and checks. Stage task-owned paths only
  (`git add <paths>`, never `-A`/`.`), review the staged diff including new files, preserve
  unrelated edits and pre-existing staged changes. Failed checks: report the blocker, leave the work
  uncommitted. Separate authorization needed: `stash`, amend, `checkout`/`restore`/`reset` of tracked
  files, `clean`, `push`/`pull`/`merge`/`rebase`, ref deletion, publishing. Details: `RR/git.md`.

## Layer 2 — task triggers (Read before starting)

- Code review, PR review, self-review of a large change: `RR/review.md`.
- Several chats/agents in one checkout, shared builds or logs: `RR/shared-workspace.md`.
- <Topic>: `RR/<topic>.md`.

## Shared execution rules

- Build: `<command>`, foreground, no `| tail`. Tests: `<command>`. Logs: `<how to slice logs>`.
- Subagents: none; plans and bulk prose run inline with check-in stops.
- Process skills only when the user types `/<name>`.
- Old chats: `python Tools/claude_session_grep.py <id> --prompts | "<regex>"`.
- Context measurement: `python Tools/ctx_stats.py --last 15`.
