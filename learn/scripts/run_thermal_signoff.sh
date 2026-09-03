#!/usr/bin/env bash
# Thermal signoff: UVA HotSpot architecture compact model (°C) + IR/droop secondary.
# Not Ansys / not foundry. Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=learn/lib/lab_tools.sh
source "${ROOT}/learn/lib/lab_tools.sh"
lab_tools_path "${ROOT}"

VARIANT="${FLOW_VARIANT:-flowlab}"
OUT="${ROOT}/learn/sim/reports/thermal_signoff_${VARIANT}.json"
LOG="${ROOT}/learn/sim/reports/thermal_signoff_${VARIANT}.log"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
DEFN="${RES}/6_final.def"
CHIP="${ROOT}/learn/sim/reports/pdn_chip_ir_${VARIANT}.json"
ACT="${ROOT}/learn/sim/reports/activity_power_${VARIANT}.log"
DECK="${ROOT}/learn/sim/thermal/${VARIANT}"
CFG_SRC="${ROOT}/learn/tools/hotspot/template.config"
if [[ ! -f "${CFG_SRC}" ]]; then
  CFG_SRC="${ROOT}/learn/reference/hotspot.template.config"
fi

mkdir -p "$(dirname "${OUT}")" "${DECK}"
: > "${LOG}"

IR_MV=0
DROOP_MV=0
if [[ -f "${CHIP}" ]]; then
  read -r IR_MV DROOP_MV <<< "$(python3 - <<PY
import json
from pathlib import Path
c = json.loads(Path("${CHIP}").read_text())
ir = float(c.get("static", {}).get("worst_ir", 0) or 0) * 1e3
dr = float(c.get("transient", {}).get("worst_droop", 0) or 0) * 1e3
print(ir, dr)
PY
)"
fi

HS=""
if HS="$(hotspot_bin "${ROOT}")"; then
  echo "HOTSPOT_BIN ${HS}" | tee -a "${LOG}"
else
  echo "HOTSPOT missing — install via learn/scripts/install_hotspot.sh" | tee -a "${LOG}"
fi

COMBINED="$(python3 - <<PY
print(float("${IR_MV}") + float("${DROOP_MV}"))
PY
)"

HOTSPOT_OK=false
TMAX=""
TMIN=""
HS_NOTE="HotSpot binary missing"
if [[ -n "${HS}" && -f "${DEFN}" ]]; then
  python3 "${ROOT}/learn/scripts/write_hotspot_deck.py" \
    --def "${DEFN}" \
    --activity-log "${ACT}" \
    --out-dir "${DECK}" | tee -a "${LOG}"
  CFG="${DECK}/hotspot.config"
  if [[ -f "${CFG_SRC}" ]]; then
    cp -f "${CFG_SRC}" "${CFG}"
  else
    echo "FAIL missing HotSpot template.config" | tee -a "${LOG}"
  fi
  if [[ -f "${CFG}" ]]; then
    set +e
    "${HS}" -c "${CFG}" -f "${DECK}/gcd.flp" -p "${DECK}/gcd.ptrace" \
      -steady_file "${DECK}/gcd.steady" -model_type block \
      >> "${LOG}" 2>&1
    HS_RC=$?
    set -e
    if [[ "${HS_RC}" -eq 0 && -f "${DECK}/gcd.steady" ]]; then
      eval "$(python3 - <<PY
import json, sys
sys.path.insert(0, "${ROOT}/learn/scripts")
from write_hotspot_deck import parse_steady
rec = parse_steady(__import__("pathlib").Path("${DECK}/gcd.steady"))
print("TMAX=" + str(rec.get("t_max_c", "")))
print("TMIN=" + str(rec.get("t_min_c", "")))
print("HOTSPOT_OK=" + ("true" if rec.get("ok") else "false"))
open("${DECK}/parse.json","w").write(json.dumps(rec, indent=2)+"\\n")
PY
)"
      HS_NOTE="architecture compact model (UVA HotSpot), not foundry / not Ansys"
    else
      HS_NOTE="HotSpot ran rc=${HS_RC} — see ${LOG}"
    fi
  fi
fi

python3 - <<PY
import json
from pathlib import Path
tmax = "${TMAX}"
tmin = "${TMIN}"
hs_ok = "${HOTSPOT_OK}" == "true"
try:
    tmax_f = float(tmax) if tmax not in ("", "None") else None
except ValueError:
    tmax_f = None
try:
    tmin_f = float(tmin) if tmin not in ("", "None") else None
except ValueError:
    tmin_f = None
# Educational bound 85 °C. Tiny GCD + package R_ja is far below.
bound = 85.0
temp_ok = bool(hs_ok and tmax_f is not None and tmax_f <= bound)
proxy_ok = float("${COMBINED}") <= 50.0
ok = temp_ok
status = "READY" if ok else ("GAP" if not hs_ok else "WATCH")
out = {
  "kind": "thermal_signoff",
  "variant": "${VARIANT}",
  "status": status,
  "thermal": {
    "engine": "hotspot",
    "kind": "thermal_hotspot",
    "t_max_c": tmax_f,
    "t_min_c": tmin_f,
    "t_bound_c": bound,
    "chip_ir_mv": float("${IR_MV}"),
    "chip_droop_mv": float("${DROOP_MV}"),
    "combined_proxy_mv": float("${COMBINED}"),
    "note": "${HS_NOTE}",
  },
  "evaluation": {
    "checks": [
      {
        "id": "hotspot_tmax_c",
        "label": "HotSpot t_max (°C)",
        "actual": tmax_f,
        "target": bound,
        "ok": temp_ok,
        "note": "architecture compact model",
      },
      {
        "id": "ir_droop_proxy_mv",
        "label": "Secondary IR+droop proxy (mV)",
        "actual": float("${COMBINED}"),
        "target": 50.0,
        "ok": proxy_ok,
        "note": "kept as a labeled secondary check; not the pass criterion",
      },
    ],
    "ok": ok,
  },
  "ok": ok,
  "summary": (
      f"HotSpot t_max={tmax_f:.2f} °C" if tmax_f is not None
      else "Thermal GAP · HotSpot not READY"
  ) + f" · IR+droop proxy {float('${COMBINED}'):.2f} mV",
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\n")
print("THERMAL_SIGNOFF_JSON", "${OUT}")
print(out["summary"])
if not ok:
    raise SystemExit(1)
PY

echo "THERMAL_SIGNOFF_DONE ${VARIANT}"
