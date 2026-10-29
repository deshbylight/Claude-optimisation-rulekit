---
name: handoff
description: Move a request that is unrelated to the current chat's task into a fresh chat with a small, request-specific context file. Run when the [TOPIC-GATE] or [LONG-SESSION] note says so, or when the user types /handoff.
---

Goal: the new chat starts at the baseline context plus only what the new request needs.
The old chat stays intact; it can be searched later with `python Tools/claude_session_grep.py`.

Do NOT read project files or run builds here. Work only from what is already in this chat.

1. Pick a short ASCII slug for the new request (`login-timeout`, `export-csv`).
   File: `.claude/handoff/<YYYY-MM-DD_HHMM>_<slug>.md` (keep `.claude/handoff/` gitignored).

2. Write the file, ≤ 50 lines, in this shape:

   ```
   # Handoff: <slug>
   ## Request
   <the task as it stands now (see "Request" below)>
   ## Relevant context from the previous chat
   - <only facts the new request needs: `path:line`, decisions + why, constraints,
     what was verified and how (build / tests / log line)>
   - <unfinished state that touches this area: uncommitted edits, known-bad hypotheses>
   (if nothing is relevant, write one line: "no context needed")
   ## Open problems
   - <each known problem in this area: what is broken or unverified, its evidence (`path:line`,
     log line, failing test), and hypotheses already ruled out and why>
   (always present; if none, write one line: "none known")
   ## Do not carry over
   <one line: what the old chat was about, so the new chat doesn't go there>
   ## Source
   Claude chat <session ID, or "ID unavailable">; `python Tools/claude_session_grep.py <id> --prompts`
   ```

   Rules: no summaries of the old task, no file dumps, no guesses — only facts established
   in this chat. Stale facts (superseded hypotheses, reverted edits) are left out.

   Request: the new task often grew over several turns (question → your proposal or
   clarifying question → a short answer like "both"). The last user line alone is then
   already answered and means nothing in a fresh chat. Write the task as agreed: the user's
   own words from every turn that shaped it (quoted), plus the options and decisions they
   accepted. Copy only the last line verbatim when it is self-contained. When the user listed
   items, keep every item with the user's numbering and a status (done + commit / open /
   unverified + the check that settles it); re-read the turn that listed them before writing.

3. Write the first message for the new chat to `.claude/handoff/<file>.prompt.txt`:

   ```
   <the task from "## Request", in the user's words where possible>

   Previous-chat context: .claude/handoff/<file>.md — read it first.
   ```
   Copy it to the clipboard: Windows `Get-Content -Raw -Encoding UTF8 '<file>' | Set-Clipboard`,
   macOS `pbcopy < '<file>'`, Linux `xclip -selection clipboard < '<file>'`.

4. Reply with two lines only: that this is a new area → new chat (paste), and the handoff path.
   Stop — don't start the new task here.

If the user then answers that it should stay here (or resends with a leading `+`), just do it in
this chat.
