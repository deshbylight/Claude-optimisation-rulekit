# Third-party skills and tools

What the kit takes from public repositories, what is used next to it, and what is suggested for
new projects. Checked against the upstream READMEs on 2026-10-29; re-check before relying on an
install command, flags move.

## What the kit ships

Everything in this repository is original kit code and text under the kit's [MIT license](../../LICENSE);
no third-party file is vendored. The `handoff` skill is the kit's own design (topic gate, ≤50-line
file under `.claude/handoff/`, fresh chat). `mattpocock/skills` has an unrelated skill with the same
name that writes a session summary for another agent: if you install both as project skills, rename
one folder; as a plugin, the upstream one is namespaced and both coexist.

## Skills used alongside the kit (not shipped)

Adapted copies of these MIT-licensed skills are used in projects that run the kit. They are not in
this repository; adopt them per project.

| Upstream | Skill | Purpose | Trigger |
|----------|-------|---------|---------|
| [mattpocock/skills](https://github.com/mattpocock/skills) | `engineering/diagnosing-bugs` | Disciplined loop for hard bugs and perf regressions: reproduce, hypothesise, test one variable, confirm | model |
| same | `engineering/grill-with-docs` (+ `productivity/grilling`, `engineering/domain-modeling`) | Interview that sharpens a plan before code and records resolved terms and decisions | user |
| same | `engineering/code-review` | Two-axis review: does the diff do what the spec asked, and does it follow the repo's standards | model |
| same | `engineering/wayfinder` | Plans work larger than one session as a map of decision tickets | user |
| [obra/superpowers](https://github.com/obra/superpowers) | brainstorming, writing-plans, executing-plans | Design doc → task plan → inline execution; specs and plans live in `docs/superpowers/{specs,plans}/` | user |

### Adopting one into a kit project

- Copy only the skill folders you need into `.claude/skills/`, plus the upstream `LICENSE` file
  (MIT requires the notice); start each `SKILL.md` body with `<!-- Adapted from <repo> <skill> (MIT) -->`.
- Installing a whole plugin (`claude plugin install …`) puts every skill description in every call
  and overrides the kit's `enabledPlugins: {}`. Copying selected folders keeps the baseline small.
- Make process skills user-invoked (`disable-model-invocation: true`) or set them to `"name-only"` in
  `skillOverrides`: the description leaves the per-call context, `/<name>` still works.
- Rewrite steps that clash with the kit: the kit denies `Agent`, so steps that dispatch subagents
  (superpowers `subagent-driven-development`, `dispatching-parallel-agents`) run inline or are
  dropped; commits follow `RR/git.md`; questions go through `AskUserQuestion`.
- Upstream setup skills that write their own config (`/setup-matt-pocock-skills`) are not needed:
  replace the files they would create with the kit's paths (`Docs/Review/`, `RR/`).
- After adding a skill: fresh chat, `/context`, compare the skills total with the kit baseline
  ([Cost](Cost.md)).

## Suggested for new projects: Graft (Trail-code)

[Trail-code](https://github.com/trailhq/Trail-Code), formerly Graft (`NanoNets/Graft`, npm
`@nanonets/graft`; the `graft` command still works), is an MIT, local code-graph layer for coding
agents. It builds a graph of the repository with tree-sitter and injects matching code pointers
(`file:line`, summaries, dependents of an edited file) into each prompt, so the agent re-explores
less. Its README reports 42% fewer tokens and 46% fewer tool calls on its own benchmark; that is a
vendor number, not measured with this kit.

It fits the kit's goal (less exploration per task) and has no hard conflict with it. It is not
installed by `install.py`, and it has not been tested together with the kit. Points to know:

| Area | Graft does | With the kit |
|------|-----------|--------------|
| `.claude/settings.json` | Merges hooks and a `statusLine`; never overwrites existing keys or `CLAUDE.md` | Coexists: both installers merge. The kit sets no `statusLine`. `install.py --uninstall` removes only the kit's hooks |
| Hooks | `SessionStart`, `UserPromptSubmit` (context injection), `PreToolUse` on Bash, `PostToolUse`, `Stop` | Run next to the kit's hooks; a block from either `PreToolUse` hook stops the call. The injected text adds to every prompt: measure it |
| Machine-wide writes | By default also writes hooks to `~/.claude/settings.json`, `~/.claude/helpers/`, and an MCP server to `~/.claude.json`, for every repository | Use `--no-global`: the kit keeps per-project behaviour in the project and machine settings explicit |
| MCP server `trail` (6 tools, `.mcp.json`) | Code search / call tracing tools | Tool schemas cost tokens on every call unless Claude Code defers them; `disableClaudeAiConnectors` does not cover `.mcp.json`. Check `/context` |
| Skill `.claude/skills/trail/` | One more skill description | Set it to `"name-only"` in `skillOverrides` if you call it explicitly |
| Telemetry | Anonymous usage pings on by default | `DO_NOT_TRACK=1` or `trail telemetry disable` |
| Requirements | Node 22.3+ (20.16 reported to work) | The kit itself stays Python-only; Graft is a separate dependency |
| `CLAUDE.md` | Not touched | Add one Context line naming its tools first, e.g. "Code lookups: `trail_find_code` before Grep" |

Install order: kit first (`install.py`, adaptation prompt), commit, then:

```
npm install -g @trailhq/trail-code
DO_NOT_TRACK=1 trail init --agents claude --no-global --dry-run
DO_NOT_TRACK=1 trail init --agents claude --no-global
```

Keep it only if it pays: compare `python Tools/ctx_stats.py --last 15` and a fresh chat's `/context`
before and after a week of normal work. Remove with `trail uninstall -y --no-global`.
