# <YYYY-MM-DD> <topic>

<!-- Copy to `Docs/plans/YYYY-MM-DD-<topic>.md` (or `Docs/plans/<topic>/<stage-id>.md` for a stage
     of a map). Steps follow `.claude/reference-rules/planning.md`. Delete these comments. -->

Status: draft | approved | done `<commit>`. Map: `<Docs/plans/<topic>/MAP.md, stage id, or none>`.

## Goal

<one or two lines: what changes for the user or the system; how we know it worked>

## Ownership and scope

- Owner layer / system: <core | orchestrator | adapter | presentation>; system entry: `Docs/Systems/<system>.md`.
- Files: `<path>` — <what changes>.
- Out of scope: <what this plan deliberately does not touch>.

## Steps

| # | File / function | Change | Check |
|---|-----------------|--------|-------|
| 1 | `<path>` `<Function>` | <what> | <build / test name / log line> |

## Weak points

| Step | Risk (values, lifetime, concurrency, order, persistence, perf, conflicts) | Handling: fix, guard with reason, or verification step |
|------|------|----------|

## Verified claims

- `<symbol / path / API / behavior>` — opened `<path:line>` or docs `<URL>`; or `unverified` → step `<#>`.

## Decided

- <implementation choices made without asking: names, placement, order — owner may override>.

## Open questions (key logic only)

- <behavior or architecture fork: options, consequences, recommendation> — or "none".
