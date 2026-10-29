#!/usr/bin/env python3
"""UserPromptSubmit hook: re-assert the chat reply language on every prompt.

When rules and files are English but the owner chats in another language, long or compacted
sessions drift into English chat replies. One short line per prompt keeps the preference in
recent context.

Config: env RULEKIT_REPLY_LANG (e.g. "Russian", set in .claude/settings.json -> env).
Unset or empty: the hook does nothing.

Wired in .claude/settings.json -> hooks.UserPromptSubmit.
"""
import json
import os
import sys

LANGUAGE = os.environ.get("RULEKIT_REPLY_LANG", "").strip()
REMINDER = ("Reply to the user in {lang} (including the final task report and "
            "build/commit summaries). English applies only to text written into files.")


def main() -> int:
    if not LANGUAGE:
        return 0
    json.dump({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                      "additionalContext": REMINDER.format(lang=LANGUAGE)}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
