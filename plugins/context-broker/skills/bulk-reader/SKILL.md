---
name: bulk-reader
description: "Use Context Broker for broad exploration: full files over the configured threshold, questions across three or more files, or large diffs. Verify consequential findings with targeted reads before editing."
---

Run the plugin command with a focused question and explicit paths:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/repo-read --question "<focused question>" --paths <file1> [<file2> ...]
```

Use the result as a map, not authority. For a change, read the cited source range directly and then reason, edit, and test normally.

Do not use this skill for architecture, debugging root cause, security/authorization decisions, or final review.
