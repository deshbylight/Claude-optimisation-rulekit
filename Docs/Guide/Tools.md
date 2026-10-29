# Tools and skills: disabled and available

Every tool the model can call has a schema (name, description, parameters) that is re-sent on every
model call, used or not. Every skill has a description in the context for the same reason. The kit
removes what a terminal coding workflow does not use. Tool names differ between Claude Code
versions: check `/context` after upgrades and adjust `permissions.deny`.

## Disabled tools (`.claude/settings.json` → `permissions.deny`)

| Tool | Why it is off | Turn it back on when |
|------|---------------|----------------------|
| `Agent` | A subagent starts with its own full baseline and its own tool calls; the parent then re-sends the subagent's result on every following call. Multiplies cost, and the work is harder to review. Planning and bulk text run inline with check-in stops | You run large, independent, parallel jobs and accept the cost |
| `SendMessage`, `ListAgents` | Only meaningful with subagents/agent teams | `Agent` is on |
| `Glob` | Duplicates `Grep` (file lists with a glob filter) and shell `ls`/`find`; one schema less | Your shell has no `find`/`ls` |
| `NotebookEdit` | No Jupyter notebooks in a typical repo | You edit `.ipynb` files |
| `EnterWorktree`, `ExitWorktree` | Switch the working directory to another checkout; worktree operations need explicit authorization under `RR/git.md` | You isolate parallel tasks in worktrees on purpose |
| `Artifact`, `DesignSync` | Publish or sync rendered output outside the terminal; outward-facing and unused in coding | You publish artifacts or design files |
| `SendFeedback` | Sends text to an external service; outward-facing | Never needed by the agent |
| `Workflow` | Workflow authoring/automation, not part of coding tasks | You build Claude Code workflows |
| `ScheduleWakeup`, `CronCreate`, `CronDelete`, `CronList`, `RemoteTrigger` | Background scheduling and remote triggers: an agent acting later without the owner watching | You run scheduled agent jobs |
| `PushNotification` | Notifications outside the chat | You want phone/desktop pushes |
| `ReportFindings` | A separate findings channel; the kit wants findings in the chat report and owner questions in `AskUserQuestion` | Your review flow consumes it |

### PowerShell (Windows)

The kit does **not** deny `PowerShell`, because on Windows without Git Bash it may be the only
shell. If `Bash` works for you on Windows (Git Bash installed), add `"PowerShell"` to the deny list:
measured, that alone cut the first-call input from 46,987 to 42,726 tokens (tool
schemas 104,459 → 86,517 chars). The read guard's matcher keeps `Bash|PowerShell`, so it guards
whichever shell stays on. On macOS/Linux the tool does not exist and the entry is harmless.

## Available tools

| Tool | Used for | Kit constraints |
|------|----------|-----------------|
| `Read` | Reading files, images, PDFs | Ranged reads (offset/limit) for files over 300 lines; enforced by the read guard |
| `Grep` | Content search | First step before any Read |
| `Edit` | Exact replacements | Preferred over `Write` for existing files |
| `Write` | New files, full rewrites of small files | Rewrite of a 300+ line file blocked → use Edit |
| `Bash` (and `PowerShell` if kept) | Builds, tests, git, scripts | Output over 5,000 chars persists to a file; whole-file `cat`/`sed` of large files blocked |
| `AskUserQuestion` | Every question that needs the owner's answer | Only channel for questions; the full report goes into chat first |
| `Skill` | Running a skill | Process skills only when the user types `/<name>` |
| `ToolSearch` | Loading schemas of deferred tools on demand | Deferred tools cost only their name until loaded |
| `WebSearch`, `WebFetch` | Docs and prior art (`RR/search.md`) | Deferred; load when needed |
| `EnterPlanMode`, `ExitPlanMode` | Plan mode | Deferred |
| `Monitor`, `TaskStop` | Watching / stopping background commands | Deferred; no sleep/poll loops |

## Skills

User-level `skillOverrides` (`user/settings.json`):

- `"off"`: the skill is gone from the context and cannot be called. Used for document, office,
  browser, scheduling, memory, setup and authoring skills that a coding repo does not need.
- `"name-only"`: only the name stays; the skill can still be called by name at near-zero cost. Used
  for skills you invoke rarely by hand (planning, debugging, review process skills, `docx`).
- Project-level overrides (`.claude/settings.json`) hide built-in skills for this repo only.

Kept and shipped: `handoff` (`.claude/skills/handoff/`) — moves a new topic into a fresh chat with
a small context file. Its description is the only skill text in the kit's baseline.

Process skills (brainstorming, planning, debugging, review) are `name-only` and run only when the
user types `/<name>`: an auto-triggered process skill loads its whole body and usually adds steps
the task did not ask for.

## Settings that remove built-in text

| Setting | Removes |
|---------|---------|
| `outputStyle: "lean"` (`keep-coding-instructions: false`) | Built-in coding instructions; `CLAUDE.md` replaces them |
| `includeGitInstructions: false` | Built-in commit/PR section. The `Bash` tool description keeps its own git safety notes; that part cannot be removed |
| `autoMemoryEnabled: false` | Auto memory file and its instructions |
| `enabledPlugins: {}` | Plugin tools, skills and instructions |
| `disableClaudeAiConnectors: true` | claude.ai connectors: their MCP tool names in the deferred list and their instruction blocks (~1.7k tokens for one connector) |
