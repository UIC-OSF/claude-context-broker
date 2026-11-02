#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
command="$(printf '%s' "$input" | jq -r '.tool_input.command // empty')"

# Let searches, pipes, redirection, and clearly bounded commands through. This
# hook is intentionally conservative: it prevents only simple full-file dumps.
if [[ "$command" == *"|"* || "$command" == *">"* || "$command" =~ (^|[[:space:]])(rg|grep|sed|awk)([[:space:]]|$) ]]; then
  exit 0
fi
if [[ ! "$command" =~ ^[[:space:]]*(cat|less|more)[[:space:]]+([^[:space:]]+)[[:space:]]*$ ]]; then
  exit 0
fi

file_path="${BASH_REMATCH[2]}"
if [[ ! -f "$file_path" ]]; then
  exit 0
fi
threshold="${CONTEXT_BROKER_MIN_LINES:-750}"
line_count="$(wc -l < "$file_path" | tr -d ' ')"
if (( line_count <= threshold )); then
  exit 0
fi
reason="Large shell read blocked (${line_count} lines; threshold ${threshold}). Use bin/repo-read for exploration or a targeted command for an exact range."
jq -n --arg reason "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
