#!/usr/bin/env bash
# Fast CI gates that must pass on a clean checkout (no ORFS cook required).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts"

ASAP7_CFG="${ROOT}/tools/OpenROAD-flow-scripts/flow/designs/asap7/gcd/config.mk"
if [[ -f "${ASAP7_CFG}" ]]; then
  echo "==> Python: test_asap7_lab"
  python3 learn/scripts/test_asap7_lab.py
else
  echo "SKIP test_asap7_lab (ORFS asap7 designs absent)"
fi

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

if command -v cmake >/dev/null 2>&1 && command -v g++ >/dev/null 2>&1; then
  echo "==> Engine: cmake + dpn_test"
  cmake -S engine -B engine/build -DCMAKE_BUILD_TYPE=Release
  cmake --build engine/build --target dpn_test -j"$(nproc 2>/dev/null || echo 2)"
  ./engine/build/dpn_test
else
  echo "SKIP engine dpn_test (cmake/g++ not installed on this host)"
fi

echo "OK ci_fast_gates"
