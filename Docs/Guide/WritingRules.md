# Writing and compressing rules

A rule is paid for every time it loads: `CLAUDE.md` on every model call, a path-scoped rule on every
call after a matching file is touched, an on-demand rule after it is read. Write the shortest text
that still changes behavior, and put it at the cheapest level that still fires
(`.claude/reference-rules/rule-authoring.md` has the placement ladder).

## What a rule line must be

Each line is either a **behavior the agent gets wrong without it** or a **pointer** to where the
detail lives. Anything else (background, motivation, history, examples) belongs in `Docs/`.

| Keep | Cut |
|------|-----|
| An observable action: "Read with offset/limit" | A value: "be careful with context" |
| A concrete trigger: "before staging" | A vague scope: "when appropriate" |
| The exception that people hit: "piped reads pass" | Every exception you can imagine |
| The command to run: `python Tools/ctx_stats.py` | A description of what the command does |
| One wording, once | The same law restated in L1, L2 and the hook message |

## Good / bad examples

**Vague → actionable**

Bad:
```
- Be careful not to waste context when reading files.
```
Good:
```
- Grep before Read; Read with offset/limit (40–120 lines), never whole files over 300 lines.
```
The good line names the tools, the numbers and the threshold; it can be checked against a transcript.

**Explanation → law + pointer**

Bad (in `CLAUDE.md`):
```
- We had several incidents where a retry loop hid a race in the upload worker, and a default value
  made a broken config look valid, so please never paper over errors; instead report them, and keep
  a list somewhere so they are not forgotten.
```
Good (in `CLAUDE.md`):
```
- No masking: each confirmed bug = own report line and own fix item; never a fallback/default/
  skip/retry as the fix (`RR/no-masking.md`).
```
The incidents go to a `Docs/` failure note; the detailed Forbidden/Must list goes to the on-demand rule.

**Hook-enforced text → removed**

Bad:
```
- Never Read a file over 300 lines whole; never cat it either; never sed more than 120 lines; ...
```
Good: one short L1 line plus the hook. When a hook blocks the action, its stderr tells the model
what to do at the moment it matters; repeating the full list in L1 pays for it on every call.

**Description that never triggers → description that does**

Bad frontmatter:
```
description: Guidelines for database work
```
Good:
```
description: Before writing an Alembic revision or changing a SQLAlchemy model — revision order,
  data migrations, downgrade, locking on large tables
```
The agent decides to read an on-demand rule from its description. Name the operations, file types
and identifiers it will see in the task, not the topic.

**Rule without `paths:` in `.claude/rules/` → scoped or moved**

Bad: `.claude/rules/testing.md` with no frontmatter (loads in every session).
Good: `paths: ["tests/**", "**/*_test.py"]`, or move it to `.claude/reference-rules/` and add a
Layer 2 trigger line.

## Compression techniques

- **Symbols over sentences**: `→` for "then/leads to", `=` for "counts as", `·` as a list separator,
  `/` for alternatives. Keep them consistent across files.
- **One clause per idea**, no connective prose ("Note that", "It is important to", "Please").
- **Numbers instead of adjectives**: "≤3 parallel calls", "over 300 lines", "≥100k tokens".
- **Merge duplicates**: when two rules say the same thing, keep it in one and point from the other.
- **Name the failure in the description, not the body**: the description is read to decide; the
  body is read only after that decision.
- **Size budget**: a new on-demand rule body ≤ ~40 lines / ~1.5 KB. Bigger → split by trigger.

## Where text goes

| Text | Place |
|------|-------|
| Applies to every task, breaks without it | `CLAUDE.md` Layer 1, one bullet |
| Applies to one topic, needs a list | `.claude/reference-rules/<topic>.md` + one Layer 2 trigger line |
| Applies to a folder or file pattern | `.claude/rules/<name>.md` with `paths:` |
| Mechanical limit the model keeps breaking | A hook; L1 keeps one line or nothing |
| Why, history, examples, measurements | `Docs/` |

## Rules by code module

Project knowledge follows the code's decomposition (`.claude/reference-rules/architecture.md`), so
a task loads the rules of the module it touches and nothing else.

- **One path-scoped rule set per system**: `.claude/rules/<system>/<topic>.md`, `paths:` = that
  system's folders or file patterns (`src/billing/**/*.py`, `**/*Parser*.{h,cpp}`). Split a
  system's rules by topic (state, hot path, identity), each with targeted globs, instead of one file
  that matches the whole tree.
- **Glob audit**: a rule whose glob matches every source folder is a baseline cost on every file
  touch; narrow it, or move it to `CLAUDE.md` if it really is project-wide law.
- **Canon page per system** (`Docs/<system>/Canon.md`): the invariants in prose, with the why. Each
  rule has `Ref: <canon path>` in its frontmatter; the rule is the enforcement digest, the canon the
  explanation. Decisions → `Docs/Decisions/ADR-NNN-<topic>.md` (problem, decision, alternatives
  rejected); the canon links them.
- **System entry per system** (`Docs/Systems/<system>.md`): entry points, layers, owners, files,
  how to verify. `CLAUDE.md` Layer 1 says "before changing a system, read its system entry"; it
  does not list the systems.
- **Nested `CLAUDE.md`** (`src/<system>/CLAUDE.md`) loads when Claude reads files in that folder. Use
  it only for a self-contained subtree with its own build or language; otherwise prefer path-scoped
  rules, which load per file pattern rather than per folder.
- **Generated index** (optional): a script that lists, per source folder, which rules match it,
  catches dead globs and blanket rules; run it in CI.

## Review checklist before committing a rule

1. Does a failure in a real chat motivate it? Name it in the commit message.
2. Is there an existing rule it should extend instead?
3. Is it at the cheapest level that still fires?
4. Can every line be checked against a transcript?
5. Is anything in it also enforced by a hook? Delete that part.
6. `python Tools/check_kit.py` passes; `/context` in a fresh chat shows the expected baseline.
