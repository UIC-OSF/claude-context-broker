---
name: benchmark
description: "Run the paired Context Broker benchmark: full Claude Code sessions with and without the broker, compared on task pass rate and total cost (primary + worker). Use when the user wants to know whether the broker is worth enabling for this project."
---

This spends real money: every run is a complete `claude -p` session, and the broker condition adds worker calls. Follow the steps in order and do not start step 4 until the user has confirmed.

1. **Scaffold the tasks file** if `.context-broker/bench/tasks.json` does not exist:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/bench/run.py --init
   ```
2. **Write real tasks with the user.** Each task needs an `id`, a `prompt` that a fresh session can act on, `reset` commands that return the tree to a clean state (the default `git checkout -- . && git clean -fdq -e .context-broker -e .claude` is usually right; add `-e` for any other untracked directory the user wants kept, and confirm `git status` is clean before the first run because reset discards uncommitted work), and `checks`: shell commands that exit 0 only if the task was done correctly. Aim for 3-5 tasks: a bug investigation, a small feature, a test addition, and one task where the broker should *not* help (small files). Optional per task: `max_turns`, `model`, `permission_mode`, `allowed_tools` (a list of Claude Code permission rules such as `Bash(npm test:*)`), or a `broker_prompt` to replace the default hint. The harness always pre-approves the broker command itself; a non-interactive session cannot answer a permission prompt, so without that the broker condition would never run the broker. Tasks that edit files need `acceptEdits` plus `allowed_tools` for any shell commands they must run, or `bypassPermissions`. Remove every `REPLACE ME`.
3. **Confirm the budget.** Tell the user: number of tasks x runs x 2 conditions = total sessions, and that the baseline condition runs with the hooks disabled. Recommend `--runs 3` for a first pass. Wait for an explicit yes.
4. **Run both conditions:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/bench/run.py --condition baseline --runs 3
   python3 ${CLAUDE_PLUGIN_ROOT}/bench/run.py --condition broker --runs 3
   ```
5. **Score:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/bench/score.py
   ```

Before reporting, confirm the broker condition actually used the broker: every broker row in `results.jsonl` has a `worker_usage` list, and `.context-broker/bench/worker-usage/` has one file per broker run that invoked it. If those are empty the comparison is "hooks on" versus "hooks off", not broker versus no broker; say so. Also report how many runs in each condition hit a hook denial at all; if none did, the project's reading habits never trigger the plugin and the cost columns are noise.

Report the table and apply the decision rule in order: first compare check pass rate; if the broker condition passes less often than the baseline beyond the margin the user set, the broker loses regardless of cost. Only then compare `total-usd` (primary plus worker). Token columns are informational. Say plainly that with few runs the difference may be noise. Raw transcripts are in `.context-broker/bench/results.jsonl` for blinded human review.
