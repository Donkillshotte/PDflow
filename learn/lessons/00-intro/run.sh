#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "00" "Introduction to the RTL→GDS flow" "45–60 min"

  ui_section "Theory"
  ui_note "Read learn/lessons/00-intro/README.md, glossary.md and golden-metrics.md (what a 'reference run' is)."
  learn_atlas "win_anatomy_labeled.png"
  ui_pause "Press ENTER after reading the README (or immediately if already read)..."

  ui_section "Exercise 0-A — Verify toolchain"
  learn_check_prerequisites || return 1
  ui_pause

  ui_section "Exercise 0-B — Explore the GCD design"
  learn_orfs_env
  ui_print_file "RTL source" "${FLOW}/designs/src/gcd/gcd.v" 25
  ui_print_file "Tutorial config" "${TUTORIAL_SRC}/config.mk" 30
  ui_print_file "Constraints" "${TUTORIAL_SRC}/constraint.sdc" 20
  learn_make_hint synth
  ui_tip "RTL describes *what* the chip does; SDC says *how fast* it must run."
  ui_pause

  ui_section "Exercise 0-C — Tcl script map"
  ui_note "ORFS Tcl scripts per macro-stage:"
  for f in synth.tcl floorplan.tcl global_place.tcl cts.tcl global_route.tcl detail_route.tcl final_report.tcl; do
    [[ -f "${FLOW}/scripts/${f}" ]] && echo "  • ${FLOW}/scripts/${f}"
  done
  ui_tip "Open one Tcl script and follow OpenROAD commands one by one — that is the best way to learn."
  ui_pause

  ui_section "Exercise 0-D — Quick smoke test (synth only)"
  ui_note "We run synthesis only to verify yosys + OpenROAD without waiting for the full flow."
  if ui_confirm "Run 'make synth' now? (~30 seconds)"; then
    learn_make synth
    learn_validate_stage synth
    learn_show_tree
  fi

  ui_section "Exercise 0-E — Open the GUI (optional)"
  ui_note "Command: ./scripts/learn_physical_design.sh --lesson 02  (includes synth GUI)"
  ui_note "Or: cd flow && make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk FLOW_VARIANT=learn gui_1_synth.odb"
  ui_tip "Open Desktop on cursor.com/agents, then run the gui_* command."
  ui_pause

  ui_section "Lesson 00 summary"
  cat <<'EOF'
  You learned:
  • The RTL → GDS sequence and where files live in ORFS
  • The difference between file mode (Makefile/log/report) and GUI (.odb)
  • That the course uses FLOW_VARIANT=learn so it does not touch "base" runs
  Next lesson: 01-constraints — SDC and config.mk
EOF
}
