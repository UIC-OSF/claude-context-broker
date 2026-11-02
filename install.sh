#!/usr/bin/env bash
set -euo pipefail

target="${1:?Usage: ./install.sh /path/to/project}"
target="$(cd "$target" && pwd)"
mkdir -p "$target/.claude/hooks" "$target/bin"
cp .claude/hooks/block-large-read.sh .claude/hooks/block-large-bash-read.sh "$target/.claude/hooks/"
cp bin/repo-read "$target/bin/repo-read"
chmod +x "$target/.claude/hooks/"*.sh "$target/bin/repo-read"

if [[ -e "$target/.claude/settings.json" ]]; then
  echo "Hooks installed. Merge .claude/settings.json manually so existing settings are preserved."
else
  cp .claude/settings.json "$target/.claude/settings.json"
  echo "Installed hooks and settings in $target"
fi
