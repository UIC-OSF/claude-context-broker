# Claude Context Broker

A small, repository-owned guardrail for Claude Code. It prevents unbounded reads
of large files, lets a lower-cost worker produce an evidence-bearing map of the
relevant code, and leaves judgment, edits, and review with Claude Code.

This is intentionally not an agent platform. It is a hook, a narrow command,
and an evaluation harness you can own.

## What it changes

When Claude tries to fully read a file above the configured threshold, a
`PreToolUse` hook rejects that one call and explains how to use `bin/repo-read`.
Targeted reads with an offset or limit are allowed. Claude can therefore use the
worker's findings to request the exact code it needs before making an edit.

The worker is deliberately pluggable. It receives JSON on stdin and must return
JSON on stdout. This lets an institution point it at an approved low-cost model
through its own gateway without putting credentials in this repository.

## Quick start

### Claude Code plugin (recommended)

From Claude Code, add the marketplace and install once:

```bash
claude plugin marketplace add UIC-OSF/claude-context-broker
claude plugin install context-broker@claude-context-broker
```

Start a new Claude Code session and use `/context-broker:setup` to validate the
zero-config worker. From then on, large-file exploration is automatic: the
plugin hook redirects broad reads to a lower-cost Claude worker, while Claude
Code retains judgment, targeted reads, edits, and review. Teams can replace the
default worker with an approved gateway through `CONTEXT_BROKER_WORKER`.

Two short commands cover normal evaluation:

- `/context-broker:check` verifies installation, prerequisites, and hook behavior without sending source to a model.
- `/context-broker:benchmark` identifies a few relevant large files and gives a quick context-volume estimate. It is intentionally a screening tool, not a billing or quality claim.

### Repository installation

```bash
git clone <this-repository>
cd claude-context-broker
python3 -m unittest discover -s tests -v

# Install into another repository (review the generated settings first).
./install.sh /path/to/your/project
```

Then start a fresh Claude Code session in the target project. The hook activates
from `.claude/settings.json`.

To enable real summaries, set a worker command. The command receives the broker
request as JSON on stdin and returns the worker response as JSON on stdout:

```bash
export CONTEXT_BROKER_WORKER="/path/to/your/approved-worker"
bin/repo-read --question "Where is authorization checked?" --paths src/auth.ts src/routes.ts
```

`examples/anthropic-worker.sh` is a reference adapter for a low-cost Anthropic
model. Review its data handling and use an approved gateway before enabling it
for institutional code.

## Claude Code behavior

```text
You: Find the authorization path for course import and fix any gap.

Claude: searches normally with rg
Claude: attempts a full read of a 1,200-line route file
Hook: blocks that full read and directs Claude to repo-read
Claude: runs bin/repo-read with the question and candidate paths
Worker: returns evidence with paths, line ranges, and confidence
Claude: reads only the cited ranges, decides whether a gap exists, edits, tests
```

The broker should not be used to decide architecture, security policy, or a
debugging root cause. It identifies candidate evidence; Claude and a human
remain responsible for the decision.

## Origins and attribution

Claude Context Broker is based on the architecture described in Spotify's
public [Shunt plugin](https://github.com/spotify/portal-ai-plugins/tree/main/plugins/shunt)
and its accompanying engineering post, ["Portal by Spotify cut my Claude Code
token usage by 90%"](https://engineering.atspotify.com/2026/9/portal-by-spotify-cut-my-claude-code-token-usage-by-90/).

The shared idea is deliberately small: enforce a boundary around broad,
I/O-heavy file reading; delegate that mechanical work to a cheaper worker; then
keep targeted reads, judgment, edits, testing, and final review with the main
Claude Code session. Spotify's version routes through Portal and AiKA modes.
This project is an independent implementation that instead offers a
zero-config local Claude worker or a configurable institutionally approved
worker command.

## Configuration

The default threshold is 750 lines. Override it per project:

```json
{
  "env": {
    "CONTEXT_BROKER_MIN_LINES": "1000",
    "CONTEXT_BROKER_WORKER": "/opt/context-broker/worker"
  }
}
```

Merge those values into `.claude/settings.json`; do not replace other project
settings. Files matching common secret names, files over 750 KiB, and binary
files are rejected by `repo-read` by default.

## Measuring whether it earns its complexity

Use `bench/` before enforcing the hook team-wide.

1. Choose 10-20 representative tasks that require understanding several files.
   Include bug investigation, a small feature, a test addition, and one task
   where the broker should *not* be used.
2. Give each task an acceptance test and a short hidden rubric with expected
   evidence or behavior.
3. Run both conditions in fresh clones and fresh Claude sessions, with the same
   Claude model, permissions, task prompt, and maximum turns. Run each at least
   five times to account for model variance.
4. Compare task-pass rate first. The broker passes only if it does not lower
   quality beyond your preset margin. Then compare primary-model tokens, worker
   tokens, estimated total cost, wall-clock time, and human correction time.

`bench/run.py` records command exit state, elapsed time, stdout/stderr, and any
usage fields emitted by Claude's JSON output. `bench/score.py` combines blinded
human or grader scores with those run records. Do not claim a savings percentage
from token counts alone: include the worker-model cost and latency.

Example:

```bash
cp bench/tasks.example.json bench/tasks.json
# Edit commands to match your Claude Code installation and test suite.
python3 bench/run.py --tasks bench/tasks.json --condition baseline --runs 5
python3 bench/run.py --tasks bench/tasks.json --condition broker --runs 5
python3 bench/score.py --results bench/results.jsonl
```

## Worker protocol

Request:

```json
{"question":"Where is authorization checked?","files":[{"path":"src/auth.ts","content":"..."}]}
```

Response:

```json
{"answer":"- src/auth.ts:42-79 - requireRole()...","model":"approved-cheap-model","usage":{"input_tokens":123,"output_tokens":45}}
```

The answer should cite a path and line range for every finding and explicitly
say when the supplied files are insufficient.

## Security notes

Treat the worker as a data egress route. Use an approved model endpoint, remove
or deny sensitive files, set a payload ceiling, log only metadata by default,
and never place API keys in repository settings or shell history.
