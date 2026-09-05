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
  # Default: RVT TT/SS so CCS TC/WC stop being a refuse. Full dump is ASAP7_CCS_ALL=1.
  if [[ "${ASAP7_CCS_ALL:-0}" == "1" ]]; then
    mapfile -d '' archives < <(find "${SRC}" -path '*LIB*CCS*' -name '*.7z' -print0 2>/dev/null)
  else
    mapfile -d '' archives < <(find "${SRC}" -path '*LIB*CCS*' \( -name '*_RVT_TT_*.7z' -o -name '*_RVT_SS_*.7z' \) -print0 2>/dev/null)
  fi
  for archive in "${archives[@]+"${archives[@]}"}"; do
    [[ -z "${archive}" ]] && continue
    "${UNZIP}" x -y -o"${DEST_CCS}" "${archive}" >/dev/null || true
    extracted_ccs=1
  done
else
  echo "leftover: p7zip/7z not installed; CCS .7z not extracted" >&2
fi

cat > "${ROOT}/learn/lab/asap7/LIBEXTRAS.md" <<EOF
ASAP7 CCS/CDL extras come from The-OpenROAD-Project/asap7sc7p5t_28
via learn/scripts/fetch_asap7_libextras.sh.

Not a finish. Not Calibre. Views under ccs/ and cdl/ are gitignored.
CCS TC/WC refuse drops only when a matching .lib exists on disk.
CDL is leftover-named netlist reference only.
EOF

echo "ccs dest ${DEST_CCS} extracted=${extracted_ccs}"
echo "cdl dest ${DEST_CDL} copied=${copied_cdl} count=$(find "${DEST_CDL}" -name '*.cdl' | wc -l)"
ls "${DEST_CCS}" 2>/dev/null | head || true
ls "${DEST_CDL}" 2>/dev/null | head || true
