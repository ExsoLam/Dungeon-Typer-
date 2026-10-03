#!/usr/bin/env bash
# Removes worktrees and local branches whose PR has merged. Never touches a worktree
# with uncommitted work, or a branch whose tip differs from its merged PR head.
# Usage: git tidy [--dry-run]
set -euo pipefail
dry=${1:-}
cd "$(git rev-parse --show-toplevel)"
git fetch --prune --quiet origin
git worktree prune
merged=$(gh pr list --state merged --limit 200 --json headRefName,headRefOid -q '.[]|.headRefName+" "+.headRefOid' 2>/dev/null) \
  || { echo "tidy: gh is needed to confirm merges (gh auth login)."; exit 1; }
main_wt=$(git worktree list --porcelain | awk 'NR==1{print $2}')
git for-each-ref --format='%(refname:short) %(objectname)' refs/heads | while read -r branch sha; do
  [ "$branch" = main ] && continue
  grep -qx "$branch $sha" <<< "$merged" || continue
  wt=$(git worktree list --porcelain | awk -v b="refs/heads/$branch" '/^worktree /{w=$2} $0=="branch "b{print w}')
  if [ -n "$wt" ]; then
    [ "$wt" = "$main_wt" ] && { echo "skip $branch: checked out in the main checkout"; continue; }
    if [ -n "$(git -C "$wt" status --porcelain)" ]; then echo "skip $branch: $wt has uncommitted work"; continue; fi
    echo "remove worktree $wt"; [ "$dry" = --dry-run ] || git worktree remove "$wt"
  fi
  echo "delete branch $branch (merged)"; [ "$dry" = --dry-run ] || git branch -D "$branch" >/dev/null
done
