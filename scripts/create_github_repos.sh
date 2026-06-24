#!/usr/bin/env bash
set -euo pipefail
OWNER=${1:?Uso: ./scripts/create_github_repos.sh OWNER [public|private]}
VISIBILITY=${2:-public}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
REPOS=(
  incubator-sensor-service
  incubator-aggregator-service
  quantum-anomaly-detector-service
  hybrid-incubator-deployment
)
command -v gh >/dev/null || { echo "Instala GitHub CLI y ejecuta gh auth login"; exit 1; }
for name in "${REPOS[@]}"; do
  cd "$ROOT/$name"
  test -d .git || git init
  git branch -M main
  git add .
  if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
    git commit -m "Initial version"
  elif test -n "$(git status --porcelain)"; then
    git commit -m "Update project files"
  fi
  gh repo create "$OWNER/$name" "--$VISIBILITY" --source . --remote origin --push
done
cd "$ROOT/hybrid-incubator-deployment"
python scripts/set_github_owner.py "$OWNER"
