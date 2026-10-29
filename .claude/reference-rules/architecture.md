---
description: Designing a new system, module or project from scratch, or a change that moves code between layers — pure core vs boundary, Config/Output/Transient state, dense ids and O(1) indexes, explicit phases, determinism, and the docs each system gets
load: on-demand
---

# Code decomposition

## Forbidden

- Core logic (algorithms, rules, data transforms) that includes or calls framework objects, UI,
  network, database, filesystem, clock, global state or authority/permission checks.
- Algorithms on data-holder types (config objects, assets, DTOs, ORM models); they hold data only.
- Static/global caches, singletons or `thread_local` scratch as hidden state of a computation.
- Resetting state by zeroing fields one by one; one context struct mixing input, result and scratch.
- An O(N) scan, retry or default after an O(1) index lookup misses (`no-masking.md`).
- Wall-clock limits or timing-dependent branches in anything that affects results.
- `is`/`can`/`has` queries that mutate state or log; undo by hand (`old = x; mutate; restore`).

## Must

- **Layers**: core (pure data + algorithms, unit-testable with no framework running) → orchestrator
  (owns the pipeline, threads, IO, authority, framework objects) → presentation/adapters. Dependencies
  point toward the core; the boundary talks to it via DTOs or interfaces.
- **State buckets**: `Config` (immutable input, validated once at the boundary) + `Output` (result) +
  `Transient` (scratch, attempt counters; reset as one `= {}`). Each field's bucket is documented.
- **Identity**: id == dense array index for the pipeline lifetime; lookups by id, grid or pair key
  are O(1) maps kept up to date incrementally; a miss is an explicit error. No mid-array erase
  without a remap.
- **Phases**: the pipeline is named steps, each with one owner, its input, its output and the thread it
  runs on (setup on the main thread → pure work on a pool → apply results in budgeted slices).
  Parallel work gathers locally and merges after the phase; no locks in loop bodies.
- **Determinism**: search and retry limits are iteration counts or quotas; wall-clock budgets only for
  presentation work that does not change results. Same seed/input → same output (checksum it).
- **Transactions**: rollback through a delta journal O(changes). Validation and range checks at the
  boundary; the core asserts instead of silently clamping.
- **Forbidden-first**: before implementing a system, write its Forbidden/Must list as a path-scoped
  rule (`.claude/rules/<system>.md`, `paths:` = its folders) with `Ref:` to its canon page.
- **Per-system docs**: a system entry `Docs/Systems/<system>.md` (entry points, layers, owners,
  files, how to verify), a canon page (the invariants above made concrete), an ADR per decision
  with alternatives rejected. Read them before changing the system; update them in the same commit
  as the change.

## New project or system, in order

1. Glossary of domain terms → 2. layers and folders → 3. state buckets and ids → 4. phase list with
threads → 5. path-scoped rules + canon + system entry → 6. core with tests before any adapter →
7. orchestrator → 8. presentation. Each step is one plan (`planning.md`) and one commit.
