#!/usr/bin/env bash
# STA signoff: OpenSTA on 6_final.v + SPEF + SDC vs golden-gcd.json
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
REPORTS="${FLOW}/reports/nangate45/gcd/${VARIANT}"
LIB="${FLOW}/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
SDC="${FLOW}/designs/nangate45/gcd-tutorial/constraint.sdc"
V="${RES}/6_final.v"
SPEF="${RES}/6_final.spef"
FINISH_RPT="${REPORTS}/6_finish.rpt"

[[ -f "${V}" ]] || { echo "FAIL missing ${V}"; exit 1; }

OUT="${ROOT}/learn/sim/reports/sta_signoff_${VARIANT}.json"
mkdir -p "$(dirname "${OUT}")"

# Parse finish report (OpenROAD signoff numbers)
parse_finish() {
  local wns tns viol period
  wns="$(rg -m1 'wns max\s+([-\d.]+)' "${FINISH_RPT}" -or '$1' 2>/dev/null || echo "")"
  tns="$(rg -m1 'tns max\s+([-\d.]+)' "${FINISH_RPT}" -or '$1' 2>/dev/null || echo "")"
  viol="$(rg -c 'VIOLATED' "${FINISH_RPT}" 2>/dev/null || echo 0)"
  period="$(rg -m1 'period_min\s*=\s*([\d.]+)' "${FINISH_RPT}" -or '$1' 2>/dev/null || echo "")"
  echo "${wns}|${tns}|${viol}|${period}"
}

IFS='|' read -r WNS TNS VIOL PERIOD <<< "$(parse_finish)"

# Optional independent STA run with SPEF
STA_LOG="${ROOT}/learn/sim/reports/sta_signoff_${VARIANT}.log"
SPEF_LINE=""
[[ -f "${SPEF}" ]] && SPEF_LINE="read_spef ${SPEF}"

cd "${FLOW}"
sta -no_init -exit <<EOF 2>&1 | tee "${STA_LOG}"
read_liberty ${LIB}
read_verilog ${V}
link_design gcd
read_sdc ${SDC}
${SPEF_LINE}
report_wns
report_tns
report_worst_slack -max
report_checks -format end -group_path_count 3
puts "STA_SIGNOFF_DONE ${VARIANT}"
EOF

rg -q 'STA_SIGNOFF_DONE' "${STA_LOG}" || { echo "FAIL STA signoff"; exit 1; }

STA_WNS="$(rg -m1 'wns max\s+([-\d.]+)' "${STA_LOG}" -or '$1' 2>/dev/null || echo "${WNS}")"
STA_TNS="$(rg -m1 'tns max\s+([-\d.]+)' "${STA_LOG}" -or '$1' 2>/dev/null || echo "${TNS}")"

METRICS="${ROOT}/learn/sim/reports/.sta_metrics_${VARIANT}.json"
python3 - <<PY
import json
from pathlib import Path
m = {
  "timing": {
    "wns_ns": float("${STA_WNS}" or "${WNS}" or 0),
    "tns": float("${STA_TNS}" or "${TNS}" or 0),
    "setup_violations": int("${VIOL}" or 0),
    "period_min_ns": float("${PERIOD}" or 0) if "${PERIOD}" else None,
  }
}
Path("${METRICS}").write_text(json.dumps(m, indent=2))
PY

python3 "${ROOT}/learn/scripts/signoff_eval.py" --pillar timing --metrics "${METRICS}" --out "${OUT}.eval" --repo "${ROOT}" || true

python3 - <<PY
import json
from pathlib import Path
root = Path("${ROOT}")
metrics = json.loads(Path("${METRICS}").read_text())
evald = {}
ep = Path("${OUT}.eval")
if ep.exists():
    evald = json.loads(ep.read_text())
out = {
  "kind": "sta_signoff",
  "variant": "${VARIANT}",
  "engine": "opensta+finish_rpt",
  "timing": metrics["timing"],
  "evaluation": evald.get("pillars", {}).get("timing", {}),
  "ok": evald.get("pillars", {}).get("timing", {}).get("ok"),
  "summary": f"STA WNS {metrics['timing']['wns_ns']} ns · TNS {metrics['timing']['tns']} · viol {metrics['timing']['setup_violations']}",
  "artifacts": {
    "finish_rpt": "${FINISH_RPT}",
    "sta_log": "${STA_LOG}",
  },
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("STA_SIGNOFF_JSON", "${OUT}")
print(out["summary"])
PY

# Best-effort educational IR-aware overlay. Never fails nominal STA / WNS.
IR_SCRIPT="${ROOT}/learn/scripts/run_sta_ir_aware.sh"
if [[ -x "${IR_SCRIPT}" || -f "${IR_SCRIPT}" ]]; then
  if FLOW_VARIANT="${VARIANT}" "${IR_SCRIPT}"; then
    python3 - <<PY
import json
from pathlib import Path
out_p = Path("${OUT}")
ir_p = Path("${ROOT}/learn/sim/reports/sta_ir_aware_${VARIANT}.json")
blob = json.loads(out_p.read_text())
if ir_p.is_file():
    ir = json.loads(ir_p.read_text())
    sta = ir.get("sta") or {}
    blob["ir_aware"] = {
        "report": str(ir_p),
        "ok": ir.get("ok"),
        "slack_ns": sta.get("slack_ns"),
        "slack_ir_ns": sta.get("slack_ir_ns"),
        "n_joined": sta.get("n_joined"),
        "n_gates": sta.get("n_gates"),
        "degradation_ps": sta.get("degradation_ps"),
        "note": "educational NLDM × ITerm V; does not change nominal WNS",
    }
    out_p.write_text(json.dumps(blob, indent=2) + "\\n")
    print(
        f"STA_IR_AWARE slack={sta.get('slack_ns')} slack_ir={sta.get('slack_ir_ns')} "
        f"joined={sta.get('n_joined')}/{sta.get('n_gates')}"
    )
PY
  else
    echo "STA_IR_AWARE_SKIP (nominal STA unchanged)"
  fi
fi

echo "STA_SIGNOFF_DONE ${VARIANT}"
