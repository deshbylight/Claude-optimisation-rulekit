---
description: Work too large for one chat (a new system, a migration, a multi-module feature) — split into stages that each fit one session, with a map file, one check and one commit per stage, and handoffs between chats
load: on-demand
---

# Splitting large work into sessions

A stage fits one session when it touches one subsystem or layer, needs ≤ ~15 files read, ends in one
check (build, test, log line) and one commit, and leaves the tree working. Bigger → split it.

## Forbidden

- Starting code for work of more than one stage without a map file.
- A stage that ends with the tree broken, a check skipped, or work uncommitted "for the next chat".
- Carrying the whole chat forward; a handoff restating what the map, plan or commits already hold.
- Changing an earlier stage's decision silently inside a later stage.
- Merging stages because the context still has room; splitting by file count instead of by owner.

## Must

- **Map** `Docs/plans/<topic>/MAP.md`: goal, out of scope, a stage table (id, scope, depends on,
  check, status `todo`/`doing`/`done <commit>`/`blocked <reason>`), decisions (id, choice, why),
  open questions (each one a stage or an owner question, never "later").
- **Order**: stages follow the layer order in `architecture.md` — glossary and contracts, core with
  tests, orchestrator, adapters, presentation. A stage depends only on `done` stages.
- **Per stage**: a plan (`planning.md`, `Docs/plans/_TEMPLATE.md`) when it is non-trivial; the
  check passes; one scoped commit; the map row → `done <hash>`; findings out of scope →
  `Docs/Review/OpenDefects.md` or a new stage.
- **Between stages**: a fresh chat. The `handoff` file names the map path, the next stage id, and
  only facts not already in the map, plans or commits.
- **Start of a stage**: read the map, the stage's plan and the system entries (`Docs/Systems/`) it
  names; re-check that `done` stages it depends on are still true (one check each).
- **Re-plan**: a stage that grows past one session is split in the map before more code is written;
  a decision that changes → new decision row and the stages it invalidates set back to `todo`.
