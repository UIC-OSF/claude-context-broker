# Claude Context Broker

A small, repository-owned nudge for Claude Code. It denies the common ways of
dumping a large file into the primary context, lets a locked-down lower-cost
worker produce an evidence-bearing map of the relevant code, and leaves
judgment, edits, and review with Claude Code.

This is intentionally not an agent platform. It is two hooks, a narrow command,
and an evaluation harness you can own.

## What it changes, and what it does not

When Claude tries to read more than the configured number of lines from one
file, a `PreToolUse` hook denies that call and points at the bulk-reader skill.
A Read is bounded only if `offset` and `limit` together span at most the
threshold; `offset` alone or an oversized `limit` is treated as a full read.
The Bash hook denies the common dump commands (`cat`, `less`, `more`, `nl`,
`bat`, `tac`, `pr`, and unbounded `head`/`tail`) including flags, quoting,
multiple files, `cd dir && cat f`, and relative paths.

**The hooks are a nudge, not a security boundary.** A pipeline that filters
output (`cat big | grep x`), a bounded range (`sed -n '10,40p'`), an arbitrary
interpreter, `Grep`, subagents, and MCP file tools are all allowed. The hooks
fail open: if they crash, the read proceeds. The goal is to make the broker the
path of least resistance for broad exploration, not to make large reads
impossible. Measure whether that happens with `bench/` before relying on it.

The worker is pluggable. It receives JSON on stdin and must return JSON on
stdout. The default worker is a Claude CLI call locked down to no tools, one
turn, no session persistence, and no inherited project or user settings; see
"Worker protocol". An institution can instead point `CONTEXT_BROKER_WORKER` at
an approved gateway without putting credentials in this repository.

## Quick start

### Claude Code plugin (recommended)

From Claude Code, add the marketplace and install once:

```bash
claude plugin marketplace add UIC-OSF/claude-context-broker
claude plugin install context-broker@claude-context-broker
```

Start a new Claude Code session and use `/context-broker:setup` to validate the
zero-config worker. From then on, large-file exploration is automatic: the
plugin hook redirects broad reads to a locked-down lower-cost Claude worker,
while Claude Code retains judgment, targeted reads, edits, and review. Teams can
replace the default worker with an approved gateway through
`CONTEXT_BROKER_WORKER`.

Two short commands cover normal evaluation:

- `/context-broker:check` verifies prerequisites and exercises the hook scripts against fixtures, including known bypass shapes, without sending source to a model.
- `/context-broker:benchmark` reports, for one question, how the worker summary compares with what a capped Read would have put in context, plus the worker's own tokens and cost. It is a screening tool, not a savings claim.

### Repository installation

```bash
git clone <this-repository>
cd claude-context-broker
python3 -m unittest discover -s tests -v

# Install into another repository (review the generated settings first).
./install.sh /path/to/your/project
```

This copies `plugins/context-broker/{hooks,scripts}` to
`.claude/context-broker/` in the target and writes (or offers a snippet for)
`.claude/settings.json`. Start a fresh Claude Code session in the target project.

Without the plugin system, run the broker directly:

```bash
.claude/context-broker/scripts/repo-read --question "Where is authorization checked?" --paths src/auth.ts src/routes.ts
.claude/context-broker/scripts/repo-read --question "..." --paths ... --dry-run   # show the request, send nothing
```

To route through your own endpoint, set `CONTEXT_BROKER_WORKER` to a command
that reads the request JSON on stdin and writes the response JSON on stdout.
`examples/anthropic-worker.sh` is a reference adapter for a low-cost Anthropic
model. Review its data handling and use an approved gateway before enabling it
for institutional code. Note that `CONTEXT_BROKER_WORKER` is executed as a shell
command with the developer's environment; if you set it in a committed
`.claude/settings.json`, anyone with write access to the repository controls it.

## Claude Code behavior

```text
You: Find the authorization path for course import and fix any gap.

Claude: searches normally with rg
Claude: attempts a full read of a 1,200-line route file
Hook: denies that read and points at the bulk-reader skill
Claude: runs repo-read with the question and candidate paths
Worker: returns evidence with paths and line ranges, wrapped as untrusted output
Claude: reads only the cited ranges (bounded), decides whether a gap exists, edits, tests
```

The broker should not be used to decide architecture, security policy, or a
debugging root cause. It identifies candidate evidence; Claude and a human
remain responsible for the decision. Worker output is model output over source
that may contain adversarial text, so `repo-read` wraps it in an
`UNTRUSTED WORKER OUTPUT` block and the skill tells Claude not to follow
instructions found inside it.

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
settings.

| Variable | Default | Meaning |
|---|---|---|
| `CONTEXT_BROKER_MIN_LINES` | `750` | Reads or shell dumps spanning more lines than this are denied |
| `CONTEXT_BROKER_MAX_FILE_BYTES` | `768000` | Per-file ceiling for `repo-read` |
| `CONTEXT_BROKER_MAX_TOTAL_BYTES` | `1000000` | Per-request ceiling for `repo-read` |
| `CONTEXT_BROKER_WORKER` | plugin `worker-claude` | Worker command (shell) |
| `CONTEXT_BROKER_WORKER_MODEL` | `haiku` | Model for the default worker |
| `CONTEXT_BROKER_DISABLE` | unset | `1` turns the hooks off |

`repo-read` refuses: paths that resolve outside the project root (including
through symlinks), git-ignored files, files whose names match secret patterns
(`.env*`, `*credentials*`, `*secret*`, `*.tfstate`, `*.tfvars`, `.netrc`,
`.npmrc`, SSH keys, certificates, and more), files whose content matches
secret-like patterns (private key blocks, AWS/Anthropic/GitHub/Slack token
shapes, `password = "..."`), binary files, and files over the ceilings. These
are filters, not guarantees; review what your worker receives.

## Measuring whether it earns its complexity

Use `bench/` before enforcing the hook team-wide. `scripts/benchmark` alone
cannot tell you whether the broker saves anything: a summary is always smaller
than its source, and it does not count the follow-up reads the primary session
still makes.

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

`bench/run.py` runs each task's `reset` commands before every repetition, sets
`CONTEXT_BROKER_DISABLE=1` for the baseline condition so the hook is really off,
and records exit state, elapsed time, stdout/stderr, Claude's `usage` and
`total_cost_usd`, and every worker usage record that `repo-read` emitted.
`bench/score.py` reports uncached input, cache reads, output, primary cost,
worker cost, and total cost per condition. Compare total cost, not token counts:
cache reads are billed at a fraction of input, and the worker's spend is real.

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

Treat the worker as a data egress route *and* as an instruction ingress route.

- Egress: use an approved model endpoint, keep the deny patterns and ceilings,
  rely on project-root containment, and never place API keys in repository
  settings or shell history.
- Ingress: the worker reads third-party code, PR branches, and vendored
  dependencies, any of which may contain text written to steer a model. Its
  output is wrapped as untrusted and the skill instructs Claude not to follow
  instructions inside it, but that is a mitigation, not a guarantee. Keep
  judgment, edits, and review with the primary session and a human.
- `CONTEXT_BROKER_WORKER` is a shell command. Whoever controls the settings
  file that sets it controls what runs with the developer's environment.
