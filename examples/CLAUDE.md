# Ledgerly

<!-- Example only: the kit template filled in for a fictional invoicing service. Compare it with the
     template (`template/CLAUDE.md`) to see which lines are project facts and which are kit law. -->

Chat language: every reply to the user is in English; code, identifiers, commands and log text stay as-is.

- Project: invoicing REST service, Python 3.12 + FastAPI + SQLAlchemy 2 + PostgreSQL 16; entry
  `app/main.py`, domain in `app/billing/`, workers in `app/jobs/`. Build: `make lint`. Tests: `make test`.
- Architecture: money is `Decimal` in minor units, never `float`; every write to `invoices` goes
  through `InvoiceService`; schema changes only via Alembic revisions, never `create_all`.
- Path prefix: `RR/` = `.claude/reference-rules/`.

## Layer 1 — always-apply digest

- Contract: classify the task and ownership before editing. Never invent API, library behavior,
  modules, configs or paths: Grep/Read first. Project decisions beat generic advice. Code and comment
  disagree: believe the code, flag the stale comment. Stop and ask on high risk: Alembic migrations,
  public REST schema (`app/api/schemas/`), payment-provider webhooks, mass rename, `pyproject.toml`.
- Evidence: label claims Verified / Inferred / Unverified. Database or queue state is fact only after
  a query, script or log this session, else `unverified` plus the check that settles it. Green lint =
  "built, unverified" until `make test` or the owner confirms. Owner contests a verified claim:
  re-check, don't just agree. `make test-integration` (8 min, Docker) only when the ask needs it;
  state aim and duration first.
- Code edits need explicit approval: propose briefly (files, what, why; no full patch in chat), get
  approval, then edit. A change spanning several packages or with non-trivial logic: first Read
  `RR/planning.md` and send a self-verified plan. Approval persists for the approved scope.
  `.md`, `Tools/` scripts and builds need no separate approval when part of the ask.
- No masking: each confirmed bug = own report line and own fix item; not fixed in the same commit →
  a row in `Docs/Review/OpenDefects.md`. Never a fallback/default/skip/retry as the fix, nor a fix
  behind a default-off flag because some tests regressed (`RR/no-masking.md`).
- Before adding a module, a new mechanism or a non-trivial algorithm: search the project, then
  FastAPI/SQLAlchemy/Pydantic, then public prior art (`RR/search.md`). Before "done", check where
  relevant: transactions and session lifetime, async/await correctness, idempotency of jobs, perf.
- Rule gaps: a fix whose root cause is a reusable class of bug with no rule, or writing a rule:
  first Read `RR/rule-authoring.md`.
- Output: no preamble, no recaps, no basic lectures. Minimal scope: no drive-by
  refactors/renames/reformatting. Any question that needs the owner's answer goes through
  `AskUserQuestion` only; the full report is written in chat before it. Updates plain and short.
- Context: Grep before Read; Read with offset/limit (40–120 lines), never whole files over 300 lines.
  Batch independent lookups (≤3 parallel calls). Logs: 3–5 lines around the error. Re-read before
  editing. A `[LONG-SESSION]` or `[TOPIC-GATE]` note → follow it (skill `handoff`).
- File language: new or edited file text in English.
- Git: after an authorized task passes `make lint test`, create a scoped local commit without asking
  again; report hash and checks. Stage task-owned paths only. Separate authorization needed:
  `stash`, amend, `checkout`/`restore`/`reset`, `clean`, `push`/`pull`/`merge`/`rebase`. Details: `RR/git.md`.

## Layer 2 — task triggers (Read before starting)

- Alembic migration or model change: `RR/migrations.md`.
- Payment-provider webhooks, retries, idempotency keys: `RR/webhooks.md`.
- Code review, PR review: `RR/review.md`.

## Shared execution rules

- Lint: `make lint` (ruff + mypy, errors only). Tests: `make test` (pytest -q -x), foreground, no `| tail`.
  Logs: `python scripts/tail_errors.py --last 200`.
- Subagents: none. Process skills only when the user types `/<name>`.
- Old chats: `python Tools/claude_session_grep.py <id> --prompts | "<regex>"`.
- Context measurement: `python Tools/ctx_stats.py --last 15`.
