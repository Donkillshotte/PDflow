#!/usr/bin/env bash
# Avvia OpenROAD Physical Design Studio (UI web).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/studio"
PORT="${PORT:-43217}"
HOST="${HOST:-127.0.0.1}"

if [[ ! -d node_modules ]]; then
  echo "==> npm install in studio/"
  npm install
fi

if [[ "${1:-}" == "--build" ]]; then
  npm run build
  exec npx next start -H "${HOST}" -p "${PORT}"
fi

exec npx next dev -H "${HOST}" -p "${PORT}"
