#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
file_path="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')"
offset="$(printf '%s' "$input" | jq -r '.tool_input.offset // empty')"
limit="$(printf '%s' "$input" | jq -r '.tool_input.limit // empty')"

# Narrow reads retain exact source context and are always allowed.
if [[ -n "$offset" || -n "$limit" || -z "$file_path" || ! -f "$file_path" ]]; then
  exit 0
fi

threshold="${CONTEXT_BROKER_MIN_LINES:-750}"
line_count="$(wc -l < "$file_path" | tr -d ' ')"
if (( line_count <= threshold )); then
  exit 0
fi

reason="Large unbounded read blocked (${line_count} lines; threshold ${threshold}). Search first, then run bin/repo-read with a focused question and explicit paths. Targeted Read calls with offset/limit are allowed."
jq -n --arg reason "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
