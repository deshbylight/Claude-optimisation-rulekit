---
description: Found bug or error → report it, keep it in Docs/Review/OpenDefects.md until its fix lands, fix each one; no fallback/default/skip/retry or default-off flag as the fix, no "one update covers it" bundling
load: on-demand
---

# No masking of found defects

Applies whenever an investigation, review, log read or fix turns up a defect: code bug, wrong data,
config error, failed check.

## Forbidden

- Proposing a fallback, default value, retry, `continue`/early-return skip, clamp or "safe" guard as
  the fix for a defect whose root cause is known or findable; the fallback hides the broken primary path.
- Gating a correct fix behind a flag that defaults to the old buggy behavior because some tests,
  inputs or metrics got worse with it. Code that passed only through a defect is not a baseline: ship
  the fix and log the newly failing cases as a new defect with its own row and investigation. Flags
  stay for A/B of genuine design alternatives, not for correctness fixes.
- Folding several distinct defects into one item ("the upcoming refactor covers all of these")
  without listing each defect separately.
- Dropping a found defect from the report because a planned change "will fix it anyway", because it
  is not the asked-for symptom, or because current logs show no occurrence.
- Leaving a found defect only in chat, or deleting its row from `Docs/Review/OpenDefects.md` for any
  reason but a landed fix. Only the owner may close a row without a fix.
- Waving off a failed check (build, test, lint) as "pre-existing / unrelated" with only the check name.

## Must

- One line per defect: what, where (`file:line`), effect, root cause, fix. Count the defects found;
  the report and the fix plan list the same number.
- One change that fixes several defects → name each defect, show how the change removes it, and
  verify each one separately (test, log line, repro), not the bundle as a whole.
- A degradation path the design genuinely needs (missing user data, external input) stays loud:
  a warning/error with a stable tag, and the defect that triggers it keeps its own fix item.
- Warnings and unconfirmed suspicions → one report line each (what, where, the check that would
  confirm it), no `OpenDefects.md` row until confirmed.
- Every confirmed defect, in task scope or not, found and not fixed in the same commit → a row in
  `Docs/Review/OpenDefects.md` in the same turn it is reported. Its fix commit deletes the row after
  the fix is verified; a partial fix shrinks the row to the remaining part.
- Every case a fix excludes or skips → state why it is legitimately out of scope, or turn it into
  its own defect and fix item.
- Each failing check left unfixed → own report line: check name, the failing items quoted from its
  output, cause, the fix, and the evidence it is not yours (failing paths outside your diff, or it
  fails on `HEAD` without your change).
