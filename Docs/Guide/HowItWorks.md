# How the rulekit works

## 1. Cost model

- Every model call re-sends the whole context: system prompt, tool schemas, `CLAUDE.md`, output
  style, skill descriptions, loaded rules and the entire conversation so far, including every tool
  result. Prompt caching makes repeats cheaper, not free.
- Therefore cost ≈ (fixed baseline + accumulated conversation) × number of calls. Two levers:
  1. **Baseline** — what loads before the first prompt. Paid on every call of every chat.
  2. **Growth** — what each step adds (large reads, verbose shell output, re-reads, long sessions).
- A line in `CLAUDE.md` is the most expensive text in the repository; a line in an on-demand rule
  costs nothing until read; a hook costs nothing at all unless it injects text.

Run `/context` in a fresh chat to see the baseline; run `python Tools/ctx_stats.py --last 15` to see
start context, mean/max context and growth per call across real sessions.

## 2. Layers

| Layer | Where | Loads | Holds |
|-------|-------|-------|-------|
| L1 digest | `CLAUDE.md` | always | Short, dense law that applies to every task; trigger lines pointing to L2 |
| L2 on-demand | `.claude/reference-rules/*.md` | when the agent reads it (named by an L1 trigger or another rule) | Detailed Forbidden/Must lists for one topic |
| L2 path-scoped | `.claude/rules/**/*.md` with `paths:` frontmatter | when the agent touches a matching file | Laws that belong to a folder or file pattern |
| L3 knowledge | `Docs/**` | only through search | Explanations, decisions, failure notes, examples |

Rules of thumb:

- L1 says *what* and names the L2 file; L2 says *how exactly*; L3 says *why* and *examples*.
- A `.claude/rules/` file without `paths:` loads in every session — it is an L1 cost hidden in L2.
- Every L1 bullet should be either a behavior the agent breaks without it, or a pointer.

## 3. Enforcement: rules vs hooks

Rules are advice the model may skip, especially late in a long chat. Hooks are scripts Claude Code
runs on events; they cannot be ignored.

| Need | Mechanism |
|------|-----------|
| Behavior that needs judgment (when to ask, how to report) | Rule |
| A mechanical limit (no whole-file reads, no raw build output) | PreToolUse hook that blocks with a reason |
| A reminder that decays over a long chat (reply language) | UserPromptSubmit hook that injects one line |
| A check before the turn ends ("edited code, did not build") | Stop hook |

Hook contract used in this kit (see the official Claude Code hooks documentation for the full schema):

- Input: one JSON object on stdin (`tool_name`, `tool_input`, `cwd`, `prompt`, `session_id`,
  `transcript_path`, depending on the event).
- PreToolUse: exit code 2 blocks the tool call; stderr is shown to the model as the reason, so the
  reason must say what to do instead.
- UserPromptSubmit: printing
  `{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "..."}}` adds that
  text to the model's context for this prompt.
- Every hook in this kit exits 0 on malformed input or unreadable files: a broken hook must never
  block the user.

## 4. Session hygiene

- `claude_topic_gate.py`: when the chat is already large and a new, unrelated request arrives, the
  model is told to move it to a fresh chat via skill `handoff` instead of dragging the old context.
- `claude_session_length.py`: after very many calls, several compactions, or a finished task at a
  large context, the model recommends a fresh chat.
- Skill `handoff` writes a ≤50-line context file with only the facts the new request needs and puts
  the first prompt on the clipboard. The old chat stays searchable with `claude_session_grep.py`.
- A `+` at the start of a prompt keeps the current chat.

## 5. Quality rules shipped in L1/L2

These target the failure modes that cost the most rework, independent of language or stack:

| Failure | Countermeasure |
|---------|----------------|
| Invented APIs, paths, library behavior | Contract: Grep/Read first; evidence labels |
| "Done" without proof | Build ≠ verified; runtime state is unverified until a check ran this session |
| Bugs hidden by fallbacks/retries/flags | `RR/no-masking.md` + `Docs/Review/OpenDefects.md` |
| Plans with unchecked claims, owner asked trivia | `RR/planning.md` |
| Reinventing existing mechanisms | `RR/search.md` |
| Unscoped edits, drive-by refactors | Approval before code edits; minimal scope |
| Rule sprawl | `RR/rule-authoring.md`: cheapest level that still fires |
| Lost or mixed work in git | Scoped commits of task-owned paths; risky git ops need authorization (`RR/git.md`) |
| Partial reviews reported as complete | `RR/review.md`: per-file coverage, one evidenced line per finding |
| Agents colliding in one checkout | `RR/shared-workspace.md` |

## 6. The improvement loop

1. Measure: `ctx_stats.py` (where context grows), `/context` (baseline), the chat itself (where the
   agent went wrong).
2. Classify the cause: a one-off, or a recurring class.
3. Recurring → the cheapest fix that fires (`RR/rule-authoring.md`): a bullet in an existing rule →
   a new on-demand rule → a path-scoped rule → a hook if the rule is still ignored → L1 only with
   the measured cost.
4. Measure again; delete what no longer pays for itself. The history of this loop: [Fix log](Fixes.md).
