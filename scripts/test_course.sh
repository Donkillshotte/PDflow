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
         golden-metrics.md \
         walkthrough-synth.tcl.md walkthrough-floorplan.tcl.md \
         walkthrough-global_place.tcl.md walkthrough-cts.tcl.md \
         walkthrough-route.tcl.md walkthrough-finish.tcl.md; do
  [[ -f "${ROOT}/learn/reference/${f}" ]] && ok "reference/${f}" || bad "manca reference/${f}"
done
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

if [[ "${FAIL}" -ne 0 ]]; then
  echo "SMOKE FAILED"
  exit 1
fi
echo "SMOKE PASSED"
exit 0
