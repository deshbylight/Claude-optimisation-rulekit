---
description: Before a change spanning several modules or with non-trivial logic, draft a plan document, hunt its weak points, verify every claim yourself, polish it, then send it for approval asking the owner only key-logic choices
load: on-demand
---

# Self-verified plan before approval

Applies to code changes that touch more than one module/class or change non-trivial logic, and to
multi-file tasks beyond `.md` and `Tools/`. A one-module change with simple logic (a condition, a
value, a log line) needs only the short proposal and approval from CLAUDE.md. High-risk areas (data
formats, public API, protocol, migrations) need the full plan plus a separate owner approval of
their consequences. A `.md`/`Tools/`-only change the owner asked for needs no document: run steps
2–3 in your head and proceed.

## Forbidden

- Sending a plan for approval while any claim in it is unchecked: a symbol, path, API, library
  behavior or "existing mechanism" you did not open this session.
- Asking the owner what the code, logs, docs or project conventions already answer; asking
  implementation details (names, file placement, step order) — decide them and list them under `Decided`.
- Steps such as `TBD`, "investigate later", "adjust if needed", or a risk without a mitigation or
  verification step.
- Implementing before the plan is approved; approval covers the plan's scope only.

## Must

1. **Draft** in `Docs/plans/YYYY-MM-DD-<topic>.md` from `Docs/plans/_TEMPLATE.md`: goal, ownership, files, steps.
2. **Weak-point pass** per step: failure modes; value table (negative/zero/overflow/empty/sentinel);
   lifetime, concurrency, init/teardown order; persistence; perf in hot paths; interaction with
   existing systems; conflicting decisions or rules. Each finding becomes a plan item (fix, guard
   with a reason, or verification) — never a silent fallback (`no-masking.md`).
3. **Self-verify**: open every symbol, path and call site; library claims from its source or docs;
   search for an existing equivalent first (`search.md`). A fact only a runtime run can settle is
   marked `unverified` with that run placed as a plan step.
4. **Polish**: every step names file + function + change + its check (build, test, log line).
   State what stays out of scope.
5. **Review pass**: re-read the whole document as a reviewer — contradictions, missing steps, order
   dependencies. Fix, then repeat until clean.
6. **Present**: a short chat summary + the document path; the `Decided` list (owner may override);
   only open key-logic questions — behavior or architecture forks where the choice changes the
   result — each self-contained with options and a recommendation (`AskUserQuestion`). No open
   forks → ask for approval only.
