#!/usr/bin/env bash
# Build UVA HotSpot 7 into learn/tools/hotspot. Architecture compact model.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREFIX="${ROOT}/learn/tools/hotspot"
SRC="${HOTSPOT_SRC:-/tmp/vendor-src/HotSpot}"
mkdir -p "${PREFIX}"
if [[ ! -f "${SRC}/hotspot.c" ]]; then
  git clone --depth 1 https://github.com/uvahotspot/HotSpot.git "${SRC}"
fi
make -C "${SRC}" -j"$(nproc)" SUPERLU=0
install -m 0755 "${SRC}/hotspot" "${PREFIX}/hotspot"
[[ -f "${SRC}/hotfloorplan" ]] && install -m 0755 "${SRC}/hotfloorplan" "${PREFIX}/hotfloorplan" || true
cp -f "${SRC}/template.config" "${PREFIX}/template.config"
cp -f "${SRC}/package.config" "${PREFIX}/package.config"
echo "OK hotspot → ${PREFIX}/hotspot"
"${PREFIX}/hotspot" -h | head -5 || true
