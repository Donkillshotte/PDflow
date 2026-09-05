#!/usr/bin/env bash
# Fetch ASAP7 6-track views into learn/lab/asap7/sc6t (gitignored).
# Does not cook. Does not vendor 6.8 GB into git.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="${ROOT}/learn/lab/asap7/sc6t"
SRC="${ASAP7_SC6T_SRC:-}"
WORKDIR="${ASAP7_SC6T_WORKDIR:-/tmp/asap7sc6t_26}"

mkdir -p "${DEST}/lef" "${DEST}/gds" "${DEST}/lib" "${DEST}/verilog"
if [[ -z "${SRC}" ]]; then
  if [[ ! -d "${WORKDIR}/LEF" ]]; then
    git clone --depth 1 https://github.com/The-OpenROAD-Project/asap7sc6t_26.git "${WORKDIR}"
  fi
  SRC="${WORKDIR}"
fi
cp -f "${SRC}/LEF/asap7sc6t_26_"*_1x_*.lef "${DEST}/lef/"
cp -f "${SRC}/GDS/"*.gds "${DEST}/gds/"
cp -f "${SRC}/Verilog/"*.v "${DEST}/verilog/" 2>/dev/null || true
# Liberty stays archived (.7z). Extract when p7zip is present.
if command -v 7z >/dev/null 2>&1; then
  mkdir -p "${DEST}/lib/NLDM"
  7z x -y -o"${DEST}/lib/NLDM" "${SRC}/LIB/NLDM/"*RVT*nldm*.7z >/dev/null
fi
cat > "${DEST}/SOURCE.md" <<EOF
6-track ASAP7 views copied from The-OpenROAD-Project/asap7sc6t_26.
Not a finish. Not in git. RTL→GDS lab cook stays 7.5-track.
EOF
echo "sc6t views at ${DEST}"
ls "${DEST}/lef" | head
