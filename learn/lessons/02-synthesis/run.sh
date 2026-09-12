#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "02" "Synthesis — RTL to netlist" "45–75 min"
  learn_orfs_env

  ui_section "Theory"
  ui_note "Read: learn/lessons/02-synthesis/README.md, walkthrough-synth.tcl.md, live-analysis.md."
  learn_atlas "win_synth.png"
  learn_make_hint synth
  ui_pause

  ui_section "Exercise 2-A — Run synthesis"
  learn_make clean_synth 2>/dev/null || true
  learn_make synth
  learn_validate_stage synth || return 1
  learn_show_tree
  ui_pause

  ui_section "Exercise 2-B — Read the netlist"
  ui_print_file "Post-synth netlist" "$(learn_artifact 1_2_yosys.v)" 35
  ui_print_file "Synth statistics" "$(learn_report synth_stat.txt)" 30
  learn_live_analysis
  ui_note "Read cell counts and area from the current synth_stat.txt; no stored synthesis result is a target."
  ui_pause

  ui_section "Exercise 2-C — Analyze Yosys log"
  ui_print_file "Yosys log" "$(learn_log 1_2_yosys.log)" 40
  ui_tip "Search for 'Printing statistics', 'Chip area', warnings on latch/unmapped."
  ui_pause

  ui_section "Exercise 2-D — Post-synth GUI"
  ui_note "In OpenROAD GUI with 1_synth.odb:"
  cat <<'EOF'
  • Display Control → Instances → all visible
  • Zoom out: cells overlap (no placement yet)
  • Select an instance → Inspector shows master cell (e.g. DFF_X1)
  • Try: highlight clock net
EOF
  if ui_confirm "Open gui_1_synth.odb now? (requires Desktop)"; then
    learn_gui 1_synth.odb
  fi
  ui_pause

  ui_section "Exercise 2-E — OpenSTA standalone on netlist"
  ui_note "OpenSTA can analyze the pre-layout netlist (ideal timing):"
  ui_code "cd tools/OpenROAD-flow-scripts/flow
sta -no_init -exit -c 'read_liberty platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib; read_verilog results/nangate45/gcd/learn/1_2_yosys.v; link_design gcd; read_sdc designs/nangate45/gcd-tutorial/constraint.sdc; report_checks'"
  ui_pause

  ui_section "Summary"
  cat <<'EOF'
  • Synth = RTL → gate-level + ODB import
  • 1_2_yosys.v is readable and inspectable
  • 1_synth.odb is the floorplan starting point
  Next: 03-floorplan
EOF
}
