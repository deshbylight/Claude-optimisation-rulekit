# Rulekit adaptation (run once after `install.py`)

You are adapting the rulekit to this repository. The installer already copied the files and merged
`.claude/settings.json`; your job is the part that needs judgment. Work inline, no subagents. This
task is authorized to edit `.md` files under the repo root and `.claude/`; it does not authorize
code changes.

## 1. Learn the project (cheap reads only)

- `ls` the root and the main source folders (2 levels); Read `README*`, the build manifest
  (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `CMakeLists.txt`, `*.csproj`, `*.uproject`,
  `Makefile`), CI config (`.github/workflows/*`, `.gitlab-ci.yml`) and `CONTRIBUTING*` — ranged reads.
- Existing agent instructions: `CLAUDE.md`, `CLAUDE.rulekit.md` (new template, if CLAUDE.md
  existed), `CLAUDE.local.md`, `AGENTS.md`, `.cursorrules`, `.github/copilot-instructions.md`,
  `.claude/rules/**`.
- Collect: what the project is, stack, entry points, the real build/test/lint commands (from CI
  first), where logs go, and architecture invariants stated in docs or obvious from code
  (e.g. "all DB writes go through X", "money is integer cents").

## 2. Fill `CLAUDE.md`

- No `CLAUDE.rulekit.md`: fill every remaining `<placeholder>` in `CLAUDE.md`; delete lines that do
  not apply. The `Stop and ask on high risk` list names this project's real risky areas
  (migrations, public API, save/serialization formats, protocol, build system…).
- `CLAUDE.rulekit.md` exists: the template becomes the new `CLAUDE.md`. Carry over from the old
  `CLAUDE.md` every project fact and rule that is still true:
  - short, always-relevant facts → Layer 1 / the header lines;
  - topic detail (a section about one subsystem, workflow or tool) → `.claude/reference-rules/<topic>.md`
    in the kit's rule format (frontmatter `description` + `load: on-demand`, then Forbidden / Must),
    plus one Layer 2 trigger line;
  - folder-specific law → `.claude/rules/<name>.md` with `paths:` frontmatter;
  - history, explanations, examples → `Docs/`.
  Nothing is dropped silently: list every old section and where it went in the report. Then delete
  `CLAUDE.rulekit.md`.
- `.claude/rules/*.md` without `paths:` load in every session: propose `paths:` or a move to
  `reference-rules/` (do it when the scope is obvious, ask otherwise).
- Never invent: a command or invariant you could not find in files is left as a question, not
  guessed. Do not run a full build or test suite to check a command unless it is quick; say which
  commands are unverified.
- Budget: `CLAUDE.md` ≤ ~6 KB; each new rule body ≤ ~40 lines. Placement and shape:
  `.claude/reference-rules/rule-authoring.md`. Density: one clause per idea, numbers instead of
  adjectives, no motivation prose (that goes to `Docs/`), nothing a hook already enforces.

## 3. Settings review

- Read `.claude/settings.json`. The installer kept existing values that differ from the kit's
  suggestion; it printed them as `kept …`. Mention them in the report, do not change them.
- Tools in `permissions.deny` that this project actually uses (notebooks → `NotebookEdit`,
  worktrees → `EnterWorktree`/`ExitWorktree`, subagents → `Agent`): ask before removing the entry.
- Optional, ask once if relevant: chat language (`env.RULEKIT_REPLY_LANG`), claude.ai connectors
  needed in this repo (`disableClaudeAiConnectors`).

## 4. Questions

Collect everything you could not settle from files (invariants, risky areas, unknown commands,
deny entries) and ask in one `AskUserQuestion` call, ≤4 questions, each standalone with concrete
options. Apply the answers.

## 5. Finish

- Validate: `python -c "import json; json.load(open('.claude/settings.json'))"`.
- Report in chat: what was filled, where each old section went, unverified commands, kept settings,
  open questions. Then tell the owner to start a fresh chat and run `/context` (memory files ≈ the
  size of `CLAUDE.md`), and later `python Tools/ctx_stats.py --last 15` to compare sessions.
- Git: if this is a git repository and the owner did not say otherwise, commit only the files the
  installer and you created or changed (`git add <paths>`; see `.claude/reference-rules/git.md`),
  message `chore: install and adapt rulekit`. Report the hash.
