---
description: Before staging, committing or any git command that changes the working tree, index or refs — scoped completion commit, staged-diff review, operations that need separate authorization
load: on-demand
---

# Git policy

## Forbidden without separate explicit authorization

`stash` (push/pop/drop) · `commit --amend` · `checkout` / `restore` / `reset` of tracked files ·
`clean` · `push` / `pull` / `merge` / `rebase` · `branch -D` / `tag -d` / `worktree remove` ·
publishing or history rewriting. Completion-commit authorization covers none of these, nor
committing another task's work. Never stash to get a clean baseline.

## Forbidden

- `git add .`, `git add -A`, `commit -a` in a tree that may hold other work.
- Interactive flags (`rebase -i`, `add -i`, `add -p`): the agent shell cannot answer them.
- `--no-verify` or any hook bypass; labelling an unverified checkpoint as done.
- A bare `@name` in commit/PR text unless it is a real login meant to be notified.

## Must

- Record `git status` and the index before the first edit; files dirty before you started are not yours.
- After an authorized task passes its checks, commit without asking again (read-only task or empty
  diff: no commit). The owner saying "leave it uncommitted" overrides this for that task.
- Stage task-owned paths only: `git add <path>…`. Before committing review `git diff --cached` and the
  full content of new files; a file that changed after review is reviewed again.
- A file holding both your edits and someone else's: stage your hunks only if they separate cleanly
  (`git apply --cached` on an extracted patch), else report it and leave it uncommitted.
- On `main`/`master`: create a task branch before the first commit.
- Message: English, imperative, says what changed and why. Report the hash and the checks that ran.
- Checks failed → report the blocker, no commit. Verification that lands later is a new commit,
  never an amend.
- Ending a turn with own uncommitted edits needs a stated reason: in progress, waiting for the owner,
  or a named blocker.

Read-only inspection (`status`, `diff`, `log`, `show`, `blame`, `ls-files`) is always allowed.
