#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "05" "CTS — Clock Tree Synthesis" "60–90 min"
  learn_orfs_env

  ui_section "Theory"
  ui_note "Read: learn/lessons/05-cts/README.md, walkthrough-cts.tcl.md, golden-metrics.md (CTS rows)."
  learn_atlas "win_cts.png, orfs_cts_clock_tree.png"
  learn_make_hint cts
  ui_pause

  ui_section "Exercise 5-A — Placement prerequisites"
  [[ -f "$(learn_artifact 3_place.odb)" ]] || learn_make place
  ui_pause

  ui_section "Exercise 5-B — Run CTS"
  learn_make clean_cts 2>/dev/null || true
  if learn_make cts; then
    learn_validate_stage cts
  else
    ui_warn "CTS failed — debug exercise:"
    ui_print_file "CTS log" "$(learn_log 4_1_cts.log)" 40
    ui_tip "Search for DPL-0038 or RSZ-0062; often caused by aggressive utilization/timing."
    [[ -f "$(learn_artifact 4_1_error.odb)" ]] && ui_note "Open gui_4_1_error.odb to inspect state at failure."
  fi
  ui_pause

  ui_section "Exercise 5-C — CTS report"
  ui_print_file "CTS final report" "$(learn_report 4_cts_final.rpt)" 40
  learn_grep_metric "$(learn_log 4_1_cts.log)" "DPL-0006|Inserted|RSZ-0062" || true
  learn_grep_metric "$(learn_report 4_cts_final.rpt)" "worst slack|setup violation|setup skew" || true
  learn_golden
  ui_note "Reference: util 40.5%→48.3%, Inserted 45, WNS -0.04, possible RSZ-0062 (not DPL-0038)."
  ui_pause

  ui_section "Exercise 5-D — Clock Tree GUI"
  cat <<'EOF'
  With gui_4_1_cts.odb (or gui_4_cts.odb):
  • Display Control → layer metal; Tcl `select -name "clkbuf*"`
  • Clock tree: View → Clock Tree Viewer **or** PNG
    learn/reference/gui-shots/orfs_cts_clock_tree.png
  • Compare with gui_3_place.odb: how many more cells?
EOF
  if ui_confirm "Open gui_4_cts.odb?"; then learn_gui 4_cts.odb; fi
  ui_pause

  ui_section "Exercise 5-E — Interactive Tcl (optional)"
  ui_code "openroad -gui
# Then in console:
# read_db results/nangate45/gcd/learn/4_cts.odb
# report_clock_skew"
  ui_pause

  ui_section "Summary"
  cat <<'EOF'
  • CTS distributes clock minimizing skew
  • Adds buffers → consumes area → sensitive to floorplan
  Next: 06-routing
EOF
}
