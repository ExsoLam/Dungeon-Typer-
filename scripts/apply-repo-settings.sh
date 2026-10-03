#!/usr/bin/env bash
# Repository settings and main branch rules. Needs a repo admin (gh auth as ExsoLam).
# Safe to rerun: it updates the ruleset named "main" in place.
set -euo pipefail
R=${REPO:-ExsoLam/Dungeon-Typer-}

gh api -X PATCH "repos/$R" --silent --input - <<'JSON'
{
  "delete_branch_on_merge": true,
  "allow_squash_merge": true,
  "allow_merge_commit": false,
  "allow_rebase_merge": false,
  "allow_auto_merge": true,
  "allow_update_branch": true,
  "squash_merge_commit_title": "PR_TITLE",
  "squash_merge_commit_message": "PR_BODY",
  "security_and_analysis": {
    "secret_scanning": { "status": "enabled" },
    "secret_scanning_push_protection": { "status": "enabled" }
  }
}
JSON
echo "Repo: squash merges only, branches deleted on merge, secret push protection on"

ruleset='{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "bypass_actors": [ { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request" } ],
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_linear_history" },
    { "type": "pull_request", "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["squash"] } },
    { "type": "required_status_checks", "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [ { "context": "check" }, { "context": "deploy" }, { "context": "hygiene" } ] } }
  ]
}'
id=$(gh api "repos/$R/rulesets" -q '.[]|select(.name=="main")|.id')
if [ -n "$id" ]; then gh api -X PUT "repos/$R/rulesets/$id" --silent --input - <<< "$ruleset"
else gh api -X POST "repos/$R/rulesets" --silent --input - <<< "$ruleset"; fi
echo "main: PRs only, checks check/deploy/hygiene must pass on an up-to-date branch, no force push or deletion"

gh label create assets-change -R "$R" --color B8985A --force \
  --description "Intentionally changes embedded art or word lists" >/dev/null
echo "Label assets-change ready"
