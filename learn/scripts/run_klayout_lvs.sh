#!/usr/bin/env bash
# LVS signoff via ORFS make lvs (KLayout + CDL)
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
REPORTS="${FLOW}/reports/nangate45/gcd/${VARIANT}"
GDS="${RES}/6_final.gds"
LVSDB="${RES}/6_lvs.lvsdb"
LOG="${FLOW}/logs/nangate45/gcd/${VARIANT}/6_lvs.log"
STAMP="${RES}/.lvs.ok"
OUT="${ROOT}/learn/sim/reports/lvs_signoff_${VARIANT}.json"

[[ -f "${GDS}" ]] || { echo "FAIL missing ${GDS} — run finish first"; exit 1; }
mkdir -p "$(dirname "${OUT}")"

LYLVS="${ROOT}/learn/platforms/nangate45/lvs/FreePDK45.lylvs"
ORFS_LVS="${FLOW}/platforms/nangate45/lvs/FreePDK45.lylvs"
if [[ ! -f "${LYLVS}" ]]; then
  echo "FAIL missing ${LYLVS} — see learn/reference/oss-integrations.md"
  python3 - <<PY
import json
from pathlib import Path
out = {
  "kind": "lvs_signoff",
  "variant": "${VARIANT}",
  "equivalence": {"lvs_pass": False, "lvs_errors": 0, "make_rc": 2, "missing_lylvs": True},
  "evaluation": {"checks": [{"id": "lvs_runset", "label": "LVS runset present", "actual": False, "target": True, "ok": False}], "ok": False},
  "ok": False,
  "summary": "LVS FAIL · missing FreePDK45.lylvs",
  "artifacts": {"lylvs_expected": "${LYLVS}", "log": "${LOG}"},
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
PY
  echo "LVS_SIGNOFF_DONE ${VARIANT}"
  exit 0
fi

# Ensure ORFS platform path (tools/ may be gitignored clone)
mkdir -p "$(dirname "${ORFS_LVS}")"
cp "${LYLVS}" "${ORFS_LVS}"

DESIGN_CDL="${RES}/6_final.cdl"
DEF_FILE="${RES}/6_final.def"
LIB_CDL="${FLOW}/platforms/nangate45/cdl/NangateOpenCellLibrary.cdl"
OBJ="${FLOW}/objects/nangate45/gcd/${VARIANT}"
PREP_CDL="${OBJ}/6_final_lvs_filtered.cdl"
mkdir -p "${OBJ}" "$(dirname "${LOG}")"
python3 "${ROOT}/learn/scripts/prepare_lvs_netlist.py" \
  --design-cdl "${DESIGN_CDL}" \
  --library-cdl "${LIB_CDL}" \
  --def "${DEF_FILE}" \
  --top gcd \
  --out "${PREP_CDL}"

cd "${FLOW}"
set +e
# Direct KLayout compare on the prepared CDL (unused library cells dropped,
# FILLCELL instances taken from DEF). ORFS make lvs concat is not used.
klayout -b \
  -rd "in_gds=${GDS}" \
  -rd "cdl_file=${PREP_CDL}" \
  -rd "report_file=${LVSDB}" \
  -r "${LYLVS}" \
  2>&1 | tee /tmp/lvs-signoff-${VARIANT}.log | tee "${LOG}"
MAKE_RC=$?
set -e

LVS_PASS=false
LVS_ERRORS=0
COMBINED_LOG="/tmp/lvs-signoff-${VARIANT}.log"
if [[ -f "${LVSDB}" ]]; then
  if rg -q 'LVS not supported' "${LVSDB}" 2>/dev/null; then
    echo "WARN LVS not supported on platform marker"
  elif rg -q '<error' "${LVSDB}" 2>/dev/null; then
    LVS_ERRORS="$(rg -c '<error' "${LVSDB}" || echo 1)"
  fi
fi
# KLayout writes 6_lvs.lvsdb even when netlists do not match.
if rg -q "Netlists match" "${LOG}" "${COMBINED_LOG}" 2>/dev/null && \
   ! rg -q "Netlists don't match" "${LOG}" "${COMBINED_LOG}" 2>/dev/null; then
  LVS_PASS=true
fi
if rg -q "Netlists don't match" "${LOG}" "${COMBINED_LOG}" 2>/dev/null; then
  LVS_PASS=false
  echo "WARN KLayout: Netlists don't match (educational LVS still recorded)"
fi

METRICS="${ROOT}/learn/sim/reports/.lvs_metrics_${VARIANT}.json"
python3 - <<PY
import json
from pathlib import Path
lvs_pass = "${LVS_PASS}" == "true"
m = {"equivalence": {"lvs_pass": lvs_pass, "lvs_errors": int("${LVS_ERRORS}"), "make_rc": int("${MAKE_RC}")}}
Path("${METRICS}").write_text(json.dumps(m, indent=2))
PY

python3 "${ROOT}/learn/scripts/signoff_eval.py" --pillar equivalence --metrics "${METRICS}" --out "${OUT}.eval" --repo "${ROOT}" || true

python3 - <<PY
import json
from pathlib import Path
metrics = json.loads(Path("${METRICS}").read_text())
evald = json.loads(Path("${OUT}.eval").read_text()) if Path("${OUT}.eval").exists() else {}
eq = metrics["equivalence"]
ev = evald.get("pillars", {}).get("equivalence", {})
artifact_parse = {}
import subprocess
log_path = "${LOG}" if Path("${LOG}").exists() else "/tmp/lvs-signoff-${VARIANT}.log"
try:
    lvsdb_path = "${LVSDB}" if Path("${LVSDB}").exists() else "/dev/null"
    raw = subprocess.check_output([
        "python3", "${ROOT}/learn/scripts/parse_signoff_artifacts.py",
        "--kind", "lvs", "--path", lvsdb_path, "--log", log_path,
    ], text=True)
    artifact_parse = json.loads(raw)
except Exception:
    pass
out = {
  "kind": "lvs_signoff",
  "variant": "${VARIANT}",
  "equivalence": eq,
  "evaluation": ev,
  "artifact_parse": artifact_parse,
  "ok": eq["lvs_pass"],
  "must_connect": (artifact_parse.get("lvsdb") or {}).get("must_connect", 0),
  "educational_note": (
      "KLayout compare on filtered CDL + DEF fillers + well→VDD/VSS. "
      "FILL/TAP/VIA are blank_circuit (empty Nangate CDL, no invented devices). "
      "XNOR2/MUX2/NAND3-4/OAI22/AND3 flatten. Remaining must-connect is DFF_X2 "
      "(Nangate split wells). Flatten-all before extract fails the compare."
  ),
  "summary": f"LVS {'PASS' if eq['lvs_pass'] else 'FAIL'} · errors {eq['lvs_errors']}",
  "artifacts": {"lvsdb": "${LVSDB}", "log": "${LOG}"},
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("LVS_SIGNOFF_JSON", "${OUT}")
print(out["summary"])
PY

if [[ "${LVS_PASS}" == "true" ]]; then
  date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP}"
else
  rm -f "${STAMP}"
fi
echo "LVS_SIGNOFF_DONE ${VARIANT}"
