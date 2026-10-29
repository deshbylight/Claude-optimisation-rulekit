---
description: Several chats or agents working in one checkout — overlapping dirty files, shared build outputs, logs and generated artifacts, another task's processes
load: on-demand
---

# Shared workspace

## Forbidden

- Reverting, restoring or overwriting another task's changes to get a clean baseline.
- Two builds or test runs writing the same output directory, or runs sharing one writable log/report.
- Killing another task's process, messaging other chats or publishing without owner authorization.
- Editing a file to fix an error that belongs to another live task's unfinished change.

## Must

- Inspect `git status` and the index at the start; treat files dirty before your first edit as foreign.
- Re-read a shared file right before a narrow edit; never patch from a stale read.
- Wait for a busy build/output to finish, or use real isolation (separate checkout or worktree when
  authorized). Different log file names do not isolate shared binaries.
- One foreground build/test call that waits on its own lock; no sleep/poll loops around it.
- Unique run IDs, log names and report directories per task; re-check a generated report's timestamp
  after edits settle before citing it.
- A failing build or test whose error sits in a file another task is changing: report it as the
  blocker with the file and error line instead of editing that file.
- Stage only owned paths/hunks and keep pre-existing staged changes (`RR/git.md`).
