#!/usr/bin/env bash
# Validazione esaustiva fasi corso + FlowLab + catena power.
# Richiede Studio su 127.0.0.1:43217 per i test API (opzionale).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAIL=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; FAIL=1; }

echo "== Fasi lezione 00–07 =="
for id in 00-intro 01-constraints 02-synthesis 03-floorplan 04-placement 05-cts 06-routing 07-finish; do
  dir="${ROOT}/learn/lessons/${id}"
  for f in README.md LAB.md run.sh; do
    [[ -f "${dir}/${f}" ]] && ok "${id}/${f}" || bad "manca ${id}/${f}"
  done
  [[ -x "${dir}/run.sh" ]] && ok "${id}/run.sh executable" || bad "${id}/run.sh non eseguibile"
  bash -n "${dir}/run.sh" && ok "${id}/run.sh syntax" || bad "${id}/run.sh syntax error"
  rg -q 'Catena power|SPICE|power' "${dir}/README.md" && ok "${id} power section" || bad "${id} README senza power/SPICE"
done

echo "== powerChainLessons.ts copertura =="
for id in 00-intro 01-constraints 02-synthesis 03-floorplan 04-placement 05-cts 06-routing 07-finish; do
  rg -q "lessonId: \"${id}\"" "${ROOT}/studio/src/lib/powerChainLessons.ts" \
    && ok "powerChain ${id}" || bad "powerChainLessons manca ${id}"
done

echo "== FlowLab 9 fasi =="
for phase in rtl synth floorplan pdn place cts route finish pkg; do
  rg -q "id: \"${phase}\"" "${ROOT}/studio/src/components/flowlab/phases.ts" \
    && ok "phase ${phase}" || bad "manca fase ${phase}"
done

echo "== Azioni power in run.ts =="
for action in rtl_sim synth floorplan gridcheck place cts route finish \
  activity_power chip_pdn_ir system_pdn export_spice_lab power_chain; do
  rg -q "\"${action}\"" "${ROOT}/studio/src/lib/run.ts" \
    && ok "action ${action}" || bad "run.ts senza ${action}"
done

echo "== Script signoff Fase 2 =="
for s in run_thermal_signoff.sh run_pkg_bump.sh run_pkg_rdl.sh run_pkg_signoff.sh run_signoff_phase2.sh; do
  f="${ROOT}/learn/scripts/${s}"
  [[ -f "${f}" ]] && bash -n "${f}" && ok "${s}" || bad "script ${s}"
done
python3 -m py_compile "${ROOT}/learn/scripts/parse_signoff_artifacts.py" && ok "parse_signoff_artifacts.py" || bad "parse_signoff_artifacts.py"

echo "== Azioni Fase 2 in run.ts =="
for action in thermal_signoff pkg_bump pkg_rdl pkg_signoff signoff_phase2; do
  rg -q "\"${action}\"" "${ROOT}/studio/src/lib/run.ts" \
    && ok "action ${action}" || bad "run.ts senza ${action}"
done

echo "== Script signoff =="
for s in run_sta_signoff.sh run_drc_signoff.sh run_klayout_lvs.sh run_power_signoff.sh run_signoff_all.sh; do
  f="${ROOT}/learn/scripts/${s}"
  [[ -f "${f}" ]] && bash -n "${f}" && ok "${s}" || bad "script ${s}"
done
python3 -m py_compile "${ROOT}/learn/scripts/signoff_eval.py" && ok "signoff_eval.py" || bad "signoff_eval.py"
[[ -f "${ROOT}/learn/signoff/golden-gcd.json" ]] && ok "golden-gcd.json" || bad "golden-gcd.json"
[[ -f "${ROOT}/learn/reference/signoff-matrix.md" ]] && ok "signoff-matrix.md" || bad "signoff-matrix.md"
rg -q 'SIGNOFF_PILLARS' "${ROOT}/studio/src/lib/signoff.ts" && ok "signoff.ts registry" || bad "signoff.ts"

echo "== Azioni signoff in run.ts =="
for action in sta_signoff drc_signoff klayout_lvs power_signoff signoff_all; do
  rg -q "\"${action}\"" "${ROOT}/studio/src/lib/run.ts" \
    && ok "action ${action}" || bad "run.ts senza ${action}"
done

echo "== STAGE_DEPS signoff =="
python3 - <<PY || bad "STAGE_DEPS signoff incompleti"
import re
text = open("${ROOT}/studio/src/lib/jobs.ts").read()
for a in ["sta_signoff", "drc_signoff", "klayout_lvs", "power_signoff", "signoff_all"]:
    m = re.search(rf'{a}:\s*"(\w+)"', text)
    assert m and m.group(1) == "finish", f"{a} dep {m.group(1) if m else 'missing'}"
print("signoff deps ok")
PY
ok "STAGE_DEPS signoff"

echo "== Script catena power =="
for s in run_rtl_sim.sh run_activity_power.sh run_chip_pdn_ir.sh run_system_pdn.sh \
  run_power_chain.sh export_spice_lab.sh run_gridcheck.sh; do
  f="${ROOT}/learn/scripts/${s}"
  [[ -f "${f}" ]] && bash -n "${f}" && ok "${s}" || bad "script ${s}"
done
[[ -f "${ROOT}/learn/lib/power_vcd.sh" ]] && bash -n "${ROOT}/learn/lib/power_vcd.sh" && ok "power_vcd.sh" || bad "power_vcd.sh"

echo "== STAGE_DEPS power =="
python3 - <<PY || bad "STAGE_DEPS power incompleti"
import re, sys
text = open("${ROOT}/studio/src/lib/jobs.ts").read()
need = ["gridcheck", "system_pdn", "chip_pdn_ir", "power_chain", "activity_power", "export_spice_lab"]
for a in need:
    m = re.search(rf'{a}:\s*"(\w+)"', text)
    assert m, f"missing {a}"
    assert m.group(1) in ("floorplan", "finish"), f"{a} dep {m.group(1)}"
print("deps ok")
PY
ok "STAGE_DEPS power chain"

echo "== Artefatti flowlab (se presenti) =="
RES="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab"
if [[ -f "${RES}/6_final.odb" ]]; then
  for stamp in .gridcheck_pdn.ok .system_pdn.ok .chip_pdn_ir.ok; do
    [[ -f "${RES}/${stamp}" ]] && ok "stamp ${stamp}" || bad "manca ${stamp} (esegui signoff)"
  done
  [[ -f "${ROOT}/learn/sim/reports/power_chain_flowlab.log" ]] \
    && rg -q 'POWER_CHAIN_DONE' "${ROOT}/learn/sim/reports/power_chain_flowlab.log" \
    && ok "power_chain log complete" || bad "power_chain non completata"
  [[ -f "${ROOT}/learn/sim/spice/mesh_stats_flowlab.json" ]] && ok "mesh_stats export" || bad "mesh_stats assente"
  [[ -f "${ROOT}/learn/sim/reports/sta_signoff_flowlab.json" ]] && ok "sta_signoff report" || ok "skip sta_signoff (non eseguito)"
else
  ok "skip flowlab artifacts (finish non eseguito)"
fi

if curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:43217/ 2>/dev/null | rg -q 200; then
  echo "== Studio API (delegato a test_studio_api.sh) =="
  "${ROOT}/scripts/test_studio_api.sh"
else
  ok "skip Studio API (server non in ascolto su :43217)"
fi

if [[ "${FAIL}" -ne 0 ]]; then
  echo "ALL PHASES VALIDATION FAILED"
  exit 1
fi
echo "ALL PHASES VALIDATION PASSED"
exit 0
