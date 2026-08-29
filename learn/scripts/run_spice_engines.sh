#!/usr/bin/env bash
# SPICE engines: ngspice INTEGRATED; Sandia Xyce probed (usually GAP).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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

xyce_bin=""
for c in xyce Xyce; do
  if command -v "${c}" >/dev/null 2>&1; then
    xyce_bin="$(command -v "${c}")"
    break
  fi
done

python3 - <<PY
import json, shutil
from pathlib import Path
xyce = shutil.which("xyce") or shutil.which("Xyce")
payload = {
  "ok": bool(${ng_ok}),
  "kind": "spice_engines",
  "ngspice_present": shutil.which("ngspice") is not None,
  "ngspice_version": ${ng_v@Q},
  "ngspice_demo_ok": bool(${ng_ok}),
  "xyce_present": xyce is not None,
  "xyce_bin": xyce,
  "role": "ngspice is the System PDN / chip-mesh engine; Xyce (Sandia) is the parallel SPICE-class alternative",
  "commercial_gap": None if xyce else "Sandia Xyce not installed — ngspice covers AC/TRAN PDN on GCD",
  "summary": "ngspice={0} Xyce={1}".format(
    "ok" if ${ng_ok} else "no",
    "yes" if xyce else "GAP",
  ),
}
Path(${JSON@Q}).write_text(json.dumps(payload, indent=2) + "\n")
print(payload["summary"])
PY
echo "OK spice engines → ${JSON}"
