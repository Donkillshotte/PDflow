#!/usr/bin/env bash
# Fast CI gates that must pass on a clean checkout (no ORFS cook required).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts"

echo "==> Python: test_events"
python3 learn/scripts/test_events.py

echo "==> Python: test_registry"
python3 learn/scripts/test_registry.py

echo "==> Python: test_resource_runner"
python3 learn/scripts/test_resource_runner.py

echo "==> Python: test_symphony_workflow"
python3 learn/scripts/test_symphony_workflow.py

ASAP7_CFG="${ROOT}/tools/OpenROAD-flow-scripts/flow/designs/asap7/gcd/config.mk"
if [[ -f "${ASAP7_CFG}" ]]; then
  echo "==> Python: test_asap7_lab"
  python3 learn/scripts/test_asap7_lab.py
else
  echo "SKIP test_asap7_lab (ORFS asap7 designs absent)"
fi

echo "==> Python: test_review_fixes"

python3 learn/scripts/test_review_fixes.py

echo "==> Python: test_studio_security"

python3 learn/scripts/test_studio_security.py

echo "==> Python: test_lab_physics"
python3 learn/scripts/test_lab_physics.py

echo "==> Python: test_signoff_honesty"
python3 learn/scripts/test_signoff_honesty.py

echo "==> Python: test_dse_next (synthetic; ORFS-live sections skip when absent)"
python3 learn/scripts/test_dse_next.py

STUDIO_NODE="${ROOT}/studio/node-runtime/node"
STUDIO_ESLINT="${ROOT}/studio/node_modules/eslint/bin/eslint.js"
STUDIO_NEXT="${ROOT}/studio/node_modules/next/dist/bin/next"

if command -v npm >/dev/null 2>&1; then
  echo "==> Studio: npm ci"
  "${ROOT}/scripts/run_resource_job.sh" studio-npm-ci bash -c 'cd studio && npm ci'
  echo "==> Studio: lint"
  "${ROOT}/scripts/run_resource_job.sh" studio-lint bash -c 'cd studio && npm run lint'
  echo "==> Studio: build"
  "${ROOT}/scripts/run_resource_job.sh" studio-next-build bash -c 'cd studio && npm run build'
elif [[ -x "${STUDIO_NODE}" && -x "${STUDIO_ESLINT}" && -x "${STUDIO_NEXT}" ]]; then
  echo "==> Studio: bundled native Node runtime"
  echo "==> Studio: lint"
  "${ROOT}/scripts/run_resource_job.sh" studio-lint-bundled \
    bash -c 'cd studio && ./node-runtime/node node_modules/eslint/bin/eslint.js .'
  echo "==> Studio: build"
  "${ROOT}/scripts/run_resource_job.sh" studio-next-build-bundled \
    bash -c 'cd studio && ./node-runtime/node node_modules/next/dist/bin/next build --webpack'
else
  echo "SKIP Studio lint/build (npm and bundled native Node dependencies are unavailable)"
fi

BUILD_TOOLS_PREFIX="${PD_FLOW_BUILD_TOOLS_PREFIX:-}"
if [[ -n "${BUILD_TOOLS_PREFIX}" ]]; then
  if [[ -z "${PD_FLOW_CMAKE:-}" && -x "${BUILD_TOOLS_PREFIX}/usr/bin/cmake" ]]; then
    export PD_FLOW_CMAKE="${BUILD_TOOLS_PREFIX}/usr/bin/cmake"
  fi
  if [[ -z "${PD_FLOW_CTEST:-}" && -x "${BUILD_TOOLS_PREFIX}/usr/bin/ctest" ]]; then
    export PD_FLOW_CTEST="${BUILD_TOOLS_PREFIX}/usr/bin/ctest"
  fi
  if [[ -z "${PD_FLOW_EIGEN3_DIR:-}" && -f "${BUILD_TOOLS_PREFIX}/usr/share/eigen3/cmake/Eigen3Config.cmake" ]]; then
    export PD_FLOW_EIGEN3_DIR="${BUILD_TOOLS_PREFIX}/usr/share/eigen3/cmake"
  fi
fi

CMAKE_BIN="${PD_FLOW_CMAKE:-$(command -v cmake || true)}"
CTEST_BIN="${PD_FLOW_CTEST:-$(command -v ctest || true)}"
EIGEN3_DIR="${PD_FLOW_EIGEN3_DIR:-}"
EIGEN3_AVAILABLE=0
if [[ -d /usr/include/eigen3 || -d /usr/local/include/eigen3 \
  || -f "${EIGEN3_DIR}/Eigen3Config.cmake" ]]; then
  EIGEN3_AVAILABLE=1
fi
if [[ -x "${CMAKE_BIN}" && -x "${CTEST_BIN}" && -n "$(command -v g++ || true)" \
  && "${EIGEN3_AVAILABLE}" -eq 1 ]]; then
  echo "==> Engine: cmake + dpn_test"
  "${ROOT}/scripts/run_resource_job.sh" engine-dpn-test bash -c '
    set -Eeuo pipefail
    build_dir="$(mktemp -d /tmp/pdflow-engine-ci.XXXXXX)"
    trap "rm -rf \"$build_dir\"" EXIT
    if [[ -n "${PD_FLOW_EIGEN3_DIR:-}" ]]; then
      "${PD_FLOW_CMAKE:-cmake}" -S engine -B "$build_dir" \
        -DCMAKE_BUILD_TYPE=Release "-DEigen3_DIR=$PD_FLOW_EIGEN3_DIR"
    else
      "${PD_FLOW_CMAKE:-cmake}" -S engine -B "$build_dir" -DCMAKE_BUILD_TYPE=Release
    fi
    "${PD_FLOW_CMAKE:-cmake}" --build "$build_dir" --target dpn_test -j"${PD_FLOW_NUM_THREADS:-4}"
    "${PD_FLOW_CTEST:-ctest}" --test-dir "$build_dir" --output-on-failure
  '
else
  echo "SKIP engine dpn_test (cmake/ctest/g++/Eigen3 are unavailable; set PD_FLOW_BUILD_TOOLS_PREFIX for a local tool prefix)"
fi

echo "OK ci_fast_gates"
