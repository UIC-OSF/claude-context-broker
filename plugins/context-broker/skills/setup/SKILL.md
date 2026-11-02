---
name: setup
description: "Explain or validate Context Broker's zero-config and managed-worker modes. Use when the user asks to set up, configure, troubleshoot, or change Context Broker."
---

Context Broker works immediately after installation in zero-config mode. The default worker is a locked-down Claude CLI call: `haiku` model, no tools, one turn, no session persistence, no project or user settings, no MCP servers, run from an empty temporary directory, prompt delivered on stdin. It returns usage and cost. Verify with:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/check
```

Explain the tradeoff: zero-config reduces the primary session's context, but a flat Claude subscription may not reduce out-of-pocket cost, and the worker's own usage is real spend. For controlled or lower-cost team routing, set `CONTEXT_BROKER_WORKER` to an approved command that accepts the documented JSON worker protocol on stdin and writes `{ "answer": "...", "usage": {...}, "total_cost_usd": ... }` to stdout. That command runs in the developer's shell with the source corpus on stdin; treat it as code with repository write access would be treated.

Configuration (set in the project's Claude Code environment settings, never API keys):

- `CONTEXT_BROKER_MIN_LINES` (default 750): a Read or shell dump that would return more lines than this is denied.
- `CONTEXT_BROKER_MAX_FILE_BYTES` (default 768000) and `CONTEXT_BROKER_MAX_TOTAL_BYTES` (default 1000000): per-file and per-request ceilings for `repo-read`.
- `CONTEXT_BROKER_WORKER_MODEL` (default `haiku`): model for the default worker.
- `CONTEXT_BROKER_DISABLE=1`: turns the hooks off (used by the paired benchmark's baseline).
