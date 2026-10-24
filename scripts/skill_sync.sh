#!/usr/bin/env bash
# Sync the cloudstream-builder skill checkout with the user's GitHub repository.
#
#   ./scripts/skill_sync.sh pull     fetch + fast-forward (automatic updates)
#   ./scripts/skill_sync.sh push     commit local work and push to origin
#   ./scripts/skill_sync.sh audit    verify repo.json <-> .cs3 integrity locally
#   ./scripts/skill_sync.sh status   branch, dirty files, last commits
#
# The checkout is the skill directory itself, so `git push` from here always
# publishes to the user's own repository (altigenay/cloudstream-eklentiler).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

cmd="${1:-pull}"
case "$cmd" in
  pull)
    git fetch --prune origin
    if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
      git pull --ff-only
    else
      git branch --set-upstream-to="origin/$(git rev-parse --abbrev-ref HEAD)" >/dev/null
      git pull --ff-only
    fi
    echo "skill güncel: $(git rev-parse --short HEAD) $(git log -1 --pretty=%s)"
    ;;
  push)
    message="${2:-skill: güncelleme}"
    if [ -n "$(git status --porcelain)" ]; then
      git add -A
      git commit -m "$message"
    fi
    git push origin HEAD
    ;;
  audit)
    python3 scripts/verify_repo_integrity.py --all "$@"
    ;;
  status)
    git status --short --branch
    git log --oneline -3
    ;;
  *)
    echo "kullanım: $0 {pull|push|audit|status}" >&2
    exit 2
    ;;
esac
