#!/usr/bin/env bash
# Install Sandia Xyce into learn/tools/xyce.
# Primary: vlsida-eda linux-64 community build (Xyce 7.4) + system MPICH/OpenBLAS shims.
# Fallback: serial Trilinos+Xyce source (heavy).
# Does not drop ngspice. Do not restamp gold Dynamic IR 45.298.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREFIX="${XYCE_PREFIX:-${ROOT}/learn/tools/xyce}"
mkdir -p "${PREFIX}/bin" /tmp/vendor-src

have_xyce() {
  # shellcheck source=learn/lib/lab_tools.sh
  source "${ROOT}/learn/lib/lab_tools.sh"
  lab_tools_path "${ROOT}"
  if command -v Xyce >/dev/null 2>&1; then command -v Xyce; return 0; fi
  if [[ -x "${PREFIX}/bin/Xyce" ]]; then echo "${PREFIX}/bin/Xyce"; return 0; fi
  return 1
}

shim_xyce_libs() {
  local lib="${PREFIX}/lib"
  mkdir -p "${lib}"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libmpich12 libopenblas0-serial libgfortran5 libamd3 >/dev/null || true
  [[ -e /usr/lib/x86_64-linux-gnu/libamd.so.3 && ! -e "${lib}/libamd.so.2" ]] && \
    ln -sfn /usr/lib/x86_64-linux-gnu/libamd.so.3 "${lib}/libamd.so.2"
  [[ -e /usr/lib/x86_64-linux-gnu/libmpichfort.so.12 ]] && \
    ln -sfn /usr/lib/x86_64-linux-gnu/libmpichfort.so.12 "${lib}/libmpifort.so.12"
  [[ -e /usr/lib/x86_64-linux-gnu/libmpichcxx.so.12 ]] && \
    ln -sfn /usr/lib/x86_64-linux-gnu/libmpichcxx.so.12 "${lib}/libmpicxx.so.12"
  [[ -e /usr/lib/x86_64-linux-gnu/libmpi.so.12 ]] && \
    ln -sfn /usr/lib/x86_64-linux-gnu/libmpi.so.12 "${lib}/libmpi.so.12"
}

if [[ -x "${PREFIX}/bin/Xyce" ]]; then
  shim_xyce_libs
  export LD_LIBRARY_PATH="${PREFIX}/lib:${LD_LIBRARY_PATH:-}"
  if "${PREFIX}/bin/Xyce" -v >/dev/null 2>&1; then
    echo "OK Xyce already present: ${PREFIX}/bin/Xyce"
    "${PREFIX}/bin/Xyce" -v 2>&1 | head -3 || true
    exit 0
  fi
fi

echo "=== vlsida-eda linux-64 Xyce 7.4 ==="
TGZ="/tmp/vendor-src/xyce-conda.tar.bz2"
if [[ ! -f "${TGZ}" ]]; then
  python3 - <<'PY'
import json, urllib.request
from pathlib import Path
data = json.load(urllib.request.urlopen("https://api.anaconda.org/package/vlsida-eda/xyce", timeout=30))
files = data.get("files") or []
best = None
for f in files:
    name = str(f.get("basename") or "")
    if "linux-64" in name and name.endswith(".tar.bz2"):
        best = f
dl = (best or {}).get("download_url") or ""
if dl.startswith("//"):
    dl = "https:" + dl
if not dl:
    raise SystemExit("no linux-64 xyce tarball")
dest = Path("/tmp/vendor-src/xyce-conda.tar.bz2")
print("download", dl)
urllib.request.urlretrieve(dl, dest)
print("saved", dest.stat().st_size)
PY
fi
mkdir -p "${PREFIX}"
tar -xjf "${TGZ}" -C "${PREFIX}"
shim_xyce_libs
export LD_LIBRARY_PATH="${PREFIX}/lib:${LD_LIBRARY_PATH:-}"
if "${PREFIX}/bin/Xyce" -v 2>&1 | head -5; then
  echo "OK Xyce → ${PREFIX}/bin/Xyce"
  exit 0
fi

echo "FAIL community binary; see install log"
exit 1
