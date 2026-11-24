#!/usr/bin/env bash
# Applies the LLocDev contribution standards to one repository. Run it once per repository,
# including every new one, after its .github/workflows/pr-standards.yml is on the default branch.
#
#   scripts/apply-standards.sh <owner/repo> [--merge-commits] [extra branch pattern ...]
#
#   --merge-commits   keep merge commits allowed alongside squash (repositories with a release
#                     flow that merges release branches into main). Default: squash only.
#   extra patterns    more branches to protect besides the default branch, e.g. main 'release/**'
#
# It sets squash merges to use the PR title and description as the commit message, and creates
# or updates the "PR standards" ruleset: changes go through a pull request with one approval,
# the "pr-standards / check" status must pass, and no force pushes or deletions. Repository
# admins can bypass it. Needs gh signed in as a repository admin.
set -euo pipefail

if [ $# -lt 1 ]; then
  sed -n '4,9p' "$0"; exit 2
fi
repo=$1; shift
merge_commits=false
includes='"~DEFAULT_BRANCH"'
for arg in "$@"; do
  case "$arg" in
    --merge-commits) merge_commits=true ;;
    *) includes="$includes, \"refs/heads/$arg\"" ;;
  esac
done
methods='["squash"]'
if $merge_commits; then methods='["merge", "squash"]'; fi

echo "Merge settings for $repo"
gh api -X PATCH "repos/$repo" --silent \
  -F allow_squash_merge=true -F allow_merge_commit=$merge_commits -F allow_rebase_merge=false \
  -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=PR_BODY \
  -F delete_branch_on_merge=true

ruleset=$(cat <<JSON
{
  "name": "PR standards",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
  "conditions": {"ref_name": {"include": [$includes], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 1,
      "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": true,
      "allowed_merge_methods": $methods}},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": false,
      "do_not_enforce_on_create": true,
      "required_status_checks": [{"context": "pr-standards / check", "integration_id": 15368}]}}
  ]
}
JSON
)

id=$(gh api "repos/$repo/rulesets?includes_parents=false" \
  --jq '[.[] | select(.name == "PR standards" and .source_type == "Repository") | .id] | first // empty')
if [ -n "$id" ]; then
  echo "Updating ruleset $id"
  printf '%s' "$ruleset" | gh api -X PUT "repos/$repo/rulesets/$id" --input - --silent
else
  echo "Creating ruleset"
  printf '%s' "$ruleset" | gh api -X POST "repos/$repo/rulesets" --input - --silent
fi
gh api "repos/$repo/rulesets" --jq '.[] | "\(.id)  \(.name)  \(.enforcement)"'
