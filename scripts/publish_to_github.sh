#!/usr/bin/env bash
# Create Donkillshotte/pd-flow on GitHub (if missing) and push main from this checkout.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

OWNER="${GITHUB_OWNER:-Donkillshotte}"
REPO="${GITHUB_REPO:-pd-flow}"
VISIBILITY="${GITHUB_VISIBILITY:-public}"
BRANCH="${GITHUB_BRANCH:-main}"
REMOTE="${GITHUB_REMOTE:-github}"

TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
if [[ -z "${TOKEN}" ]]; then
  echo "FAIL: set GITHUB_TOKEN or GH_TOKEN with repo scope for ${OWNER}" >&2
  exit 1
fi

export GH_TOKEN="${TOKEN}"

if ! git rev-parse --verify "${BRANCH}" >/dev/null 2>&1; then
  echo "FAIL: branch ${BRANCH} not found in ${ROOT}" >&2
  exit 1
fi

if gh api "repos/${OWNER}/${REPO}" >/dev/null 2>&1; then
  echo "Repo ${OWNER}/${REPO} already exists"
else
  echo "Creating ${OWNER}/${REPO} (${VISIBILITY})"
  gh repo create "${OWNER}/${REPO}" \
    --"${VISIBILITY}" \
    --description "OpenROAD physical design flow — product, lab (DSE), and course/Studio (RTL→GDSII)" \
    --source "${ROOT}" \
    --remote "${REMOTE}" \
    --push=false
fi

if git remote get-url "${REMOTE}" >/dev/null 2>&1; then
  git remote set-url "${REMOTE}" "https://x-access-token:${TOKEN}@github.com/${OWNER}/${REPO}.git"
else
  git remote add "${REMOTE}" "https://x-access-token:${TOKEN}@github.com/${OWNER}/${REPO}.git"
fi

git push -u "${REMOTE}" "${BRANCH}"
git push "${REMOTE}" --tags 2>/dev/null || true

echo "OK: https://github.com/${OWNER}/${REPO}"
