# Measuring and cutting cost

[How it works](HowItWorks.md) explains the model: cost ≈ (baseline + accumulated conversation) ×
calls. This page is the practical side: what to measure, how to read it, which knob moves it.

## 1. Measure

| Question | Tool | Look at |
|----------|------|---------|
| What loads before my first prompt? | `/context` in a fresh chat | memory files, tools, skills, system prompt totals |
| How large are my sessions? | `python Tools/ctx_stats.py --last 15` | `start` (baseline), `mean`, `max`, `+/call`, `cmp` (compactions) |
| Short test sessions too | `ctx_stats.py --min-calls 1` | default skips sessions under 10 calls |
| What fills one session? | `ctx_stats.py --breakdown <id-prefix>` | share of tool results, attachments, rules; top re-read files |
| What did an old chat do? | `python Tools/claude_session_grep.py <id> --prompts` | prompts without loading the chat |
| Exact numbers of one headless run | `claude -p "<task>" --output-format json` | `usage`, `total_cost_usd` |

Context per call = `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` of one
assistant message. `start` is that value for the first call: your baseline.

## 2. Read the numbers

- **High `start`** → baseline problem: `CLAUDE.md`, rules without `paths:`, tool schemas, skill
  descriptions, plugins, MCP servers. Fix in settings and L1 (section 3).
- **High `+/call`** → growth problem: whole-file reads, long shell output, re-reads. `--breakdown`
  shows which tool dominates. Fix with hooks and wrappers (section 4).
- **High `calls` or `cmp ≥ 2`** → session problem: one chat doing many tasks. In measured real-world
  use, sessions with ≥200 calls were a minority but carried ~75% of all input tokens. Fix with
  fresh chats (section 5).

## 3. Cut the baseline

| Knob | Where | Effect |
|------|-------|--------|
| Short `CLAUDE.md`, detail in on-demand rules | repo | Paid on every call; each removed line saves on all future calls |
| `permissions.deny` for unused tools | `.claude/settings.json` | Each tool schema is re-sent on every call ([Tools](Tools.md)) |
| `skillOverrides: off / name-only` | settings | Removes skill descriptions; `name-only` keeps the skill callable |
| `enabledPlugins: {}`, no unused MCP servers | user settings | Plugin/MCP tools and instructions leave the baseline |
| `disableClaudeAiConnectors: true` | `.claude/settings.json` | claude.ai connectors' MCP tools and instruction blocks leave the baseline |
| `"PowerShell"` in `permissions.deny` (Windows with Git Bash) | `.claude/settings.json` | ~3.7k tokens: the largest single tool schema |
| `outputStyle` with `keep-coding-instructions: false` | `.claude/output-styles/` | Drops built-in coding instructions duplicated by `CLAUDE.md` |
| `includeGitInstructions: false` | settings | Drops the built-in git section; `RR/git.md` replaces it |
| `autoMemoryEnabled: false` | settings | No auto-growing memory file in every call |

## 4. Cut growth

| Knob | Effect |
|------|--------|
| `bashOutputMaxChars: 5000` | Long shell output goes to a file; the model sees a preview |
| `claude_read_guard.py` | Blocks whole reads of large files and persisted outputs; forces Grep + ranged Read |
| Wrappers for build/test/log commands | Print errors only instead of thousands of lines ([Extending](Extending.md)) |
| Batch independent lookups | One call with three results costs one re-send, three calls cost three |
| No subagents | Each subagent starts its own full baseline and its result lands in the parent anyway |

## 5. Cut session length

- One chat per task. After a task is committed at a large context, the next task in the same chat
  re-sends everything before it on every call. Observed: one chat ran 6 tasks at a median ~147k
  context, about 5× the cache-read volume of fresh chats.
- `claude_topic_gate.py` and `claude_session_length.py` tell the model to propose skill `handoff`;
  `+` at the start of a prompt overrides both.
- `/compact` keeps the chat but loses detail; a handoff file keeps exactly what the next task needs.

## 6. Cache and model settings

Prices are relative to the base input price of the model (Anthropic pricing docs, checked 2026-10):

| Item | Multiplier |
|------|-----------|
| Cache write, 5-minute TTL | 1.25× |
| Cache write, 1-hour TTL | 2× |
| Cache read | 0.1× for most models; lower on some current models (see the pricing page) |

- `promptCacheTtl: "5m"` (user settings): cheaper writes; pays off when you work in bursts. A pause
  over 5 minutes re-writes the whole context on the next call. Step away often mid-task → `"1h"`.
- `modelSettings.<model>.autoCompactWindow`: lower → cheaper calls, earlier compaction, more lost
  detail. Set it near the size where your sessions stop being productive anyway.
- `modelSettings.<model>.effortLevel: "medium"`: less hidden thinking on routine work; raise for a
  hard task. Thinking tokens are output tokens, the most expensive kind.
- Whether `promptCacheTtl` and `modelSettings` also work in project-level settings is not verified
  here; keep them in `~/.claude/settings.json`.

## 7. Verified baseline (clean repository)

Two fresh git repositories with the same 400-line Python file; one with the kit copied in, one
bare. Same user settings, same model, one headless run each with the task "Read big.py in full and
tell me the name of the last function":

| | bare | kit |
|--|------|-----|
| First-call context (tokens) | 22,440 | 15,525 |
| Second-call context | 26,998 | 15,848 |
| Run cost (USD) | 0.144 | 0.087 |
| How the file was read | whole file via Read | `grep` for definitions, per `CLAUDE.md` |

The kit's baseline is ~31% lower although it adds a ~5 KB `CLAUDE.md`: the denied tools, dropped
agent listing, built-in instructions and git section outweigh it. That run used kit 0.2.0 before
`disableClaudeAiConnectors` and with `PowerShell` allowed (Windows).

First-call context for a one-word reply with no tool calls, same machine and user settings:

| Configuration | Tokens |
|---------------|--------|
| Kit, `PowerShell` allowed, connectors on | 15,517 |
| Kit, `PowerShell` denied | 11,776 |
| Kit, `PowerShell` denied, `disableClaudeAiConnectors: true` | 10,083 |
| Larger setup (9 KB `CLAUDE.md`, same deny list incl. `PowerShell`, connectors off) | 11,932 |

On Windows the `PowerShell` schema alone is ~3.7k tokens and one claude.ai connector ~1.7k; both
outweigh any `CLAUDE.md` difference. Check `/context` and `ctx_stats.py --breakdown` for
`deferred_tools_delta` and `mcp_instructions_delta` attachments to find such blocks. A second run that forced a
whole-file Read got the guard's block message, so the hook works in real sessions. One sample per
side; repeat on your machine with your own user settings before quoting numbers.

Reproduce: `git init` two directories, run `python install.py <dir>` for one,
run the same `claude -p "…" --output-format json` in both, then `ctx_stats.py --min-calls 1` in each.
