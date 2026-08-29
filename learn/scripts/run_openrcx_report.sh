#!/usr/bin/env bash
# OpenRCX / SPEF summary (StarRC-class role in this OSS flow).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
SPEF="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/${VARIANT}/6_final.spef"
RULES="${ROOT}/tools/OpenROAD-flow-scripts/flow/platforms/nangate45/rcx_patterns.rules"
JSON="${ROOT}/learn/sim/reports/openrcx_${VARIANT}.json"
[[ -f "${SPEF}" ]] || { echo "FAIL manca ${SPEF} — esegui finish"; exit 1; }

python3 - <<PY
import json
from pathlib import Path
spef = Path(${SPEF@Q})
text = spef.read_text(errors="replace")
nets = text.count("*D_NET") + text.count("*R_NET")
caps = text.count("*CAP")
ress = text.count("*RES")
json.dump({
  "ok": nets > 0,
  "kind": "openrcx_spef",
  "variant": ${VARIANT@Q},
  "spef": str(spef),
  "bytes": spef.stat().st_size,
  "nets": nets,
  "cap_records": caps,
  "res_records": ress,
  "rcx_rules": ${RULES@Q},
  "rules_exist": Path(${RULES@Q}).exists(),
  "commercial_gap": "StarRC / Raphael not licensed — OpenRCX SPEF is the extract used at finish",
  "summary": f"OpenRCX SPEF {nets} nets · {caps} CAP · {ress} RES · {spef.stat().st_size} B",
}, open(${JSON@Q}, "w"), indent=2)
print(json.load(open(${JSON@Q}))["summary"])
PY
echo "OK openrcx ${VARIANT} → ${JSON}"
