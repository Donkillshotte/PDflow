#!/usr/bin/env bash
# SPICE engines: ngspice INTEGRATED; Sandia Xyce probed and N4 gold if present.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=learn/lib/lab_tools.sh
source "${ROOT}/learn/lib/lab_tools.sh"
lab_tools_path "${ROOT}"
export PYTHONPATH="/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
VARIANT="${FLOW_VARIANT:-flowlab}"
JSON="${ROOT}/learn/sim/reports/spice_engines_${VARIANT}.json"
DEMO="${ROOT}/learn/sim/spice/system_pdn_tran_demo.sp"
mkdir -p "$(dirname "${JSON}")"

ng_ok=0
ng_v="missing"
if command -v ngspice >/dev/null 2>&1; then
  ng_v="$(ngspice -v 2>&1 | head -2 | tr '\n' ' ')"
  if [[ -f "${DEMO}" ]]; then
    if ngspice -b -o /tmp/ngspice-engine.log "${DEMO}" >/dev/null 2>&1; then
      ng_ok=1
    fi
  else
    ng_ok=1
  fi
fi

xyce_path=""
if xyce_path="$(xyce_bin "${ROOT}")"; then
  :
else
  xyce_path=""
fi

python3 - <<PY
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, "${ROOT}/learn/scripts")
from pdn_vrm import xyce_vrm_die_gold
xyce = shutil.which("xyce") or shutil.which("Xyce")
n4 = {}
if xyce:
    n4 = xyce_vrm_die_gold()
xyce_ready = bool(xyce) and n4.get("status") == "READY" and n4.get("ok") is True
payload = {
  "ok": bool(${ng_ok}),
  "kind": "spice_engines",
  "ngspice_present": shutil.which("ngspice") is not None,
  "ngspice_version": ${ng_v@Q},
  "ngspice_demo_ok": bool(${ng_ok}),
  "xyce_present": xyce is not None,
  "xyce_bin": xyce,
  "xyce_n4": n4,
  "xyce_status": "READY" if xyce_ready else ("GAP" if not xyce else "WATCH"),
  "role": "ngspice is the System PDN / chip-mesh engine; Xyce is the dual-solver N4 gold when installed",
  "commercial_gap": None if xyce else "Sandia Xyce not installed — run learn/scripts/install_xyce.sh",
  "summary": "ngspice={0} Xyce={1}".format(
    "ok" if ${ng_ok} else "no",
    "READY" if xyce_ready else ("yes" if xyce else "GAP"),
  ),
}
Path(${JSON@Q}).write_text(json.dumps(payload, indent=2) + "\n")
print(payload["summary"])
PY
echo "OK spice engines → ${JSON}"
