#!/usr/bin/env bash
# Fetch ASAP7 layer-1 public PDK (asap7_pdk_r1p7) into learn/lab/asap7/pdk.
# Gitignored. Not Calibre. Not a finish. Does not restamp gold 45.298 mV.
#
# Optional: ASAP7_PDK_SRC=/path/to/asap7_pdk_r1p7
# Optional: ASAP7_CALIBRE_SRC=/path/to/unpacked/ASU/calibre  (replaces placeholder)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="${ROOT}/learn/lab/asap7/pdk"
WORKDIR="${ASAP7_PDK_WORKDIR:-/tmp/asap7_pdk_r1p7}"
SRC="${ASAP7_PDK_SRC:-}"

mkdir -p "${DEST}"

if [[ -z "${SRC}" ]]; then
  if [[ ! -f "${WORKDIR}/models/hspice/7nm_TT_160803.pm" && ! -f "${WORKDIR}/models/hspice/7nm_TT.pm" ]]; then
    git clone --depth 1 https://github.com/The-OpenROAD-Project/asap7_pdk_r1p7.git "${WORKDIR}"
  fi
  SRC="${WORKDIR}"
fi

if [[ ! -d "${SRC}/models" ]]; then
  echo "FAIL: no models/ under ${SRC}" >&2
  exit 2
fi

# Copy the public tree, not .git. Placeholder calibre/ is expected.
# cp -a is enough for a 9.5 MB PDK.
rm -rf "${DEST}"
mkdir -p "${DEST}"
shopt -s dotglob
for item in "${SRC}"/*; do
  base="$(basename "${item}")"
  [[ "${base}" == ".git" ]] && continue
  cp -a "${item}" "${DEST}/"
done
shopt -u dotglob

if [[ -n "${ASAP7_CALIBRE_SRC:-}" ]]; then
  if [[ ! -d "${ASAP7_CALIBRE_SRC}" ]]; then
    echo "FAIL: ASAP7_CALIBRE_SRC is not a directory: ${ASAP7_CALIBRE_SRC}" >&2
    exit 2
  fi
  rm -rf "${DEST}/calibre"
  mkdir -p "${DEST}/calibre"
  cp -a "${ASAP7_CALIBRE_SRC}/." "${DEST}/calibre/"
  echo "calibre overlay from ${ASAP7_CALIBRE_SRC}"
fi

cat > "${DEST}/SOURCE.md" <<EOF
ASAP7 layer-1 public PDK copied from The-OpenROAD-Project/asap7_pdk_r1p7
via learn/scripts/fetch_asap7_pdk.sh.

Not a finish. Not Calibre unless ASAP7_CALIBRE_SRC replaced calibre/.
Views under learn/lab/asap7/pdk/ are gitignored.
Do not write .lvs.ok. Do not restamp gold 45.298 mV.
EOF

n_pm="$(find "${DEST}/models" -name '*.pm' | wc -l | tr -d ' ')"
n_rul="$(find "${DEST}/calibre" -name '*.rul' 2>/dev/null | wc -l | tr -d ' ')"
echo "pdk dest ${DEST}"
echo "hspice_pm ${n_pm}"
echo "calibre_rul ${n_rul} (0 means GitHub placeholder)"
ls "${DEST}/models/hspice" || true
ls "${DEST}/calibre/ruledirs" 2>/dev/null || true
