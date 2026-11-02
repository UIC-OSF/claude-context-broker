---
name: benchmark
description: "Run a quick Context Broker screening estimate for one focused large-file question. Reports a summary compression ratio and the worker's cost; not a savings claim."
---

First search to identify one focused question and 1-4 relevant large files inside the project. Then run:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/benchmark --question "<focused question>" --paths <file1> [<file2> ...]
```

Report the numbers as what they are: the worker summary's size compared with what a capped Read (2,000 lines per file) would have put into the primary context, plus the worker's own token usage and cost. Say plainly that this is not a cost saving: the primary session still makes follow-up targeted reads, and the baseline session might not have read the files in full. A negative compression on small files is expected and means the broker should not be used for them. If the estimate is promising and the task is important, recommend the paired `bench/` evaluation.
