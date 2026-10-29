# Fix log: why each piece exists

Every setting, hook and rule in the kit answers a failure observed in real Claude Code sessions.
This page keeps that history: the problem, why the fix has this shape, and what it fixes. Numbers
are measurements from session transcripts, not estimates; re-measure yours with
`Tools/ctx_stats.py`. Items marked *(pattern)* have been used in a stack-specific form and are
described in [Roadmap](Roadmap.md) / [Extending](Extending.md), not shipped as code.

## A. Baseline: what every call pays

**A1. `CLAUDE.md` as a short digest, detail in on-demand rules.**
Problem: domain rules, examples and history accumulated in `CLAUDE.md`; it is re-sent on every
model call of every chat, so a paragraph used once a week was paid thousands of times a day.
Why this shape: an L1 bullet states the law and names an `RR/` file; the agent reads the file only
when the trigger matches. Path-scoped rules cover folder-specific law.
Fixes: baseline size; also attention: a short L1 is followed more reliably than a long one.

**A2. Output style with `keep-coding-instructions: false`.**
Problem: the built-in coding instructions duplicated and sometimes contradicted `CLAUDE.md`
(e.g. generic advice on comments, summaries, git).
Why: a custom output style is the supported way to drop that block; `CLAUDE.md` carries the
project's version. Fixes: duplicate text in the baseline and conflicting instructions.

**A3. `includeGitInstructions: false` + `RR/git.md`.**
Problem: the built-in git section is generic; the project needed stricter rules (scoped staging,
no interactive flags, task branch on `main`, `@name` only for real logins).
Why: one source of git law instead of two partially overlapping ones.
Fixes: baseline size and ambiguous git behavior. Note: the `Bash` tool description still carries
its own git safety notes; they cannot be turned off.

**A4. `autoMemoryEnabled: false`.**
Problem: the auto memory file grew with unreviewed notes, loaded in every call, and some notes
contradicted rules.
Why: durable knowledge goes into rules and `Docs/`, where it is reviewed and loaded on demand.
Memory notes that mattered were moved into the matching rules.
Fixes: silent baseline growth and stale/conflicting "facts".

**A5. Deny unused tools.**
Problem: tool schemas are the largest fixed block in the baseline.
Why deny instead of "don't use": a denied tool's schema is not sent at all; an advisory rule saves
nothing. Measured: denying one shell tool cut first-call input 46,987 → 42,726 tokens.
Fixes: baseline size on every call. Full list and reasons: [Tools](Tools.md).

**A6. No subagents (`Agent` denied, custom agents removed).**
Problem: subagents each start a new full baseline, run their own call chains, and their results are
then re-sent in the parent on every following call. Delegated work was also harder to verify.
Why: inline work with check-in stops costs one context; the agent listing itself (~1.8k chars in a
bare repo) leaves the baseline too.
Fixes: multiplied cost and unreviewed delegated output.

**A7. `skillOverrides` (`off` / `name-only`), `enabledPlugins: {}`.**
Problem: dozens of skill and plugin descriptions sat in every call; process skills also
auto-triggered and added steps nobody asked for.
Why: `off` for skills never used, `name-only` for skills invoked by hand; process skills only on
`/<name>`. Fixes: baseline size and unrequested process overhead.

**A8. Hook-enforced phrases removed from `CLAUDE.md`.**
Problem: the same limit was written in L1, in a rule and in the hook message.
Why: when a hook blocks, its message reaches the model exactly when needed; the L1 copy is paid on
every call for nothing. L1 keeps one line or none.
Fixes: duplicated baseline text.

**A9. claude.ai connectors off (`disableClaudeAiConnectors: true`).**
Problem: an account-level connector added its MCP tool names to the deferred-tool list and its own
instruction block to every call of every repo, although no coding task used it. Measured: ~1.7k
tokens per call for one connector; the first kit release missed this key and started ~1.7k above
what the same settings reach with that key.
Why a setting, not deny entries: one key removes the connector's tools and instructions together,
including connectors added to the account later. Fixes: baseline size from account-wide add-ons.

## B. Growth: what each step adds

**B1. Read guard for the `Read` tool.**
Problem: full reads of 1000+ line source files, several per session, were the largest controllable
growth source; rules saying "read ranges" were ignored late in long chats.
Why a blocking hook: advice decays, an exit-2 block with a reason ("Grep first, then Read with
offset+limit") cannot be skipped. An explicit `limit` is the escape hatch, so a real need is one
parameter away. Fixes: per-read growth of thousands of lines.

**B2. Read guard extended to shell readers.**
Problem: after B1, the model switched to `cat`/`sed -n`/`Get-Content`; ~1,770 shell full-file
reads bypassed the guard in the measured period.
Why: the same thresholds for shell readers (whole file over 300 lines, slices over 120 lines);
piped/redirected output and temp/scratchpad paths pass because they do not land in context or are
the agent's own scratch files. Marker `RULEKIT_FULL_READ` for a deliberate full read.
Fixes: the bypass of B1.

**B3. Persisted tool output guard.**
Problem: `bashOutputMaxChars` sends long output to a file, then the model read the whole file
back, undoing the cap.
Why: block whole reads of `tool-results` dumps over 8k chars; Grep or ranged Read instead.
Fixes: the round-trip that defeated the output cap.

**B4. `Write` over a large existing file blocked.**
Problem: rewriting a 300+ line file sends the whole file as tool input and invites accidental loss
of unrelated code. Why: `Edit` sends only the changed region. Fixes: growth and silent deletions.

**B5. `bashOutputMaxChars: 5000`.**
Problem: build, test and search output landed in context in full.
Why: a cap with a preview keeps the head visible and the rest searchable on disk.
Fixes: single-call floods.

**B6. Wrappers instead of raw commands** *(pattern)*.
Problem: raw build output, raw log reads and identifier greps dominated shell output: grep alone was
20.8% of all Bash output; raw log reads outnumbered the log slicer ~3,300 to 171; raw identifier
greps outnumbered the symbol-lookup tool 4,760 to 80.
Why: a wrapper prints only errors / the matching slice / the definition; a PreToolUse hook routes
the raw command to the wrapper, because a wrapper the model does not use saves nothing.
Fixes: the largest repeated output sources. Lesson: a low wrapper share is an adoption problem
(hook or sharper rule), not a missing tool.

**B7. Batched lookups (≤3 parallel calls or one shell command).**
Problem: many tiny sequential calls, each re-sending the context. Why: one call with several
independent results pays one re-send; the cap keeps a batch from becoming a flood.
Fixes: call count on exploration.

## C. Session length

**C1. Long-session nudge (`claude_session_length.py`).**
Problem: sessions with ≥200 calls were few but carried ~75% of all input tokens (83 sessions).
Why: after many calls or ≥2 compactions, the model is told to recommend a fresh chat when the next
prompt starts a new step; it never hands off mid-edit/build/commit.
Fixes: the cost tail of runaway chats.

**C2. Nudge after a commit at large context.**
Problem: one chat ran 6 tasks back to back at a median ~147k context (~5× the cache-read volume of
fresh chats). Why: a finished, committed task is the cheapest moment to move on.
Fixes: task chaining in one chat.

**C3. Topic gate (`claude_topic_gate.py`) + skill `handoff`.**
Problem: unrelated requests in a large chat dragged the old context along.
Why: at ≥100k context the model first decides whether the prompt belongs to the current task;
if not, `handoff` writes a ≤50-line file with only the facts the new request needs. `+` overrides.
Fixes: paying for an unrelated context; also the model mixing two tasks.

**C4. Reply-language reminder hook (removed in 0.5.0).**
Problem: the chat language drifted back to English in long chats. Why: one injected line per
prompt is cheaper than a stronger L1 paragraph and does not decay. Fixes: language drift. Removed
from the kit: the default chat language is English, and a project that chats in another language
changes the `Chat language:` line (or keeps its own hook).

**C5. Cache TTL, compaction window, effort level.**
Why: 5-minute cache writes cost 1.25× base input vs 2× for 1-hour; work in bursts pays the
lower rate. A lower auto-compact window keeps each call cheaper. Medium effort avoids long hidden
thinking on routine steps. Fixes: per-call price without changing behavior. See [Cost](Cost.md).

## D. Working with code

**D1. Never invent API/paths/behavior: Grep/Read first.**
Problem: plausible but non-existent functions, flags and config keys; fixing them cost more than
looking them up. Why: a lookup is one cheap call; a wrong edit is a build, a revert and a retry.

**D2. Evidence labels; "built" ≠ "verified"; runtime state needs a check this session.**
Problem: "done" reported after a green build with untested behavior, or from a stale log.
Why: labels make the gap visible to the owner; the rule names the check that would settle it.
A Stop hook that asks for a build/test after source edits is the enforcing form *(pattern)*.

**D3. Approval before code edits; plan document for multi-file or non-trivial changes.**
Problem: large unrequested edits, plans with unchecked claims, the owner asked trivia.
Why: a short proposal costs one message; a plan is self-verified before approval, and only
key-logic choices go to the owner (`RR/planning.md`).

**D4. No masking + `Docs/Review/OpenDefects.md`.**
Problem: bugs "fixed" by a fallback, default, retry or default-off flag; several defects bundled
into one vague line and then forgotten.
Why: one report line and one fix item per defect; an open defect lives in a ledger until its
verified fix deletes the row (`RR/no-masking.md`).

**D5. Search before create.**
Problem: parallel implementations of existing helpers and hand-written versions of library
features. Why: project → frameworks → public prior art, with a license check (`RR/search.md`).

**D6. Minimal scope.**
Problem: drive-by refactors, renames and reformatting made diffs unreviewable and broke unrelated
code. Why: change only what the task requires; refactors are separate tasks.

**D7. Code beats comments.**
Problem: the model trusted a stale comment over the code. Why: believe the code, flag the comment.

**D8. Scoped completion commits; risky git operations need separate authorization.**
Problem: finished work stayed uncommitted, or `git add -A` swept in other tasks' edits; `stash`
and `checkout` destroyed someone's work-in-progress.
Why: standing authorization for scoped local commits, explicit authorization for anything that
rewrites, discards or publishes (`RR/git.md`). An ownership ledger that records which session
edited which path makes this provable with several agents in one tree *(pattern)*.

**D9. Shared workspace rules.**
Problem: concurrent builds overwrote each other's outputs; an agent "fixed" a compile error that
belonged to another task's unfinished change.
Why: wait for or isolate shared outputs, report foreign errors as blockers (`RR/shared-workspace.md`).

**D10. Review coverage.**
Problem: "looks good" after reading part of a diff. Why: per-file coverage and one evidenced line
per finding (`RR/review.md`).

**D11. Owner questions only via `AskUserQuestion`.**
Problem: questions buried at the end of long chat reports went unanswered or were answered
ambiguously. Why: a dialog with standalone options forces a concrete choice with named
consequences; the report stays in chat before it.

**D12. Expensive runs only when needed, with aim and duration stated.**
Problem: long test matrices and sweeps started for questions a single run answered.
Why: one line of intent lets the owner stop it; a hook can gate the largest runs *(pattern)*.

**D13. Owner contests a verified claim → re-check.**
Problem: the model agreed with any pushback, flipping correct answers. Why: re-run the check,
then answer with the evidence.

**D14. File language English, chat language free.**
Problem: mixed-language comments and docs. Why: files are read by tools, search and other people;
the chat is for the owner. CI flags non-English text (`Tools/check_kit.py`); a PreToolUse guard
on Edit/Write is the enforcing form: `claude_language_guard.py` blocks added non-English lines and
lets translations through, since the rule alone loses to a non-English chat.

**D15. Verify gate before the turn ends (`claude_verify_gate.py`).**
Problem: "done" after a source edit with no build or test at all; "green build = built, unverified"
lived only in prose. Why a Stop hook: it sees the whole turn (edit order vs successful verify
commands in the transcript) and blocks once per last edit, so it cannot loop. Fixes: unbuilt and
untested changes reported as finished.

**D16. Shell routes to wrappers (`claude_shell_guard.py`).**
Problem: raw builds, full log reads and repo-wide greps were the largest share of shell output
(measured: grep ~21% of all Bash output; raw log reads outnumbered the log wrapper ~20:1), even
with a rule naming the wrapper. Why a route table: the wrappers differ per project, the mechanism
does not; `RULEKIT_RAW` keeps an explicit escape. Fixes: context floods and late failures from raw
tool output.

**D17. Commit reminder (`claude_commit_reminder.py`).**
Problem: the rule-gap check after a fix and knowledge capture after a code change depended on the
model remembering a `CLAUDE.md` line at the end of a long task. Why PostToolUse on `git commit`: the
commit is the moment the change is final and its subject says whether it was a fix. Fixes: the same
class of bug coming back with no rule; lessons that stay only in a closed chat.

## E. The loop that produced this list

**E1. Rule gap check after every fix** (`RR/rule-authoring.md`).
Problem: the same class of mistake came back in new chats. Why: after a verified fix, ask whether
the root cause is a reusable class with no rule; place the fix at the cheapest level that fires.
A post-commit hook on `fix…` commits reminding of the check, a finder for the user's corrections
("wrong", "revert") and a finder for costly repeated tool use feed the loop *(pattern)*.

**E2. Measure before and after.** Every change above was kept only if `ctx_stats.py`,
`/context` or the transcripts showed it paid for itself; what stops paying is deleted.
