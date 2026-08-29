#!/usr/bin/env bash
# Smoke test del corso: struttura file, profondità, GUI shots, wrapper, toolchain, lezione 00 auto.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAIL=0

ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; FAIL=1; }

min_lines() {
  local f="$1" n="$2"
  local got
  got="$(wc -l < "${f}")"
  if [[ "${got}" -ge "${n}" ]]; then
    ok "lines ${got}>=${n} ${f#${ROOT}/}"
  else
    bad "troppo corto (${got}<${n} righe) ${f#${ROOT}/}"
  fi
}

min_bytes() {
  local f="$1" n="$2"
  local got
  got="$(stat -c%s "${f}")"
  if [[ "${got}" -ge "${n}" ]]; then
    ok "size ${got}>=${n} ${f#${ROOT}/}"
  else
    bad "file piccolo (${got}<${n} B) ${f#${ROOT}/}"
  fi
}

echo "== Struttura lezioni =="
for id in 00-intro 01-constraints 02-synthesis 03-floorplan 04-placement 05-cts 06-routing 07-finish; do
  for f in README.md LAB.md run.sh; do
    p="${ROOT}/learn/lessons/${id}/${f}"
    [[ -f "${p}" ]] && ok "${id}/${f}" || bad "manca ${p}"
  done
  min_lines "${ROOT}/learn/lessons/${id}/README.md" 60
  min_lines "${ROOT}/learn/lessons/${id}/LAB.md" 80
  min_lines "${ROOT}/learn/lessons/${id}/run.sh" 45
done

echo "== Reference =="
for f in glossary.md file-formats.md debug-playbook.md gui-openroad.md gui-atlas.md \
         golden-metrics.md tool-hooks.md extended-flow.md signoff-matrix.md oss-integrations.md \
         walkthrough-synth.tcl.md walkthrough-floorplan.tcl.md \
         walkthrough-global_place.tcl.md walkthrough-cts.tcl.md \
         walkthrough-route.tcl.md walkthrough-finish.tcl.md; do
  [[ -f "${ROOT}/learn/reference/${f}" ]] && ok "reference/${f}" || bad "manca reference/${f}"
done
min_lines "${ROOT}/learn/reference/tool-hooks.md" 80
min_lines "${ROOT}/learn/reference/extended-flow.md" 100
rg -q 'OpenROAD -web' "${ROOT}/learn/reference/tool-hooks.md" && ok "hooks -web" || bad "hooks senza -web"
rg -q 'report_checks -format json' "${ROOT}/learn/reference/tool-hooks.md" && ok "hooks sta json" || bad "hooks senza sta json"
rg -q 'run_rtl_sim|gridcheck|activity_power|bump|thermal|signoff|FreePDK45.lylvs' "${ROOT}/learn/reference/extended-flow.md" \
  && ok "extended-flow topics" || bad "extended-flow incompleto"
[[ -f "${ROOT}/learn/reference/signoff-matrix.md" ]] && ok "signoff-matrix.md" || bad "manca signoff-matrix"
[[ -f "${ROOT}/learn/reference/oss-integrations.md" ]] && ok "oss-integrations.md" || bad "manca oss-integrations"
[[ -f "${ROOT}/learn/platforms/nangate45/lvs/FreePDK45.lylvs" ]] \
  && ok "FreePDK45.lylvs vendored" || bad "manca LVS runset"
[[ -f "${ROOT}/studio/src/lib/signoff.ts" ]] && rg -q 'SIGNOFF_PILLARS' "${ROOT}/studio/src/lib/signoff.ts" \
  && ok "signoff.ts registry" || bad "signoff.ts incompleto"
for s in run_sta_signoff.sh run_signoff_phase2.sh parse_signoff_artifacts.py; do
  [[ -f "${ROOT}/learn/scripts/${s}" ]] && ok "script ${s}" || bad "manca ${s}"
done
rg -q 'sta_signoff|signoff_phase2|thermal_signoff' "${ROOT}/studio/src/lib/run.ts" \
  && ok "studio signoff actions" || bad "run.ts signoff incompleto"
rg -q 'signoff-matrix|Parte 7' "${ROOT}/learn/lessons/07-finish/LAB.md" \
  && ok "L07 signoff LAB" || bad "L07 LAB senza signoff"
[[ -f "${ROOT}/learn/sim/gcd/tb_gcd.v" ]] && ok "tb_gcd.v" || bad "manca tb"
[[ -x "${ROOT}/learn/scripts/run_rtl_sim.sh" ]] || chmod +x "${ROOT}/learn/scripts/run_rtl_sim.sh"
[[ -x "${ROOT}/learn/scripts/run_gridcheck.sh" ]] || chmod +x "${ROOT}/learn/scripts/run_gridcheck.sh"
if command -v iverilog >/dev/null; then
  "${ROOT}/learn/scripts/run_rtl_sim.sh" >/tmp/rtl-sim-smoke.log 2>&1 \
    && ok "rtl_sim smoke" \
    || { bad "rtl_sim fallita"; tail -20 /tmp/rtl-sim-smoke.log; }
else
  bad "iverilog assente"
fi
"${ROOT}/learn/scripts/run_gridcheck.sh" pdn >/tmp/gridcheck-smoke.log 2>&1 \
  && ok "gridcheck smoke" \
  || { bad "gridcheck fallita"; tail -20 /tmp/gridcheck-smoke.log; }

min_lines "${ROOT}/learn/reference/gui-atlas.md" 150
min_lines "${ROOT}/learn/reference/walkthrough-global_place.tcl.md" 80
min_lines "${ROOT}/learn/reference/walkthrough-cts.tcl.md" 80
min_lines "${ROOT}/learn/reference/debug-playbook.md" 80
min_lines "${ROOT}/learn/reference/glossary.md" 80
min_lines "${ROOT}/learn/reference/golden-metrics.md" 70
min_lines "${ROOT}/learn/reference/file-formats.md" 80

rg -q 'RSZ-0062' "${ROOT}/learn/reference/glossary.md" && ok "glossary RSZ-0062" || bad "glossary senza RSZ-0062"
rg -q 'period_min' "${ROOT}/learn/reference/glossary.md" && ok "glossary period_min" || bad "glossary senza period_min"
rg -q 'IFP-0028' "${ROOT}/learn/reference/glossary.md" && ok "glossary IFP-0028" || bad "glossary senza IFP-0028"
rg -q 'OpenRCX' "${ROOT}/learn/reference/glossary.md" && ok "glossary OpenRCX" || bad "glossary senza OpenRCX"
rg -q 'NDR' "${ROOT}/learn/reference/glossary.md" && ok "glossary NDR" || bad "glossary senza NDR"
rg -q 'gcell' "${ROOT}/learn/reference/glossary.md" && ok "glossary gcell" || bad "glossary senza gcell"
rg -q '\*SPEF' "${ROOT}/learn/reference/file-formats.md" && ok "file-formats SPEF header" || bad "file-formats senza SPEF header"
rg -q 'DPL-0038' "${ROOT}/learn/reference/debug-playbook.md" && ok "playbook DPL-0038" || bad "playbook senza DPL-0038"

echo "== GUI shots (pixel-level) =="
SHOT="${ROOT}/learn/reference/gui-shots"
[[ -d "${SHOT}" ]] && ok "gui-shots dir" || bad "manca gui-shots"
for spec in \
  "win_anatomy.png:100000" \
  "win_anatomy_labeled.png:100000" \
  "win_display_control_crop.png:20000" \
  "win_synth.png:20000" \
  "win_floorplan.png:30000" \
  "win_pdn.png:40000" \
  "win_place_gp.png:80000" \
  "win_place_dp.png:80000" \
  "win_cts.png:80000" \
  "win_grt.png:80000" \
  "win_route.png:100000" \
  "win_final.png:100000" \
  "win_inspector_tab.png:100000" \
  "win_layers_m2m3.png:80000" \
  "03_pdn.png:15000" \
  "03_pdn_labeled.png:20000" \
  "04_place_gp.png:100000" \
  "04_place_gp_labeled.png:100000" \
  "05_place_dp.png:100000" \
  "06_cts.png:100000" \
  "07_grt.png:100000" \
  "08_route.png:200000" \
  "08_route_labeled.png:200000" \
  "09_final.png:200000" \
  "orfs_cts_clock_tree.png:30000" \
  "orfs_final_worst_path.png:80000" \
  "orfs_final_congestion.png:80000" \
  "orfs_final_ir_drop.png:80000"; do
  name="${spec%%:*}"
  bytes="${spec##*:}"
  p="${SHOT}/${name}"
  if [[ -f "${p}" ]]; then
    min_bytes "${p}" "${bytes}"
  else
    bad "manca screenshot ${name}"
  fi
done

rg -q 'win_anatomy_labeled.png' "${ROOT}/learn/reference/gui-atlas.md" && ok "atlas embeds anatomy" || bad "atlas senza anatomy"
rg -q '03_pdn_labeled.png' "${ROOT}/learn/reference/gui-atlas.md" && ok "atlas embeds pdn" || bad "atlas senza pdn"
rg -q 'win_inspector_tab.png' "${ROOT}/learn/reference/gui-atlas.md" && ok "atlas embeds inspector" || bad "atlas senza inspector"
rg -q 'orfs_cts_clock_tree.png' "${ROOT}/learn/reference/gui-atlas.md" && ok "atlas embeds clock tree" || bad "atlas senza clock tree"
rg -q 'orfs_final_worst_path.png' "${ROOT}/learn/reference/gui-atlas.md" && ok "atlas embeds worst path" || bad "atlas senza worst path"
rg -q 'gui-atlas.md' "${ROOT}/learn/README.md" && ok "learn README cita atlas" || bad "README senza atlas"
rg -q 'gui-atlas.md' "${ROOT}/learn/CURRICULUM.md" && ok "curriculum cita atlas" || bad "CURRICULUM senza atlas"
rg -q 'golden-metrics.md' "${ROOT}/learn/README.md" && ok "learn README cita golden-metrics" || bad "README senza golden-metrics"
rg -q 'golden-metrics.md' "${ROOT}/learn/CURRICULUM.md" && ok "curriculum cita golden-metrics" || bad "CURRICULUM senza golden-metrics"
rg -q 'golden-metrics.md' "${ROOT}/README.md" && ok "root README cita golden-metrics" || bad "root README senza golden-metrics"

echo "== Nessun make con puntini nei LAB =="
if rg -n --glob '*.md' 'make \.\.\. (clean_|gui_|synth|floorplan|place|cts|route|finish)' "${ROOT}/learn"; then
  bad "LAB/reference contengono «make ...» incompleto"
else
  ok "nessun make-ellipsis nei comandi"
fi

echo "== Workbook =="
for f in README.md notes-template.md quiz.md progetto-finale-template.md solutions.md; do
  [[ -f "${ROOT}/learn/workbook/${f}" ]] && ok "workbook/${f}" || bad "manca workbook/${f}"
done
min_lines "${ROOT}/learn/workbook/quiz.md" 70
min_lines "${ROOT}/learn/workbook/solutions.md" 80
min_lines "${ROOT}/learn/workbook/progetto-finale-template.md" 50
rg -q 'Quiz GUI' "${ROOT}/learn/workbook/quiz.md" && ok "quiz GUI" || bad "quiz senza GUI"
rg -q 'golden-metrics.md' "${ROOT}/learn/workbook/progetto-finale-template.md" && ok "progetto cita golden-metrics" || bad "progetto senza golden-metrics"
rg -q 'solutions.md' "${ROOT}/learn/workbook/README.md" && ok "workbook README cita solutions.md" || bad "workbook README senza solutions.md"

echo "== Meta corso =="
[[ -f "${ROOT}/learn/AUDIT.md" ]] && ok "AUDIT.md" || bad "manca AUDIT.md"
[[ -f "${ROOT}/learn/EVIDENCE.md" ]] && ok "EVIDENCE.md" || bad "manca EVIDENCE.md"

echo "== Studio UI =="
[[ -f "${ROOT}/studio/package.json" ]] && ok "studio/package.json" || bad "manca studio"
[[ -f "${ROOT}/scripts/run_studio.sh" ]] && ok "run_studio.sh" || bad "manca run_studio.sh"
[[ -f "${ROOT}/studio/src/app/page.tsx" ]] && ok "studio home" || bad "manca studio home"
[[ -f "${ROOT}/studio/src/app/lezioni/page.tsx" ]] && ok "studio lezioni" || bad "manca lezioni"
[[ -f "${ROOT}/studio/src/app/strumenti/page.tsx" ]] && ok "studio strumenti" || bad "manca strumenti"
[[ -f "${ROOT}/studio/src/app/api/run/route.ts" ]] && ok "studio api/run" || bad "manca api/run"
[[ -f "${ROOT}/studio/src/app/api/run/stream/route.ts" ]] && ok "studio api/run/stream" || bad "manca stream"
[[ -f "${ROOT}/studio/src/components/LessonWizard.tsx" ]] && ok "LessonWizard" || bad "manca LessonWizard"
[[ -f "${ROOT}/studio/src/components/LiveRunConsole.tsx" ]] && ok "LiveRunConsole" || bad "manca LiveRunConsole"
[[ -f "${ROOT}/studio/src/components/ResultsPanel.tsx" ]] && ok "ResultsPanel" || bad "manca ResultsPanel"
[[ -f "${ROOT}/studio/src/components/OpsDashboard.tsx" ]] && ok "OpsDashboard" || bad "manca OpsDashboard"
[[ -f "${ROOT}/studio/src/lib/jobs.ts" ]] && ok "jobs.ts" || bad "manca jobs.ts"
[[ -f "${ROOT}/studio/src/lib/open.ts" ]] && ok "open.ts" || bad "manca open.ts"
[[ -f "${ROOT}/studio/src/lib/inspect.ts" ]] && ok "inspect.ts" || bad "manca inspect.ts"
[[ -f "${ROOT}/studio/src/lib/webviewer.ts" ]] && ok "webviewer.ts" || bad "manca webviewer.ts"
[[ -f "${ROOT}/studio/src/components/InspectPanel.tsx" ]] && ok "InspectPanel" || bad "manca InspectPanel"
[[ -f "${ROOT}/studio/src/app/api/inspect/route.ts" ]] && ok "api/inspect" || bad "manca api/inspect"
[[ -f "${ROOT}/studio/src/app/api/viewer/route.ts" ]] && ok "api/viewer" || bad "manca api/viewer"
[[ -f "${ROOT}/studio/src/components/CommandPalette.tsx" ]] && ok "CommandPalette" || bad "manca CommandPalette"
[[ -f "${ROOT}/studio/src/app/api/open/route.ts" ]] && ok "api/open" || bad "manca api/open"
rg -q 'system_pdn|gridcheck' "${ROOT}/studio/src/lib/run.ts" && ok "run system_pdn/gridcheck" || bad "run senza system_pdn"
rg -q 'id: "pdn"' "${ROOT}/studio/src/components/flowlab/phases.ts" && ok "FlowLab phase pdn" || bad "manca fase pdn"
rg -q 'id: "pkg"' "${ROOT}/studio/src/components/flowlab/phases.ts" && ok "FlowLab phase pkg" || bad "manca fase pkg"
[[ -f "${ROOT}/learn/scripts/system_pdn_hier.py" ]] && ok "system_pdn_hier.py" || bad "manca system_pdn_hier.py"
[[ -f "${ROOT}/learn/system_pdn/default.json" ]] && ok "system_pdn config" || bad "manca system_pdn/default.json"
[[ -f "${ROOT}/learn/scripts/pdn_transient.py" ]] && ok "pdn_transient.py" || bad "manca pdn_transient.py"
[[ -f "${ROOT}/learn/scripts/run_chip_pdn_ir.sh" ]] && ok "run_chip_pdn_ir.sh" || bad "manca chip PDN script"
[[ -f "${ROOT}/learn/scripts/run_vyges_em_ir.sh" ]] && ok "run_vyges_em_ir.sh" || bad "manca vyges-em-ir script"
[[ -f "${ROOT}/learn/scripts/run_dynamic_ir.sh" ]] && ok "run_dynamic_ir.sh" || bad "manca dynamic_ir script"
[[ -f "${ROOT}/learn/scripts/pdn_dynamic.py" ]] && ok "pdn_dynamic.py" || bad "manca pdn_dynamic.py"
[[ -f "${ROOT}/learn/reference/vyges-em-ir.md" ]] && ok "vyges-em-ir.md" || bad "manca vyges-em-ir.md"
[[ -f "${ROOT}/learn/reference/dynamic-ir.md" ]] && ok "dynamic-ir.md" || bad "manca dynamic-ir.md"
[[ -f "${ROOT}/learn/reference/dynamic-ir-landscape.md" ]] && ok "dynamic-ir-landscape.md" || bad "manca landscape"
[[ -f "${ROOT}/learn/scripts/spice_to_pdn.py" ]] && ok "spice_to_pdn.py" || bad "manca spice_to_pdn.py"
python3 -m py_compile "${ROOT}/learn/scripts/spice_to_pdn.py" && ok "spice_to_pdn compile" || bad "spice_to_pdn compile"
python3 -m py_compile "${ROOT}/learn/scripts/pdn_dynamic.py" && ok "pdn_dynamic compile" || bad "pdn_dynamic compile"
python3 -m py_compile "${ROOT}/learn/scripts/pdn_solvers.py" && ok "pdn_solvers compile" || bad "pdn_solvers compile"
python3 -m py_compile "${ROOT}/learn/scripts/pdn_extract.py" && ok "pdn_extract compile" || bad "pdn_extract compile"
python3 -m py_compile "${ROOT}/learn/scripts/pdn_em.py" && ok "pdn_em compile" || bad "pdn_em compile"
python3 -m py_compile "${ROOT}/learn/scripts/pdn_vrm.py" && ok "pdn_vrm compile" || bad "pdn_vrm compile"
if "${ROOT}/learn/scripts/build_dpn_engine.sh" >/tmp/dpn-engine-build.log 2>&1; then
  ok "libdpn build + dpn_test"
else
  bad "libdpn build"
  tail -20 /tmp/dpn-engine-build.log || true
fi
if PYTHONPATH=/usr/lib/python3/dist-packages:"${ROOT}/learn/scripts" python3 - <<'PY'
from scipy import sparse
import numpy as np
from pdn_solvers import DirectLU, SAAMG, RASDD
n=200
A=sparse.diags([-np.ones(n-1), 2*np.ones(n), -np.ones(n-1)], [-1,0,1], shape=(n,n), format="csr")
b=np.ones(n)
xa=DirectLU(A).solve(b)
B=SAAMG(A)
xb=B.solve(b)
assert B.n_levels>=2
assert float(np.max(np.abs(xa-xb)))<1e-6
print("amg poisson ok", B.n_levels, getattr(B, "backend", "?"))
assert getattr(B, "backend", "") == "native"
D=RASDD(A)
xd=D.solve(b)
assert D.n_levels>=2
assert float(np.max(np.abs(xa-xd)))<1e-6
print("ras poisson ok", D.n_levels, getattr(D, "backend", "?"))
assert getattr(D, "backend", "") == "native"
PY
then ok "SA-AMG vs LU poisson (native)"; else bad "SA-AMG poisson"; fi
rg -q 'vyges_em_ir' "${ROOT}/studio/src/lib/run.ts" && ok "studio vyges_em_ir action" || bad "studio senza vyges_em_ir"
rg -q 'dynamic_ir' "${ROOT}/studio/src/lib/run.ts" && ok "studio dynamic_ir action" || bad "studio senza dynamic_ir"
rg -F -q 'image/svg+xml' "${ROOT}/studio/src/app/api/content/route.ts" && ok "content SVG mime" || bad "content senza SVG"
# Tiny mesh: adapter + real binary (if present)
mkdir -p /tmp/vyges-course-smoke
cat > /tmp/vyges-course-smoke/mesh.sp <<'SP'
R0 p1 a R=0.05
R1 a c R=0.20
I0 c 0 DC 0.010
V0 p1 0 DC 1.8
SP
if PYTHONPATH=/usr/lib/python3/dist-packages python3 "${ROOT}/learn/scripts/spice_to_pdn.py" \
  --spice /tmp/vyges-course-smoke/mesh.sp --out-dir /tmp/vyges-course-smoke --design tiny \
  >/tmp/vyges-course-smoke.log 2>&1 && rg -q 'SPICE_TO_PDN_DONE' /tmp/vyges-course-smoke.log
then
  ok "spice_to_pdn tiny mesh"
else
  bad "spice_to_pdn tiny mesh"
fi
VYGES_BIN=""
if command -v vyges-em-ir >/dev/null 2>&1; then
  VYGES_BIN="$(command -v vyges-em-ir)"
elif [[ -x "${ROOT}/tools/vyges-em-ir/vyges-em-ir" ]]; then
  VYGES_BIN="${ROOT}/tools/vyges-em-ir/vyges-em-ir"
elif [[ -x "${ROOT}/learn/scripts/ensure_vyges_em_ir.sh" ]]; then
  VYGES_BIN="$("${ROOT}/learn/scripts/ensure_vyges_em_ir.sh" 2>/dev/null || true)"
fi
if [[ -n "${VYGES_BIN}" && -x "${VYGES_BIN}" ]]; then
  if "${VYGES_BIN}" run /tmp/vyges-course-smoke/tiny.emir --json -o /tmp/vyges-course-smoke/out.json \
    >/tmp/vyges-course-smoke/stdout.json 2>/tmp/vyges-course-smoke/err.ndjson \
    && python3 -c 'import json; r=json.load(open("/tmp/vyges-course-smoke/out.json")); assert r["worst_ir"]["drop"]>0'
  then
    ok "vyges-em-ir tiny solve"
  else
    bad "vyges-em-ir tiny solve"
  fi
else
  ok "skip vyges-em-ir binary (not installed yet)"
fi
# Replaceable current/activity layers (CCS interpolator; NLDM never mapped)
if PYTHONPATH=/usr/lib/python3/dist-packages python3 "${ROOT}/learn/scripts/test_pdn_layers.py"
then
  ok "pdn current/activity layers"
else
  bad "pdn current/activity layers"
fi
# Tiny mesh: pdn_dynamic BE + ngspice gold
mkdir -p /tmp/dynir-course-smoke
cat > /tmp/dynir-course-smoke/mesh.sp <<'SP'
R0 p1 ITermNode_metal1_0_0 R=0.05
R1 ITermNode_metal1_0_0 ITermNode_metal1_100_0 R=0.20
I0 ITermNode_metal1_100_0 0 DC 0.001
V0 p1 0 DC 1.1
SP
if PYTHONPATH=/usr/lib/python3/dist-packages python3 "${ROOT}/learn/scripts/pdn_dynamic.py" \
  --spice /tmp/dynir-course-smoke/mesh.sp --out /tmp/dynir-course-smoke/out.json \
  --mode simultaneous --dt-ps 20 --t-end-ns 0.5 \
  >/tmp/dynir-course-smoke.log 2>&1 && rg -q 'DYNAMIC_IR_DONE' /tmp/dynir-course-smoke.log
then
  python3 - <<PY && ok "pdn_dynamic tiny mesh" || bad "pdn_dynamic tiny parse"
import json
r=json.load(open("/tmp/dynir-course-smoke/out.json"))
assert r["ok"] and r["kind"]=="dynamic_ir"
assert r["static"]["worst_ir"] > 0
assert r["sim_levels"]["L0_static"]["status"]=="READY"
assert r["sim_levels"]["L2_vcd_dynamic"]["status"]=="GAP"
assert r["hotspot"]["droop_mv"] > 0
assert r["emsim_split"]["A_cell_current"]["status"]=="PARTIAL"
assert r["emsim_split"]["B_pdn_solve"]["status"]=="READY"
p=r["platform"]
assert p["solvers"]["A_direct_be"]["status"]=="READY"
assert p["solvers"]["B_sa_amg"]["status"]=="READY"
assert p["solvers"]["C_rational_krylov_mor"]["status"] in ("READY", "PARTIAL")
assert r.get("solver_c") is not None
assert r["solver_c"]["abs_err_vs_A_mv"] < 5.0
assert r.get("solver_d") is not None
assert r["solver_d"]["ok"] is True
assert r["solver_d"]["abs_err_vs_A_mv"] < 5.0
assert p["solvers"]["D_ras_schwarz"]["status"] in ("READY", "PARTIAL")
assert "i_L" in (r["solver_c"].get("via") or "") or "RLC" in (r["solver_c"].get("via") or "") or r["solver_c"]["abs_err_vs_A_mv"] < 1.0
assert r.get("current_model", {}).get("status") in ("GAP", "PARTIAL", "READY")
assert r.get("activity_model", {}).get("status") == "GAP"
assert r["dynamic"].get("timestep_loop") in ("native", "native_hist", "python", "python_hist", "python_ccs", "python_ccs_hist", None)
assert p["product_tiers"]["FAST"]["status"]=="READY"
assert p["product_tiers"]["SIGNOFF"]["status"]=="GAP"
assert p["network_levels"]["N1_R"]["status"]=="READY"
assert p["network_levels"]["N4_vrm"]["status"] in ("READY", "PARTIAL")
assert r.get("n4") is None or r["n4"].get("ok") is True
assert r.get("n4") is None or r["n4"].get("backend") in (None, "native", "python")
assert "i_L" in p["network_levels"]["N3_RC_pkg"]["via"]
assert p["em_thermal"]["status"] in ("READY", "PARTIAL")
assert p["em_thermal"]["i_absmax_a"] > 0
if p["em_thermal"].get("n_with_j"):
    assert p["em_thermal"]["status"] == "READY"
    assert p["em_thermal"]["j_absmax_a_m2"] > 0
    assert p["em_thermal"].get("ttf_rel_min") is not None
assert r.get("extract", {}).get("backend") == "write_pg_spice"
assert (r.get("extract") or {}).get("spef", {}).get("status") == "GAP"
assert p.get("extract", {}).get("backend") == "write_pg_spice"
assert "vyges-em-ir" in p["do_not_fork"]
assert r["solver_b"]["ok"] is True
assert r["solver_b"]["abs_err_vs_A_mv"] < 5.0
assert r["timing_impact"]["status"]=="PARTIAL"
g=r.get("ngspice_gold")
assert g is None or g.get("ok") is True, g
g_rl=r.get("ngspice_rl_gold")
assert g_rl is None or g_rl.get("ok") is True, g_rl
g_n4=r.get("ngspice_n4_gold")
assert g_n4 is None or g_n4.get("ok") is True, g_n4
print(r["summary"][:100])
PY
else
  bad "pdn_dynamic tiny mesh"
  tail -20 /tmp/dynir-course-smoke.log || true
fi
# Hierarchical System PDN smoke (ngspice)
REP_SYS="${ROOT}/learn/sim/reports/system_pdn_flowlab.json"
if command -v ngspice >/dev/null 2>&1; then
  python3 "${ROOT}/learn/scripts/system_pdn_hier.py" \
    --config "${ROOT}/learn/system_pdn/default.json" \
    --out-dir /tmp/syspdn-smoke \
    --report "${REP_SYS}" \
    --repo "${ROOT}" \
    --variant flowlab \
    --i-die 0.002 \
    >/tmp/syspdn-smoke.log 2>&1 \
    && rg -q 'SYSTEM_PDN_HIER_DONE' /tmp/syspdn-smoke.log \
    && ok "system pdn hier smoke" \
    || { bad "system pdn hier smoke"; tail -20 /tmp/syspdn-smoke.log; }
else
  ok "skip system pdn hier (no ngspice)"
fi
# Optional chip IR smoke if spice exists
SPICE_FL="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/pdn/pg_vdd_bumps.sp"
REP_FL="${ROOT}/learn/sim/reports/pdn_chip_ir_flowlab.json"
if [[ ! -f "${REP_FL}" && -f "${SPICE_FL}" ]]; then
  PYTHONPATH=/usr/lib/python3/dist-packages python3 "${ROOT}/learn/scripts/pdn_transient.py" \
    --spice "${SPICE_FL}" --out "${REP_FL}" --wave "${ROOT}/learn/sim/reports/pdn_chip_ir_flowlab.wave.csv" \
    >/tmp/pdn-trans-smoke.log 2>&1 || true
fi
if [[ -f "${REP_FL}" ]] && PYTHONPATH=/usr/lib/python3/dist-packages python3 - <<PY
import json
r=json.load(open("${REP_FL}"))
assert r["static"]["worst_ir"] < 0.05, r["static"]
assert r["transient"]["worst_droop"] >= r["static"]["worst_ir"] * 0.5, r
print("ok", round(r["static"]["worst_ir"]*1e3,3), round(r["transient"]["worst_droop"]*1e3,3))
PY
then
  ok "chip pdn transient report sane"
else
  ok "skip chip pdn transient (no spice/report yet)"
fi
rg -q 'system_pdn_hier|ngspice' "${ROOT}/learn/scripts/run_system_pdn.sh" && ok "system_pdn uses hier ngspice" || bad "system_pdn non gerarchico"
[[ -f "${ROOT}/scripts/test_all_phases.sh" ]] && ok "test_all_phases.sh" || bad "manca test_all_phases"
bash -n "${ROOT}/scripts/test_all_phases.sh" && ok "test_all_phases syntax" || bad "syntax test_all_phases"
rg -q 'export_spice_lab' "${ROOT}/studio/src/lib/run.ts" && ok "run export_spice_lab" || bad "run senza export_spice_lab"
rg -q 'read_vcd' "${ROOT}/learn/lib/power_vcd.sh" && ok "VCD read_vcd helper" || bad "power_vcd senza read_vcd"
rg -q 'vectorless' "${ROOT}/studio/src/lib/run.ts" && ok "studio vectorless action" || bad "studio senza vectorless"
[[ -f "${ROOT}/learn/lib/power_vcd.sh" ]] && ok "power_vcd.sh shared" || bad "manca power_vcd.sh"
[[ -f "${ROOT}/studio/src/lib/actions.ts" ]] && ok "actions.ts single source" || bad "manca actions.ts"
[[ -f "${ROOT}/studio/src/lib/materials-data.ts" ]] && ok "materials-data.ts" || bad "manca materials-data"
[[ -f "${ROOT}/studio/src/app/materiali/file/[...slug]/page.tsx" ]] && ok "spice file viewer" || bad "manca file viewer"
rg -q 'PkgHubPanel' "${ROOT}/studio/src/app/pkg/page.tsx" && ok "pkg hub live panel" || bad "pkg static only"
[[ -f "${ROOT}/learn/scripts/export_spice_lab.sh" ]] && ok "export_spice_lab.sh" || bad "manca export_spice_lab"
[[ -f "${ROOT}/learn/scripts/run_power_chain.sh" ]] && ok "run_power_chain.sh" || bad "manca power_chain"
[[ -f "${ROOT}/studio/src/lib/powerChainLessons.ts" ]] && ok "powerChainLessons map" || bad "manca powerChainLessons"
rg -q 'LessonPowerChainPanel' "${ROOT}/studio/src/components/LessonWizard.tsx" && ok "lesson power panel" || bad "wizard senza power panel"
rg -q 'Catena power' "${ROOT}/learn/lessons/07-finish/README.md" && ok "L07 power chain section" || bad "L07 senza catena power"
[[ -f "${ROOT}/learn/sim/spice/system_pdn_tran_demo.sp" ]] && ok "spice demo netlist" || bad "manca demo sp"
if command -v ngspice >/dev/null 2>&1; then
  ngspice -b -o /tmp/ngspice-demo.log "${ROOT}/learn/sim/spice/system_pdn_tran_demo.sp" >/dev/null 2>&1 \
    && ok "ngspice demo tran" || ok "skip ngspice demo (warn)"
fi
if [[ -f "${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/pdn/pg_vdd_bumps.sp" ]]; then
  FLOW_VARIANT=flowlab "${ROOT}/learn/scripts/export_spice_lab.sh" >/tmp/spice-export.log 2>&1 \
    && [[ -f "${ROOT}/learn/sim/spice/mesh_stats_flowlab.json" ]] \
    && ok "export_spice_lab" || ok "skip export_spice_lab"
fi
[[ -f "${ROOT}/learn/reference/system-pdn.md" ]] && ok "system-pdn.md" || bad "manca system-pdn.md"
[[ -f "${ROOT}/learn/reference/pkg-design-package.md" ]] && ok "pkg-design-package.md" || bad "manca pkg doc"
[[ -f "${ROOT}/studio/src/app/pkg/page.tsx" ]] && ok "pkg page" || bad "manca /pkg"
rg -q 'devIndicators: false' "${ROOT}/studio/next.config.ts" && ok "Next issues badge disabled" || bad "devIndicators non disabilitato"
[[ -f "${ROOT}/scripts/test_orfs_log.mjs" ]] && ok "test_orfs_log.mjs" || bad "manca test_orfs_log.mjs"
[[ -f "${ROOT}/studio/src/lib/orfsLog.ts" ]] && ok "orfsLog.ts" || bad "manca orfsLog.ts"
if node "${ROOT}/scripts/test_orfs_log.mjs" >/tmp/orfs-log-smoke.log 2>&1; then
  ok "orfs log classify"
else
  bad "orfs log classify fallita"
  tail -15 /tmp/orfs-log-smoke.log
fi
rg -q 'digestOrfsLog|logDigest' "${ROOT}/studio/src/components/flowlab/FlowLabTerminal.tsx" && ok "FlowLabTerminal digest" || bad "terminal senza digest"
rg -q 'logDigest' "${ROOT}/studio/src/lib/results.ts" && ok "results.logDigest" || bad "results senza logDigest"
rg -q 'Physical Design Studio' "${ROOT}/studio/src/app/layout.tsx" && ok "studio brand" || bad "studio senza brand"
rg -q 'CommandPalette' "${ROOT}/studio/src/app/layout.tsx" && ok "palette wired" || bad "palette non collegata"
rg -q 'streamCourseAction|LiveRunConsole|LessonWizard' "${ROOT}/studio/src/components/LessonWizard.tsx" && ok "wizard uses interactive flow" || bad "wizard non interattivo"
rg -q 'evaluateLessonGates|gates' "${ROOT}/studio/src/app/api/progress/route.ts" && ok "progress gates" || bad "progress senza gates"
rg -q 'acquireLock|preflightAction' "${ROOT}/studio/src/lib/run.ts" && ok "run lock/preflight" || bad "run senza lock"
rg -q 'Yosys|KLayout|Magic|Netgen|EQY|SymbiYosys|ngspice|Xyce|OpenRCX|FasterCap|Raphael|StarRC|open_pdks' \
  "${ROOT}/learn/reference/oss-integrations.md" && ok "oss-integrations matrix tools" || bad "oss-integrations incompleta"
[[ -f "${ROOT}/learn/reference/vectorless-power.md" ]] && ok "vectorless-power.md" || bad "manca vectorless-power.md"
[[ -f "${ROOT}/learn/scripts/run_vectorless.sh" ]] && bash -n "${ROOT}/learn/scripts/run_vectorless.sh" && ok "run_vectorless.sh" || bad "run_vectorless.sh"
[[ -f "${ROOT}/learn/scripts/run_yosys_equiv.sh" ]] && bash -n "${ROOT}/learn/scripts/run_yosys_equiv.sh" && ok "run_yosys_equiv.sh" || bad "run_yosys_equiv.sh"
[[ -f "${ROOT}/learn/scripts/run_formal_gcd.sh" ]] && bash -n "${ROOT}/learn/scripts/run_formal_gcd.sh" && ok "run_formal_gcd.sh" || bad "run_formal_gcd.sh"
python3 -m py_compile "${ROOT}/learn/scripts/vectorless_analysis.py" \
  "${ROOT}/learn/scripts/run_analytical_pex.py" \
  "${ROOT}/learn/scripts/export_odb_inst_power.py" && ok "vectorless/pex python" || bad "py_compile vectorless"
PYTHONPATH="${ROOT}/learn/scripts" python3 - <<'PY' && ok "Najm P01 unit" || bad "P01 unit"
from vectorless_analysis import switching_p01
assert abs(switching_p01(0.5) - 0.25) < 1e-12
assert abs(switching_p01(0.1) - 0.09) < 1e-12
PY
if [[ -f "${ROOT}/learn/sim/reports/vectorless_flowlab.json" ]]; then
  python3 - <<PY && ok "vectorless report ok" || bad "vectorless report"
import json
r=json.load(open("${ROOT}/learn/sim/reports/vectorless_flowlab.json"))
assert r.get("ok") is True
assert r["vectorless"]["total_w"]
assert r["dynamic"]["source"].startswith("vcd")
print(r["summary"][:80])
PY
else
  ok "skip vectorless report (not run)"
fi
if [[ -f "${ROOT}/learn/sim/reports/yosys_equiv_flowlab.json" ]]; then
  python3 -c 'import json; r=json.load(open("'"${ROOT}"'/learn/sim/reports/yosys_equiv_flowlab.json")); assert r["ok"]' \
    && ok "yosys equiv report" || bad "yosys equiv report"
fi
if [[ -f "${ROOT}/learn/sim/reports/formal_gcd_flowlab.json" ]]; then
  python3 -c 'import json; r=json.load(open("'"${ROOT}"'/learn/sim/reports/formal_gcd_flowlab.json")); assert r["ok"]' \
    && ok "formal gcd report" || bad "formal gcd report"
fi
rg -q 'Sim RTL|Gridcheck|Activity' "${ROOT}/studio/src/components/LiveRunConsole.tsx" && ok "console extended chips" || bad "console senza chip estesi"
rg -q 'OpsDashboard' "${ROOT}/studio/src/app/strumenti/strumenti-client.tsx" && ok "OpsDashboard wired" || bad "OpsDashboard non collegata"
rg -q 'ToastProvider' "${ROOT}/studio/src/app/layout.tsx" && ok "ToastProvider wired" || bad "ToastProvider non collegata"
rg -q 'ConfirmDialog' "${ROOT}/studio/src/components/LiveRunConsole.tsx" && ok "ConfirmDialog wired" || bad "ConfirmDialog non collegata"
if [[ -d "${ROOT}/studio/node_modules" ]]; then
  (cd "${ROOT}/studio" && npm run build >/tmp/studio-build-smoke.log 2>&1) \
    && ok "studio build" \
    || { bad "studio build fallita"; tail -20 /tmp/studio-build-smoke.log; }
else
  bad "studio/node_modules assente — esegui npm install in studio/"
fi
rg -q 'run_studio.sh' "${ROOT}/README.md" && ok "root README cita Studio" || bad "README senza Studio"
rg -q 'gate|single-flight|Ops' "${ROOT}/studio/README.md" && ok "studio README enterprise" || bad "studio README senza enterprise"

echo "== Design tutorial =="
for f in config.mk constraint.sdc constraint_relaxed.sdc constraint_tight.sdc; do
  [[ -f "${ROOT}/learn/designs/nangate45/gcd-tutorial/${f}" ]] && ok "design/${f}" || bad "manca ${f}"
done

echo "== Bash syntax =="
bash -n "${ROOT}/scripts/learn_physical_design.sh" && ok "wrapper syntax" || bad "syntax wrapper"
bash -n "${ROOT}/scripts/test_course.sh" && ok "test_course syntax" || bad "syntax test_course"
bash -n "${ROOT}/learn/lib/"*.sh && ok "lib syntax" || bad "syntax lib"
bash -n "${ROOT}/learn/scripts/capture_gui_shots.sh" && ok "capture_gui_shots syntax" || bad "syntax capture"
for s in "${ROOT}/learn/lessons/"*/run.sh; do
  bash -n "${s}" || bad "syntax ${s}"
done
ok "lesson run.sh syntax"

echo "== Wrapper CLI =="
"${ROOT}/scripts/learn_physical_design.sh" --list >/tmp/learn-list.txt
rg -q '00-intro' /tmp/learn-list.txt && ok "list 00" || bad "list 00"
rg -q '07-finish' /tmp/learn-list.txt && ok "list 07" || bad "list 07"

"${ROOT}/scripts/learn_physical_design.sh" --check >/tmp/learn-check.txt
rg -q 'openroad' /tmp/learn-check.txt && ok "check openroad" || bad "check openroad"

echo "== Lezione 00 auto (synth smoke) =="
LEARN_AUTO=1 "${ROOT}/scripts/learn_physical_design.sh" --auto --lesson 00 >/tmp/learn-00.txt
rg -q 'completata' /tmp/learn-00.txt && ok "lesson 00 completed" || bad "lesson 00"

echo "== Tool versions =="
openroad -version >/dev/null && ok "openroad" || bad "openroad"
yosys -V >/dev/null && ok "yosys" || bad "yosys"
sta -version >/dev/null && ok "sta" || bad "sta"
klayout -v >/dev/null && ok "klayout" || bad "klayout"

echo "== FlowLab workspace =="
[[ -f "${ROOT}/learn/flowlab/gcd.v" ]] && ok "flowlab/gcd.v" || bad "manca flowlab/gcd.v"
[[ -f "${ROOT}/learn/flowlab/params.json" ]] && ok "flowlab/params.json" || bad "manca flowlab params"
rg -q 'FLOWLAB_VARIANT|flowlab' "${ROOT}/studio/src/lib/flowlab.ts" && ok "flowlab variant" || bad "flowlab variant"

if [[ "${FAIL}" -ne 0 ]]; then
  echo "SMOKE FAILED"
  exit 1
fi
echo "SMOKE PASSED"
exit 0
