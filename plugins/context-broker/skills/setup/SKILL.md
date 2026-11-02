---
name: setup
description: "Explain or validate Context Broker's zero-config and managed-worker modes. Use when the user asks to set up, configure, troubleshoot, or change Context Broker."
---

Context Broker works immediately after installation in zero-config mode. It invokes the locally authenticated Claude CLI with the `haiku` model for bulk exploration. Verify prerequisites with:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/check
```

Explain the tradeoff: zero-config reduces the primary session's context, but a flat Claude subscription may not reduce out-of-pocket cost. For controlled or lower-cost team routing, set `CONTEXT_BROKER_WORKER` to an approved command that accepts the documented JSON worker protocol on stdin and writes `{ "answer": "..." }` to stdout.

The default threshold is 750 lines. To change it for one project, add `CONTEXT_BROKER_MIN_LINES` to that project's Claude Code environment settings. Do not put API keys in project files.
