---
name: check
description: "Run a no-cost Context Broker health check. Use when the user asks whether the plugin is installed, ready, or working."
---

Run:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/check
```

Report only the result and any failed prerequisite. This check does not send repository source to a model and does not invoke a worker.
