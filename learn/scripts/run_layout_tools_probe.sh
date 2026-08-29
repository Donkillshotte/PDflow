#!/usr/bin/env bash
# Probe Magic / Netgen / KLayout. Nangate45 signoff LVS remains KLayout.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
JSON="${ROOT}/learn/sim/reports/layout_tools_${VARIANT}.json"
GDS="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}/6_final.gds"
mkdir -p "$(dirname "${JSON}")"

# netgen-lvs package installs /usr/lib/netgen/bin/netgen (symlink netgen-lvs).
if [[ -z "${PATH##*netgen*}" ]]; then
  :
fi
if ! command -v netgen >/dev/null 2>&1 && command -v netgen-lvs >/dev/null 2>&1; then
  export PATH="/usr/lib/netgen/bin:${PATH}"
fi

magic_v="missing"
netgen_v="missing"
if command -v magic >/dev/null 2>&1; then
  magic_v="$(magic --version 2>/dev/null | head -1 || echo present)"
fi
if command -v netgen >/dev/null 2>&1 || command -v netgen-lvs >/dev/null 2>&1; then
  NG_BIN="$(command -v netgen || command -v netgen-lvs)"
  netgen_v="$("${NG_BIN}" -noconsole <<'NG' 2>/dev/null | head -1 || echo present
quit
NG
)"
  netgen_v="$(echo "${netgen_v}" | tr -d '\r' | head -1)"
  [[ -n "${netgen_v}" ]] || netgen_v="present"
fi

gds_ok=0
[[ -f "${GDS}" ]] && gds_ok=1

python3 - <<PY
import json, shutil
from pathlib import Path
payload = {
  "ok": True,
  "kind": "layout_tools",
  "magic": ${magic_v@Q},
  "magic_present": shutil.which("magic") is not None,
  "netgen": ${netgen_v@Q},
  "netgen_present": shutil.which("netgen") is not None or shutil.which("netgen-lvs") is not None,
  "klayout_present": shutil.which("klayout") is not None,
  "gds": ${GDS@Q},
  "gds_exists": bool(${gds_ok}),
  "nangate_magic_tech": False,
  "signoff_lvs": "klayout",
  "notes": [
    "Nangate45 signoff DRC/LVS is KLayout (FreePDK45.lydrc / FreePDK45.lylvs).",
    "Magic is present but only ships the 'minimum' tech here — no FreePDK45 .tech, so Magic LVS is not signoff.",
    "Netgen LVS is installed (netgen-lvs) for Sky130-class flows; this course PDK has no netgen setup.",
    "open_pdks targets Sky130/gf180, not FreePDK45/Nangate45.",
  ],
  "summary": "Magic={0} Netgen={1} KLayout={2}".format(
    "yes" if shutil.which("magic") else "no",
    "yes" if (shutil.which("netgen") or shutil.which("netgen-lvs")) else "no",
    "yes" if shutil.which("klayout") else "no",
  ),
}
Path(${JSON@Q}).write_text(json.dumps(payload, indent=2) + "\n")
print(payload["summary"])
PY
echo "OK layout tools probe → ${JSON}"
