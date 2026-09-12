#!/usr/bin/env bash
# DRC signoff: route DRC report + KLayout GDS DRC (unified JSON)
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" drc-signoff bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/native_eda_env.sh"
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

echo "--- KLayout GDS DRC (current finish GDS) ---" | tee -a "${LOG}"
LYDRC="${FLOW}/platforms/nangate45/drc/FreePDK45.lydrc"
LYRDB="${REPORTS}/6_drc.lyrdb"
KLAYOUT_BIN="${KLAYOUT_CMD:-klayout}"
KLAYOUT_REAL="$(command -v "${KLAYOUT_BIN}" 2>/dev/null || true)"
if [[ -z "${KLAYOUT_REAL}" || ! -f "${LYDRC}" ]]; then
  echo "FAIL missing KLayout or DRC deck" | tee -a "${LOG}"
  exit 1
fi
KLAYOUT_PREFIX="$(cd "$(dirname "${KLAYOUT_REAL}")/.." && pwd)"
RUBY_PATHS=()
for ruby_dir in "${KLAYOUT_PREFIX}/lib/x86_64-linux-gnu/ruby/3.2.0" "${KLAYOUT_PREFIX}/lib/ruby/3.2.0" "${KLAYOUT_PREFIX}/lib/ruby/vendor_ruby"; do
  [[ -d "${ruby_dir}" ]] && RUBY_PATHS+=("${ruby_dir}")
done
if [[ "${#RUBY_PATHS[@]}" -gt 0 ]]; then
  export RUBYLIB="$(IFS=:; echo "${RUBY_PATHS[*]}")${RUBYLIB:+:${RUBYLIB}}"
fi
"${KLAYOUT_REAL}" -b -rd "in_gds=${GDS}" -rd "report_file=${LYRDB}" -r "${LYDRC}" 2>&1 | tee -a "${LOG}"

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
import sys
from pathlib import Path
root = Path("${ROOT}")
sys.path.insert(0, str(root / "learn/scripts"))
from stamp_signoff_all import leftover_from_deck, with_deck_leftover_summary
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
deck = leftover_from_deck()
if deck:
    out["leftover"] = deck
    out["summary"] = with_deck_leftover_summary(out.get("summary"), deck)
Path("${OUT}").write_text(json.dumps(out, indent=2) + "\\n")
print("DRC_SIGNOFF_JSON", "${OUT}")
print(out["summary"])
PY

echo "DRC_SIGNOFF_DONE ${VARIANT}"
python3 "${ROOT}/learn/scripts/signoff_require_ok.py" "${OUT}"
