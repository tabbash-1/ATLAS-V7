#!/usr/bin/env bash
set -euo pipefail

# Commit generated status evidence and push it to main without losing a run when
# another evidence writer advances main between fetch and push.

# Usage: commit_status_with_retry.sh NAME EMAIL MESSAGE PATH [PATH...]
# Safety: no force-push, no automatic conflict resolution, retry ref-lock races only.

if [[ "$#" -lt 4 ]]; then
  echo "usage: $0 NAME EMAIL MESSAGE PATH [PATH...]" >&2
  exit 2
fi

name="$1"; email="$2"; message="$3"; shift 3
paths=("$@")
max_attempts="${ATLAS_STATUS_PUSH_MAX_ATTEMPTS:-8}"

git config user.name "$name"
git config user.email "$email"
git add -- "${paths[@]}"

if git diff --cached --quiet; then
  echo "status evidence unchanged"
  exit 0
fi

git commit -m "$message"

for attempt in $(seq 1 "$max_attempts"); do
  echo "status push attempt $attempt/$max_attempts"
  git fetch origin main
  if ! git rebase origin/main; then
    echo "status writer rebase conflict; refusing automatic resolution" >&2
    git rebase --abort || true
    exit 1
  fi
  if git push origin HEAD:main; then
    echo "status evidence pushed"
    exit 0
  fi
  if [[ "$attempt" -lt "$max_attempts" ]]; then sleep "$((attempt * 2))"; fi
done

echo "status evidence push exhausted retries" >&2
exit 1
