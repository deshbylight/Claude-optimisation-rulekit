# Extending the rulekit

Decide the level first (`.claude/reference-rules/rule-authoring.md`): bullet in an existing rule →
on-demand rule → path-scoped rule → hook → `CLAUDE.md`. Each step down this list costs more context
or maintenance.

## Add an on-demand rule

1. Create `.claude/reference-rules/<topic>.md`:

   ```markdown
   ---
   description: <operations and identifiers an agent will see in the task, not a topic label>
   load: on-demand
   ---

   # <Topic>

   ## Forbidden

   - <what> in <where>; verify with <check>.

   ## Must

   - <what> in <where>; verify with <check>.
   ```

2. Add one trigger line to `CLAUDE.md` → "Layer 2 — task triggers":
   `- <When the task does X>: RR/<topic>.md.`
3. Keep the body ≤ ~40 lines / ~1.5 KB; move explanations to `Docs/`.

## Add a path-scoped rule

1. Create `.claude/rules/<area>/<topic>.md` with the narrowest glob:

   ```markdown
   ---
   paths:
     - "src/payments/**"
   ---

   # Payments

   ## Forbidden
   - ...
   ```

2. Never `**/*` or "all source files": that is an always-loaded rule.
3. Check that the glob matches real files (`git ls-files "src/payments/**"`).

## Add a hook

1. Write `Tools/<name>.py`. Skeleton for a blocking PreToolUse hook:

   ```python
   #!/usr/bin/env python3
   """PreToolUse hook (Bash): <what it blocks and why>.

   Escape hatch: put RULEKIT_<NAME>_OK in the command.
   Wired in .claude/settings.json -> hooks.PreToolUse.
   """
   import json
   import sys

   MARKER = "RULEKIT_<NAME>_OK"


   def main() -> int:
       try:
           data = json.load(sys.stdin)
       except ValueError:  # malformed payload: never block the tool call
           return 0
       command = str((data.get("tool_input") or {}).get("command", ""))
       if MARKER in command or not <condition>(command):
           return 0
       sys.stderr.write("<what is wrong> -> <what to run instead>\n")
       return 2


   if __name__ == "__main__":
       sys.exit(main())
   ```

2. Wire it in `.claude/settings.json` under the right event and `matcher` (tool name regex).
3. Requirements for every hook:
   - exits 0 on any malformed input or I/O error;
   - finishes well under its `timeout` (read transcript tails, not whole files, when they can be large);
   - the block message names the alternative, otherwise the model retries the same call;
   - has an escape hatch marker or env switch;
   - matches real launches, not mentions (a `grep build.sh` must not count as running `build.sh`).
4. Smoke-test with synthetic payloads before relying on it:
   `echo '{"tool_name":"Bash","tool_input":{"command":"..."}}' | python Tools/<name>.py; echo $?`

## Add a wrapper tool

When the agent repeatedly runs a command whose raw output floods the context (builds, test runners,
log readers), write a wrapper that prints only errors and the result, then add a PreToolUse hook that
routes raw calls to it. Without the hook, adoption stays low. The kit's `Tools/claude_shell_guard.py`
is that hook: add one route per wrapper to `.claude/rulekit/shell-routes.json`, for example

    {"routes": [{"match": "(^|[;&|]\\s*)make\\s+build\\b", "say": "run `python scripts/build.py`"}]}

`unless` (optional regex) lets matching commands through, e.g. ones already piped into `grep`.

Wrapper checklist: `--help`, clear errors on bad input, bounded output, a stable exit code contract,
configuration constants at the top of the script.

## Add a skill

- `.claude/skills/<name>/SKILL.md` with `name` and `description` frontmatter. The description is in
  every call's context; the body loads only when the skill runs.
- Add `disable-model-invocation: true` for skills the user starts manually (`/<name>`): then the
  model does not pick them by itself.
- Disable unused built-in skills in `settings.json` → `skillOverrides`.

## Change `CLAUDE.md`

- Only for behavior that applies to nearly every task and is broken without it.
- Measure before and after with `/context`; state the token cost in the commit message.
- Edit only the bullets the lesson touches; never "condense" the whole file in one pass.

## After any extension

- Run the hook smoke tests and `python -c "import json; json.load(open('.claude/settings.json'))"`.
- Start a fresh chat, check `/context`, then try one task that should trigger the new rule or hook.
- A week later: `python Tools/ctx_stats.py --last 15` — did start context or growth change?
