#!/usr/bin/env bash
# Reference adapter only. Prefer an institutionally approved gateway endpoint.
set -euo pipefail
: "${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY outside this repository}"
request="$(cat)"
prompt="$(jq -r '"<task>" + .question + "</task><files>" + ([.files[] | "<file path=\\\"" + .path + "\\\">" + .content + "</file>"] | join("")) + "</files><instructions>Return concise bullets. Every claim must cite path and line range. State uncertainty; do not make edits.</instructions>"' <<<"$request")"
response="$(jq -n --arg prompt "$prompt" '{model:(env.CONTEXT_BROKER_WORKER_MODEL // "claude-haiku-4-5"),max_tokens:1200,temperature:0,input:[{role:"user",content:$prompt}]}' | curl --fail-with-body -sS https://api.anthropic.com/v1/messages -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" -d @-)"
jq '{answer: .content[0].text, model: .model, usage: .usage}' <<<"$response"
