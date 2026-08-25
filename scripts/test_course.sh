#!/usr/bin/env bash
# Smoke test del corso: struttura file, wrapper, toolchain, lezione 00 auto.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAIL=0

ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; FAIL=1; }

echo "== Struttura lezioni =="
for id in 00-intro 01-constraints 02-synthesis 03-floorplan 04-placement 05-cts 06-routing 07-finish; do
  for f in README.md LAB.md run.sh; do
    p="${ROOT}/learn/lessons/${id}/${f}"
    [[ -f "${p}" ]] && ok "${id}/${f}" || bad "manca ${p}"
  done
done

echo "== Reference =="
for f in glossary.md file-formats.md debug-playbook.md gui-openroad.md \
         walkthrough-synth.tcl.md walkthrough-floorplan.tcl.md \
         walkthrough-global_place.tcl.md walkthrough-cts.tcl.md \
         walkthrough-route.tcl.md walkthrough-finish.tcl.md; do
  [[ -f "${ROOT}/learn/reference/${f}" ]] && ok "reference/${f}" || bad "manca reference/${f}"
done

echo "== Workbook =="
for f in README.md notes-template.md quiz.md progetto-finale-template.md; do
  [[ -f "${ROOT}/learn/workbook/${f}" ]] && ok "workbook/${f}" || bad "manca workbook/${f}"
done

echo "== Design tutorial =="
for f in config.mk constraint.sdc constraint_relaxed.sdc constraint_tight.sdc; do
  [[ -f "${ROOT}/learn/designs/nangate45/gcd-tutorial/${f}" ]] && ok "design/${f}" || bad "manca ${f}"
done

echo "== Bash syntax =="
bash -n "${ROOT}/scripts/learn_physical_design.sh" && ok "wrapper syntax" || bad "syntax wrapper"
bash -n "${ROOT}/learn/lib/"*.sh && ok "lib syntax" || bad "syntax lib"
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
