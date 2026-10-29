---
description: Rule authoring — after a fix, check rule coverage; write or extend the cheapest rule that still fires; keep context cost low (on-demand by default)
load: on-demand
---

# Rule authoring — bug fix → coverage gap → rule

Read this after a fix (bug, review finding, user correction) and before writing or editing a rule
(`.claude/rules/`, `.claude/reference-rules/`) or `CLAUDE.md`.

## 1. Gap check (after the fix is verified)

Write nothing unless **all** hold:

- The root cause is established (code, log, library source), not guessed.
- The cause is a **class** that can recur in another file, system or session — not a one-off typo.
- An agent would plausibly repeat it: the trap is non-obvious from the code at the edit site.

Search before writing: Grep `.claude/rules/`, `.claude/reference-rules/` and `CLAUDE.md` for the key
identifiers and the symptom.

| Finding | Action |
|---------|--------|
| A rule covers it, was loaded, and was still broken | Make the bullet concrete and checkable; if the slip is costly or recurs, enforce it with a hook or check script (rules are advisory, hooks are not) |
| A rule covers it but did not load | Fix routing: narrow/correct `paths:`, sharpen `description`, add a Layer 2 trigger line. No new text |
| A rule covers it partly | Add one bullet to that rule |
| Nothing covers it | New rule — placement below |

## 2. Placement — cheapest level that still fires when needed

1. **Bullet in an existing rule** — default.
2. **New on-demand rule** in `.claude/reference-rules/` (`load: on-demand`) plus a Layer 2 trigger
   line in `CLAUDE.md`. Costs context only when read.
3. **New path-scoped rule** in `.claude/rules/` with `paths:` frontmatter — only when the law belongs
   to a folder or file-name pattern. Use the narrowest folder, never `**/*`.
4. **`CLAUDE.md` Layer 1** — never by the agent. Propose it to the owner with the measured cost:
   it is re-sent on every model call of every chat.

## Forbidden

- A new rule when an existing one can take a bullet; two rules saying the same thing.
- Broad globs, or a glob added "so it is not missed" — a missed on-demand rule is fixed by its
  `description` and trigger line.
- Incident narrative: dates, who broke it, how it was debugged. That belongs in the commit message.
- A global ban from one case; generalize only as far as the established cause reaches.
- Rewriting or "condensing" an existing rule as a whole — edit only the bullets the lesson touches;
  whole rewrites silently drop earlier lessons.
- Encyclopedia in a rule: framework basics, rationale essays, long examples.

## Must

- **Size:** a new rule body ≤ ~40 lines / ~1.5 KB.
- **Shape:** frontmatter (`description`, `load` or `paths`), then Forbidden, then Must. Each bullet =
  what + where (exact identifiers, paths) + how to verify (test, log tag, check script).
- **Description** is the trigger: name the operations and identifiers an agent will see in the task,
  not a topic label.
- Separate library/framework behavior from project policy; library claims cite its source or docs.
- English prose; exact identifiers as-is.
- Commit it separately from the code fix and name the rule plus the one-line reason in the report.
