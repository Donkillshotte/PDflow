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
report_checks -path_delay max -slack_max 0 -group_path_count 100 -format end
report_clock_min_period
puts "STA_SIGNOFF_DONE ${VARIANT}"
EOF

rg -q 'STA_SIGNOFF_DONE' "${STA_LOG}" || { echo "FAIL STA signoff"; exit 1; }

METRICS="${ROOT}/learn/sim/reports/.sta_metrics_${VARIANT}.json"
python3 - <<PY
import json
import re
from pathlib import Path

log = Path("${STA_LOG}").read_text()
finish_p = Path("${FINISH_RPT}")
finish = finish_p.read_text() if finish_p.is_file() else ""


def first(pat: str, text: str):
    m = re.search(pat, text)
    return m.group(1) if m else None


wns = first(r"wns max\s+([-\d.]+)", log) or first(r"wns max\s+([-\d.]+)", finish)
tns = first(r"tns max\s+([-\d.]+)", log) or first(r"tns max\s+([-\d.]+)", finish)
period = first(r"period_min\s*=\s*([\d.]+)", log) or first(r"period_min\s*=\s*([\d.]+)", finish)
# Count from this OpenSTA run. A missing finish_rpt used to stamp viol 0.
viol = sum(1 for line in log.splitlines() if "(VIOLATED)" in line)
endpoint = None
kind = None
for line in log.splitlines():
    if "(VIOLATED)" not in line:
        continue
    endpoint = line.split()[0] if line.split() else None
    if "(output)" in line or (endpoint or "").startswith(("resp_", "req_")):
        kind = "output"
        if endpoint and "(output)" not in endpoint:
            endpoint = f"{endpoint} (output)"
    else:
        kind = "register"
    break
timing = {
    "wns_ns": float(wns or 0),
    "tns": float(tns or 0),
    "setup_violations": int(viol),
    "period_min_ns": float(period) if period else None,
}
if endpoint:
    timing["worst_endpoint"] = endpoint
if kind:
    timing["wns_kind"] = kind
m = {"timing": timing}
Path("${METRICS}").write_text(json.dumps(m, indent=2))
print("STA_PARSE", json.dumps(m["timing"]))
PY

python3 "${ROOT}/learn/scripts/signoff_eval.py" --pillar timing --metrics "${METRICS}" --out "${OUT}.eval" --repo "${ROOT}" || true

python3 - <<PY
import json
import sys
from pathlib import Path
root = Path("${ROOT}")
sys.path.insert(0, str(root / "learn/scripts"))
from stamp_signoff_all import leftover_from_lib_corners, leftover_from_sta, with_mcmm_leftover_summary, with_setup_leftover_summary
metrics = json.loads(Path("${METRICS}").read_text())
evald = {}
ep = Path("${OUT}.eval")
if ep.exists():
    evald = json.loads(ep.read_text())
out = {
  "kind": "sta_signoff",
  "variant": "${VARIANT}",
  "engine": "opensta",
  "timing": metrics["timing"],
  "evaluation": evald.get("pillars", {}).get("timing", {}),
  "ok": evald.get("pillars", {}).get("timing", {}).get("ok"),
  "summary": f"STA WNS {metrics['timing']['wns_ns']} ns · TNS {metrics['timing']['tns']} · viol {metrics['timing']['setup_violations']}",
  "artifacts": {
    "finish_rpt": "${FINISH_RPT}",
    "sta_log": "${STA_LOG}",
  },
}
setup = leftover_from_sta(out)
if setup:
    out["leftover"] = setup
    out["summary"] = with_setup_leftover_summary(out.get("summary"), setup)
mcmm = leftover_from_lib_corners()
if mcmm:
    out["mcmm_leftover"] = mcmm
    out["summary"] = with_mcmm_leftover_summary(out.get("summary"), mcmm)
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
python3 "${ROOT}/learn/scripts/signoff_require_ok.py" "${OUT}"
