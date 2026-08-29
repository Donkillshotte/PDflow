#!/usr/bin/env bash
# Build libdpn.so (native PDN solvers) and run dpn_test.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="${ROOT}/engine"
BUILD="${SRC}/build"
cmake -S "${SRC}" -B "${BUILD}" -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/g++-13
cmake --build "${BUILD}" -j"$(nproc)"
"${BUILD}/dpn_test"
echo "lib: ${BUILD}/libdpn.so"
