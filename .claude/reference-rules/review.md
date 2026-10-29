---
description: Reviewing code, a diff, a PR or a plan, and the self-review before saying "done" — coverage of every changed file, severity, evidence per finding, what was not reviewed
load: on-demand
---

# Review coverage

## Forbidden

- "Looks good" / "no issues" after reading part of the change; silence about files not opened.
- A finding without a location (`path:line`) or without the evidence that makes it a finding.
- Merging several defects into one line, or listing a confirmed defect as a style remark.
- Reviewing the description of the change instead of the change itself.

## Must

- Build the file list from the diff (`git diff --stat <base>`), not from the summary. Each file ends
  as `reviewed`, `skimmed (why)` or `not reviewed (why)` in the report.
- One line per finding: severity (`blocker` / `major` / `minor` / `nit`), `path:line`, what is
  wrong, the evidence (code read, command output, test), and the fix direction.
- Confirmed defects follow `RR/no-masking.md`; unconfirmed suspicions are one line each with the
  check that would confirm them.
- Check, where relevant: correctness at boundaries, error paths, lifetime/ownership, concurrency,
  persistence and versioning, init/teardown order, performance on hot paths (evidence only),
  tests covering the change.
- Self-review before "done": scope matches the ask (no drive-by edits), no invented API, claims
  labelled Verified / Inferred / Unverified, build/tests ran after the last edit or the report says not.
- Large change: state the coverage limit up front ("reviewed 12 of 40 files: …") rather than
  implying a full review.
