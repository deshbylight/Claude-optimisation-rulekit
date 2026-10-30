# Claude Code optimisation rulekit

A language- and project-agnostic starter set for Claude Code: a lean always-loaded `CLAUDE.md`,
on-demand rules, cost-control hooks and a handoff skill. Goal: a small per-call context and fewer
expensive failure modes (invented APIs, masked bugs, unscoped edits, runaway sessions).

Requirements: Claude Code, Python 3.9+ (`python` or `python3` on `PATH`; CI-tested on 3.9 and 3.12,
Linux and Windows), git. No third-party Python packages. License: [MIT](LICENSE).

## Quick start

Clone the kit once, next to your projects (it is not copied into them as a whole):

```
git clone https://github.com/deshbylight/Claude-optimisation-rulekit rulekit
python rulekit/install.py path/to/your-project --user
```

Then open Claude Code in your project and send:

```
Read .claude/rulekit/ADAPT.md and follow it.
```

That is the whole setup. Start a fresh chat afterwards and run `/context`: memory files should be
about the size of your `CLAUDE.md`.

### What the script does (mechanical, safe to re-run)

- Copies rules, hooks, the `handoff` skill, measurement tools and the adaptation prompt into the project.
- Merges `.claude/settings.json` without overwriting your keys: deny lists and hooks are unioned,
  a differing value of yours is kept and reported; the old file is saved as `settings.json.rulekit-bak`.
- `CLAUDE.md`: absent → written from `template/CLAUDE.md` with the detected stack and build/test
  commands; present → the template goes to `CLAUDE.rulekit.md` and the prompt merges it.
- Hook commands use `python` if it is a working Python 3, else `python3` (macOS/Linux).
- Windows with Git Bash: denies the `PowerShell` tool (~3.7k tokens per call); `--keep-powershell` keeps it.
- Extends `.gitignore`; writes `.claude/rulekit/manifest.json` (version, files, hashes).
- `--user` also merges `user/settings.json` into `~/.claude/settings.json` (backup kept).
- `--dry-run` prints the plan; `--force` overwrites kit files you changed (backups kept).
- An existing `settings.json` that is not plain JSON (comments) stops the script before any write.

### What the prompt does (judgment)

Fills the remaining placeholders from your README, manifests and CI; moves an old `CLAUDE.md` into
L1 / on-demand rules / path-scoped rules and lists where every section went; asks you only what it
cannot find in files; reports unverified commands and kept settings; commits the setup.
`.claude/rulekit/ADAPT.md` is read once on request and never loads on its own.

### Teams

Commit what the script and the prompt produced (`CLAUDE.md`, `.claude/`, `Tools/`, `Docs/Review/`, `Docs/plans/`).
Anyone who clones your project then gets the same setup with no install. `--user` settings are
per machine: each member runs `python rulekit/install.py <project> --user` once, or merges
`user/settings.json` by hand.

### Update

```
git -C rulekit pull
python rulekit/install.py path/to/your-project
```

New files and new settings keys are added; kit files you changed are kept and listed (`--force`
replaces them, backups kept); an adapted `CLAUDE.md` is never touched. Read `CHANGELOG.md` for
template changes worth copying into your `CLAUDE.md` by hand.

### Uninstall

```
python rulekit/install.py path/to/your-project --uninstall [--dry-run]
```

Removes kit files that are unchanged since install and the kit's hooks from `settings.json`. It
leaves `CLAUDE.md`, other settings keys and `.gitignore` entries and lists them for review.

## Manual install

1. Copy `template/CLAUDE.md` to the repository root as `CLAUDE.md`, and `.claude/`, `Tools/` and
   `Docs/Review/` and `Docs/plans/` into it; merge `user/settings.json` into `~/.claude/settings.json` (see below).
2. Fill the `<placeholders>` in `CLAUDE.md`; delete lines that do not apply.
3. Set `env.RULEKIT_VERIFY_RE` in `.claude/settings.json` to a regex of your build/test commands
   (verify gate) and add routes to `.claude/rulekit/shell-routes.json` if you have wrappers. Chatting
   in another language: change the `Chat language:` line of `CLAUDE.md`.
4. Add `.claude/handoff/` and `.claude/settings.local.json` to `.gitignore`. Optional: copy
   `.claude/settings.local.json.example` to `.claude/settings.local.json` for a safe allow list
   (read-only git, scoped `git add`/`commit`, the kit's tools) and `ask` on destructive git and `rm`.
5. Windows with Git Bash: add `"PowerShell"` to `permissions.deny` (one tool schema less on every
   call); keep it if PowerShell is your only shell. See [Tools](Docs/Guide/Tools.md).
6. Start a new chat and run `/context`: memory files should be the size of your `CLAUDE.md` only.

## Documentation

- [How it works](Docs/Guide/HowItWorks.md) — cost model, layers, rules vs hooks, improvement loop.
- [Extending](Docs/Guide/Extending.md) — adding rules, hooks, wrappers, skills; checklists.
- [Writing rules](Docs/Guide/WritingRules.md) — what a rule line must be, good/bad examples, compression.
- [Cost](Docs/Guide/Cost.md) — measuring and cutting cost; measured clean-repo baseline.
- [Tools](Docs/Guide/Tools.md) — disabled vs available tools and skills, and why.
- [Fix log](Docs/Guide/Fixes.md) — every fix behind the kit: problem, why this shape, what it fixes.
- [Third-party skills and tools](Docs/Guide/ThirdParty.md) — skills used alongside the kit and how
  to adopt them; Graft (Trail-code) as an optional code-graph layer for new projects.
- [Roadmap](Docs/Guide/Roadmap.md) — gaps and possible additions, by priority.
- [Example `CLAUDE.md`](examples/CLAUDE.md) — the template filled in for a fictional project.
- [Changelog](CHANGELOG.md).

## Layout

| Path | Loaded | Purpose |
|------|--------|---------|
| `template/CLAUDE.md` → your `CLAUDE.md` | every call | Layer 1 digest: the short always-apply law, Layer 2 trigger lines. The kit's own root `CLAUDE.md` is only for developing the kit |
| `.claude/output-styles/lean.md` | every call | `keep-coding-instructions: false` drops the built-in coding instructions; `CLAUDE.md` replaces them |
| `.claude/reference-rules/*.md` | only when read | Detailed rules named by `CLAUDE.md` (`RR/…`) |
| `.claude/rules/**` (yours) | when a file matching `paths:` is touched | Path-scoped project rules; a file without `paths:` loads always — avoid |
| `.claude/skills/handoff/` | name + description only, body on use | Moves a new topic into a fresh chat |
| `Tools/*.py` | never (hooks run outside the context) | Guards, nudges, measurement |
| `install.py`, `.claude/rulekit/ADAPT.md` | never / once on request | One-command install; the adaptation prompt; `manifest.json` records the installed version |
| `Docs/Review/OpenDefects.md` | only when read | Ledger for confirmed, not yet fixed defects |
| `Docs/plans/_TEMPLATE.md` | only when read | Plan skeleton for `RR/planning.md`; maps for `RR/decomposition.md` live next to it |
| `Tools/check_kit.py`, `Tools/tests/` | never | Kit CI: JSON, language, machine paths, private terms, links; hook tests |

## Settings (`.claude/settings.json`)

| Key | Why |
|-----|-----|
| `bashOutputMaxChars: 5000` | Long shell output is persisted to a file instead of landing in context |
| `outputStyle: "lean"` | See the output style above |
| `autoMemoryEnabled: false` | No automatically growing memory file in every call |
| `includeGitInstructions: false` | Built-in git prompt dropped; the git line in `CLAUDE.md` replaces it |
| `disableClaudeAiConnectors: true` | claude.ai connectors (MCP tools and their instructions) leave every call; measured ~1.7k tokens for one connector. Remove it if you use connectors in this repo |
| `skillOverrides` | Turns off built-in skills you do not use, so their descriptions leave the context |
| `permissions.deny` | Removes unused tools from the toolset. `Agent` (subagents) and `Glob` are denied on purpose: subagents multiply cost, `Glob` duplicates Grep/shell. Remove entries you need |
| `statusLine` | `Tools/ctx_usage.py` shows the current context size under the prompt (`ctx 20.5k/250k (8%)`), read from the transcript at no token cost. An existing `statusLine` is kept |
| `hooks` | See below |

## User settings (`user/settings.json`)

Machine-wide keys live in `~/.claude/settings.json` (Windows: `%USERPROFILE%\.claude\settings.json`),
not in the repository. Merge `user/settings.json` into that file; do not overwrite personal keys
(theme, editor mode, model, permission mode, update channel).

| Key | Why |
|-----|-----|
| `promptCacheTtl: "5m"`, `subagentPromptCacheTtl: "5m"` | A 5-minute cache write is cheaper than a 1-hour write (Anthropic pricing: 1.25× vs 2× base input, checked 2026-10). Pays off when you keep working in bursts; after a pause longer than 5 minutes the next call re-writes the cache. Use `"1h"` if you often step away mid-task |
| `modelSettings.<model>.autoCompactWindow` | Context size at which auto-compaction starts; lower = cheaper calls, more frequent compactions |
| `modelSettings.<model>.effortLevel: "medium"` | Less thinking per call on routine work; raise per task when needed |
| `skillOverrides` | `"off"` removes a built-in skill from the context; `"name-only"` keeps only its name (callable, near-zero cost). Skill names differ between Claude Code versions: check `/skills` and `/context` after upgrades |
| `enabledPlugins: {}` | No plugin descriptions or tools in the baseline |
| `feedbackDrafts: "notify"`, `agentPushNotifEnabled: false` | No feedback drafts or push notifications in the flow |

Verify after merging: a fresh chat's `/context` shows the skills and tool totals you expect.

## Hooks

| Script | Event | Effect | Knobs |
|--------|-------|--------|-------|
| `claude_read_guard.py` | PreToolUse Read/Write/Bash/PowerShell | Blocks whole-file reads over 300 lines / 40k chars, full reads of persisted tool output over 8k chars, shell slices over 120 lines, `Write` over an existing 300+ line file | constants at the top; `RULEKIT_FULL_READ` in a shell command bypasses it |
| `claude_topic_gate.py` | UserPromptSubmit | At ≥100k context, asks the model whether the new prompt belongs to this chat, else `handoff` | `RULEKIT_TOPIC_GATE_KTOK`, `RULEKIT_TOPIC_GATE_OFF` |
| `claude_session_length.py` | UserPromptSubmit | After ≥200 model calls, ≥2 compactions, or a `git commit` at ≥100k context: recommends a fresh chat | `RULEKIT_LONG_SESSION_CALLS`, `_COMPACTS`, `_CTX`, `_OFF` |
| `claude_shell_guard.py` | PreToolUse Bash/PowerShell | Routes raw commands (builds, log reads, broad greps) to the project's wrappers; routes in `.claude/rulekit/shell-routes.json`, empty by default | `RULEKIT_RAW` in a command bypasses; `RULEKIT_SHELL_GUARD_OFF` |
| `claude_language_guard.py` | PreToolUse Edit/Write | Blocks edits that add non-English lines to files (Markdown code spans and fences, locale files skipped); translating an existing line passes | `RULEKIT_FILE_LANG_SKIP` (path regex), `RULEKIT_FILE_LANG_GUARD=off` |
| `claude_commit_reminder.py` | PostToolUse Bash | After `git commit`: fix → rule-gap check (`RR/rule-authoring.md`); other source change → capture what it taught (system entry, ADR, failure log) | `RULEKIT_COMMIT_REMINDER_OFF` |
| `claude_verify_gate.py` | Stop | Source edited after the last successful build/test → once per edit, asks to run it or to say "not built" with the blocker | `RULEKIT_VERIFY_RE` (build/test commands; set by the installer from the detected commands, empty = off), `RULEKIT_SOURCE_RE`, `RULEKIT_VERIFY_GATE_OFF` |

A `+` at the start of a prompt tells both gates to stay in the current chat.

## Measurement tools

- `python Tools/ctx_stats.py --last 15` — per session: calls, start context, mean/max context,
  growth per call, compactions. `--breakdown <id-prefix>` splits the peak context by source.
- `Tools/ctx_usage.py` — the status line: context size of the last turn (lags one turn).
  The denominator is the model's `autoCompactWindow` (`modelSettings.<id>` or top-level, from user,
  project and local settings; `250k*` when none is set); `--window N` / `--model <id>` override it;
  `--transcript <file>.jsonl` for manual use.
- `python Tools/claude_session_grep.py <id> --prompts` / `<id> "<regex>"` — look into an old chat
  without loading it.

Both find transcripts from `CLAUDE_PROJECT_DIR` or the current directory; run them from the repo root.

## Extending

- Project knowledge goes to path-scoped `.claude/rules/` or on-demand `.claude/reference-rules/`,
  never to `CLAUDE.md` first; see `.claude/reference-rules/rule-authoring.md`.
- Repeated costly mistakes become hooks (advisory rules can be ignored, hooks cannot). Typical
  next hooks: route raw build/log commands to wrappers that print only errors; block "done" when
  source files changed and no build/test ran this turn.

## Checks

- `python Tools/check_kit.py` — JSON validity, English-only text, no absolute machine paths, links,
  rule frontmatter, and private terms from `.claude/kit-scan-terms.txt` (git-ignored) or
  `RULEKIT_SCAN_TERMS` (CI secret): list the names of the project you extracted rules from.
- `python -m unittest discover -s Tools/tests -v` — hook tests with synthetic payloads.

## Developing the kit

- The root `CLAUDE.md` is for working on the kit; the template users get is `template/CLAUDE.md`.
- New user-facing file → add it to `FILES` in `install.py` and a line to `CHANGELOG.md`.
- Before committing: `python Tools/check_kit.py` and `python -m unittest discover -s Tools/tests -v`;
  CI runs both on every push. Put the names of any private project you extract rules from into
  `.claude/kit-scan-terms.txt` (git-ignored) and, for CI, into the repository secret `RULEKIT_SCAN_TERMS`
  (comma-separated). The secret's value is never in the repository; CI findings name its terms
  by number only, because Actions logs of a public repository are public.
