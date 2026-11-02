#!/usr/bin/env bash
# Copy the plugin into a project that does not use the Claude Code plugin system.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${1:?Usage: ./install.sh /path/to/project}"
target="$(cd "$target" && pwd)"
dest="$target/.claude/context-broker"

rm -rf "$dest"
mkdir -p "$dest"
cp -R "$here/plugins/context-broker/hooks" "$here/plugins/context-broker/scripts" "$dest/"
rm -rf "$dest/hooks/__pycache__"
chmod +x "$dest/scripts/"* "$dest/hooks/"*.py

settings="$target/.claude/settings.json"
snippet="$(sed "s#\${CLAUDE_PROJECT_DIR}/plugins/context-broker#\${CLAUDE_PROJECT_DIR}/.claude/context-broker#g" "$here/.claude/settings.json")"
if [[ -e "$settings" ]]; then
  printf '%s\n' "$snippet" > "$dest/settings.snippet.json"
  echo "Installed to $dest. Merge $dest/settings.snippet.json into $settings by hand so existing settings are preserved."
else
  printf '%s\n' "$snippet" > "$settings"
  echo "Installed to $dest and wrote $settings."
fi
echo "Invoke the broker with: $dest/scripts/repo-read --question '...' --paths <files>"
