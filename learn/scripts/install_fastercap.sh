#!/usr/bin/env bash
# Build FasterCap (LGPL) into learn/tools/fastercap. Educational 2-wire PEX.
# Needs LinAlgebra + Geometry siblings. wxWidgets 3.2 (headless).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREFIX="${ROOT}/learn/tools/fastercap"
SRC_ROOT="${FASTERCAP_SRC:-/tmp/fastercap-src}"
mkdir -p "${PREFIX}"
if [[ ! -f "${SRC_ROOT}/FasterCap/CMakeLists.txt" ]]; then
  mkdir -p "${SRC_ROOT}"
  git clone --depth 1 https://github.com/ediloren/FasterCap.git "${SRC_ROOT}/FasterCap"
  git clone --depth 1 https://github.com/ediloren/Geometry.git "${SRC_ROOT}/Geometry"
  git clone --depth 1 https://github.com/ediloren/LinAlgebra.git "${SRC_ROOT}/LinAlgebra"
fi
# wx 3.2 on Ubuntu 24; upstream CMake asks for 3.0.
sed -i 's/--version=3.0/--version=3.2/' "${SRC_ROOT}/FasterCap/CMakeLists.txt" || true
rm -rf "${SRC_ROOT}/build"
mkdir -p "${SRC_ROOT}/build"
WXINC="$(wx-config --version=3.2 --cxxflags 2>/dev/null || wx-config --cxxflags)"
cmake -S "${SRC_ROOT}/FasterCap" -B "${SRC_ROOT}/build" \
  -G"Unix Makefiles" -DCMAKE_BUILD_TYPE=Release \
  -DFASTFIELDSOLVERS_HEADLESS=ON \
  -DwxWidgets_CONFIG_EXECUTABLE="$(command -v wx-config)" \
  -DCMAKE_CXX_COMPILER=g++ -DCMAKE_C_COMPILER=gcc \
  -DCMAKE_CXX_FLAGS="${WXINC}"
cmake --build "${SRC_ROOT}/build" -j"$(nproc)"
install -m 0755 "${SRC_ROOT}/build/FasterCap" "${PREFIX}/FasterCap"
echo "OK FasterCap → ${PREFIX}/FasterCap"
"${PREFIX}/FasterCap" -bv
