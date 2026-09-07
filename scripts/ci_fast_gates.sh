#!/usr/bin/env bash
# Fast CI gates that must pass on a clean checkout (no ORFS cook required).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts"

echo "==> Python: test_asap7_lab"
python3 learn/scripts/test_asap7_lab.py

echo "==> Python: test_review_fixes"
python3 learn/scripts/test_review_fixes.py

echo "==> Python: test_lab_physics"
python3 learn/scripts/test_lab_physics.py

echo "==> Python: test_signoff_honesty"
python3 learn/scripts/test_signoff_honesty.py

echo "==> Python: test_dse_next (synthetic; ORFS-live sections skip when absent)"
python3 learn/scripts/test_dse_next.py

if command -v npm >/dev/null 2>&1; then
  echo "==> Studio: npm ci"
  (cd studio && npm ci)
  echo "==> Studio: lint"
  (cd studio && npm run lint)
  echo "==> Studio: build"
  (cd studio && npm run build)
else
  echo "SKIP Studio lint/build (npm not installed on this host)"
fi

echo "OK ci_fast_gates"
