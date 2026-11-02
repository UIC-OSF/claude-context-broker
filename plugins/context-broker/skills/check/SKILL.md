---
name: check
description: "Run a no-cost Context Broker health check. Use when the user asks whether the plugin is installed, ready, or working."
---

Run:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/check
```

Report only the result and any failed item. This exercises the hook scripts directly against fixtures (including known bypass shapes) and does not send repository source to a model. It confirms the scripts work, not that Claude Code has registered the hooks; to confirm registration, attempt a full Read of a file over the threshold in this session and expect a denial.
