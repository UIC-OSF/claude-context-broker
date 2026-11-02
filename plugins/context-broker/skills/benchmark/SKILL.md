---
name: benchmark
description: "Run a lightweight Context Broker estimate for a focused large-file question. Use when the user wants a quick indication of context savings before a full paired benchmark."
---

First search to identify one focused question and 1â4 relevant large files. Do not include likely-secret files. Then run:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/benchmark --question "<focused question>" --paths <file1> [<file2> ...]
```

Explain that the result estimates the reduction in source context returned to the primary Claude session. It is not a dollar-cost claim, model-token invoice, or quality evaluation. If the estimate is promising and the task is important, recommend the advanced `bench/` paired evaluation.
