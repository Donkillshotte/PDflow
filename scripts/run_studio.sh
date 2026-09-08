#!/usr/bin/env bash
# Start OpenROAD Physical Design Studio (web UI).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/studio"
PORT="${PORT:-43217}"
HOST="${HOST:-127.0.0.1}"

if [[ ! -d node_modules ]]; then
  if [[ -f package-lock.json ]]; then
    echo "==> npm ci in studio/"
    npm ci
  else
    echo "==> npm install in studio/ (no lockfile present)"
    npm install
  fi
fi

if [[ "${1:-}" == "--build" ]]; then
  npm run build
  exec npx next start -H "${HOST}" -p "${PORT}"
fi

exec npx next dev -H "${HOST}" -p "${PORT}"
