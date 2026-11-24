#!/usr/bin/env bash
# Publish a shields.io endpoint JSON file to the `badges` branch, creating the branch on first use.
#
#   GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo bash publish_badge.sh python-coverage.json
#
# The README badges read the file from raw.githubusercontent.com via shields.io. Nothing else is
# ever written to the branch, and the default branch is not touched. For testing, ODS_BADGE_REMOTE
# overrides the remote URL (for example a local bare repository).
set -euo pipefail

src="${1:?usage: publish_badge.sh <json-file>}"
name="$(basename "$src")"
branch="${ODS_BADGE_BRANCH:-badges}"
remote="${ODS_BADGE_REMOTE:-${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is not set}.git}"

auth=()
if [[ -n "${GITHUB_TOKEN:-}" && "$remote" == https://* ]]; then
  b64="$(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 -w0)"
  echo "::add-mask::$b64"
  auth=(-c "http.extraheader=AUTHORIZATION: basic $b64")
fi
git_remote() { git ${auth[@]+"${auth[@]}"} "$@"; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
repo="$work/repo"

# ls-remote exits 2 when the remote is fine but the branch is absent; any other failure is an error.
rc=0
git_remote ls-remote --exit-code --heads "$remote" "refs/heads/$branch" >/dev/null || rc=$?
if [[ $rc -eq 0 ]]; then
  git_remote clone -q --depth 1 --branch "$branch" "$remote" "$repo"
elif [[ $rc -eq 2 ]]; then # first run: the branch does not exist yet
  git init -q "$repo"
  git -C "$repo" checkout -q --orphan "$branch"
  git -C "$repo" remote add origin "$remote"
else
  echo "cannot reach $remote (git exit code $rc)" >&2
  exit 1
fi

cp "$src" "$repo/$name"
cd "$repo"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add "$name"
if git diff --cached --quiet; then
  echo "badge $name unchanged"
  exit 0
fi
git commit -q -m "badge: update $name"

for attempt in 1 2 3; do
  if git_remote push -q origin "HEAD:$branch"; then
    echo "published $name to $branch"
    exit 0
  fi
  git_remote pull -q --rebase origin "$branch" || true
done
echo "could not publish $name to $branch" >&2
exit 1
