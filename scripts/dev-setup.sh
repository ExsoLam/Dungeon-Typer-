#!/usr/bin/env bash
# One-time setup for a clone: hooks, pruning and safe pull defaults. Safe to rerun.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
git config fetch.prune true
git config fetch.pruneTags true
git config pull.ff only
git config push.autoSetupRemote true
git config rerere.enabled true
git config alias.tidy '!bash scripts/tidy.sh'
mkdir -p ../dungeon-typer-wt
echo "Hooks on, fetch prunes deleted branches, pull is fast-forward only."
echo "Start work with:  git worktree add ../dungeon-typer-wt/<type>/<topic> -b <type>/<topic> origin/main"
echo "Clean up with:    git tidy"
