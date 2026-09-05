#!/usr/bin/env bash
# Fetch leftover-named ASAP7 CCS / CDL extras. Not a finish. Not Calibre LVS.
# Does not vendor archives into git. Does not restamp gold 45.298 mV.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST_CCS="${ROOT}/learn/lab/asap7/ccs"
DEST_CDL="${ROOT}/learn/lab/asap7/cdl"
WORKDIR="${ASAP7_LIBEXTRAS_WORKDIR:-/tmp/asap7sc7p5t_28}"
SRC="${ASAP7_SC7P5T_SRC:-}"

mkdir -p "${DEST_CCS}" "${DEST_CDL}"

if [[ -z "${SRC}" ]]; then
  if [[ ! -d "${WORKDIR}/CDL" && ! -d "${WORKDIR}/LIB" ]]; then
    # Official 7.5T v28 cell library (layer 2). Large; leftover-named extras only.
    git clone --depth 1 https://github.com/The-OpenROAD-Project/asap7sc7p5t_28.git "${WORKDIR}" \
      || git clone --depth 1 https://github.com/The-OpenROAD-Project/asap7.git "${WORKDIR}"
  fi
  SRC="${WORKDIR}"
fi

copied_cdl=0
if [[ -d "${SRC}/CDL" ]]; then
  find "${SRC}/CDL" -name '*.cdl' -exec cp -f {} "${DEST_CDL}/" \;
  copied_cdl=1
fi

extracted_ccs=0
if command -v 7z >/dev/null 2>&1 || command -v 7za >/dev/null 2>&1; then
  UNZIP="$(command -v 7z || command -v 7za)"
  mkdir -p "${DEST_CCS}"
  while IFS= read -r -d '' archive; do
    "${UNZIP}" x -y -o"${DEST_CCS}" "${archive}" >/dev/null || true
    extracted_ccs=1
  done < <(find "${SRC}" -path '*LIB*CCS*' -name '*.7z' -print0 2>/dev/null)
else
  echo "leftover: p7zip/7z not installed; CCS .7z not extracted" >&2
fi

cat > "${ROOT}/learn/lab/asap7/LIBEXTRAS.md" <<EOF
ASAP7 CCS/CDL extras copied from ${SRC}.
Not a finish. Not Calibre. Not in git.
CCS refuse stays until a TT/SS (or other VT) .lib exists under learn/lab/asap7/ccs.
CDL is leftover-named netlist reference only.
EOF

echo "ccs dest ${DEST_CCS} extracted=${extracted_ccs}"
echo "cdl dest ${DEST_CDL} copied=${copied_cdl} count=$(find "${DEST_CDL}" -name '*.cdl' | wc -l)"
ls "${DEST_CCS}" 2>/dev/null | head || true
ls "${DEST_CDL}" 2>/dev/null | head || true
