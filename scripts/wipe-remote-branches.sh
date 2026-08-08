#!/usr/bin/env bash
# Wipe all remote branches except main (already run once — kept for reference).
set -euo pipefail
REMOTE="${1:-origin}"
KEEP="${2:-main}"
mapfile -t branches < <(git ls-remote --heads "$REMOTE" | awk '{print $2}' | sed 's#refs/heads/##' | grep -v "^${KEEP}$")
for b in "${branches[@]}"; do
  echo "Deleting $REMOTE/$b"
  git push "$REMOTE" --delete "$b" || true
done
echo "Done. Remaining:"
git ls-remote --heads "$REMOTE"
