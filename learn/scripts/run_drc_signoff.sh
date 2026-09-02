#!/usr/bin/env bash
# DRC signoff: route DRC report + KLayout GDS DRC (unified JSON)
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VARIANT="${FLOW_VARIANT:-flowlab}"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
REPORTS="${FLOW}/reports/nangate45/gcd/${VARIANT}"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
GDS="${RES}/6_final.gds"
ROUTE_DRC="${REPORTS}/5_route_drc.rpt"
OUT="${ROOT}/learn/sim/reports/drc_signoff_${VARIANT}.json"
LOG="${ROOT}/learn/sim/reports/drc_signoff_${VARIANT}.log"

[[ -f "${GDS}" ]] || { echo "FAIL missing ${GDS} — run finish first"; exit 1; }
mkdir -p "$(dirname "${OUT}")"
: > "${LOG}"

ROUTE_LINES=0
if [[ -f "${ROUTE_DRC}" ]]; then
  ROUTE_LINES="$(wc -l < "${ROUTE_DRC}" | tr -d ' ')"
  echo "Route DRC lines: ${ROUTE_LINES}" | tee -a "${LOG}"
else
  echo "WARN route DRC report missing" | tee -a "${LOG}"
fi

echo "--- KLayout GDS DRC ---" | tee -a "${LOG}"
cd "${FLOW}"
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT="${VARIANT}" \
     CORE_UTILIZATION="${CORE_UTILIZATION:-35}" \
     OPENROAD_EXE="${OPENROAD_EXE:-openroad}" \
     OPENSTA_EXE="${OPENSTA_EXE:-sta}" \
     YOSYS_EXE="${YOSYS_EXE:-yosys}" \
     drc 2>&1 | tee -a "${LOG}"

LYRDB="${REPORTS}/6_drc.lyrdb"
GDS_VIOL=0
if [[ -f "${LYRDB}" ]]; then
  # KLayout lyrdb is XML; count violation items heuristically
  GDS_VIOL="$(python3 "${ROOT}/learn/scripts/parse_signoff_artifacts.py" --kind drc --path "${LYRDB}" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("items",0))' || echo 0)"
  echo "GDS DRC violations (items): ${GDS_VIOL}" | tee -a "${LOG}"
else
  echo "WARN lyrdb missing" | tee -a "${LOG}"
fi

METRICS="${ROOT}/learn/sim/reports/.drc_metrics_${VARIANT}.json"
python3 - <<PY
import json
from pathlib import Path
m = {"geometry": {"route_drc_lines": int("${ROUTE_LINES}"), "gds_drc_violations": int("${GDS_VIOL}")}}
Path("${METRICS}").write_text(json.dumps(m, indent=2))
PY

python3 "${ROOT}/learn/scripts/signoff_eval.py" --pillar geometry --metrics "${METRICS}" --out "${OUT}.eval" --repo "${ROOT}" || true

python3 - <<PY
import json
from pathlib import Path
metrics = json.loads(Path("${METRICS}").read_text())
evald = json.loads(Path("${OUT}.eval").read_text()) if Path("${OUT}.eval").exists() else {}
geom = metrics["geometry"]
ev = evald.get("pillars", {}).get("geometry", {})
artifact_parse = {}
if Path("${LYRDB}").exists():
    import subprocess
    raw = subprocess.check_output([
        "python3", "${ROOT}/learn/scripts/parse_signoff_artifacts.py",
        "--kind", "drc", "--path", "${LYRDB}",
    ], text=True)
    artifact_parse = json.loads(raw)
out = {
  "kind": "drc_signoff",
  "variant": "${VARIANT}",
  "geometry": geom,
  "evaluation": ev,
  "artifact_parse": artifact_parse,
  "ok": ev.get("ok"),
  "summary": f"Route DRC {geom['route_drc_lines']} lines · GDS DRC {geom['gds_drc_violations']} items",
  "artifacts": {"route_drc": "${ROUTE_DRC}", "gds_lyrdb": "${LYRDB}"},
}
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("DRC_SIGNOFF_JSON", "${OUT}")
print(out["summary"])
PY

echo "DRC_SIGNOFF_DONE ${VARIANT}"
