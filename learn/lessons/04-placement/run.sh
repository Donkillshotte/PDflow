#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "04" "Placement — global, resize, detailed" "75–90 min"
  learn_orfs_env

  ui_section "Theory"
  ui_note "Read: learn/lessons/04-placement/README.md and golden-metrics.md (Place row)."
  learn_atlas "win_place_gp.png, win_place_dp.png, 04_place_gp_labeled.png"
  learn_make_hint place
  ui_pause

  ui_section "Exercise 4-A — Prerequisites"
  [[ -f "$(learn_artifact 2_floorplan.odb)" ]] || { learn_make floorplan; }
  ui_pause

  ui_section "Exercise 4-B — Run placement"
  learn_make clean_place 2>/dev/null || true
  learn_make place
  learn_validate_stage place || return 1
  learn_show_tree
  ui_pause

  ui_section "Exercise 4-C — Global place and resizer reports"
  ui_print_file "Global place report" "$(learn_report 3_global_place.rpt)" 35
  ui_print_file "Resizer report" "$(learn_report 3_resizer.rpt)" 35
  learn_grep_metric "$(learn_report 3_resizer.rpt)" "worst slack|wns max|period_min|setup violation" || true
  learn_grep_metric "$(learn_log 3_4_place_resized.log)" "Design area" || true
  learn_golden
  ui_note "Reference: worst slack +0.01 ns, Design area 684 um^2 40%."
  ui_pause

  ui_section "Exercise 4-D — GUI global vs detailed comparison"
  cat <<'EOF'
  1. gui_3_3_place_gp.odb   → approximate positions, possible visual overlap
  2. gui_3_5_place_dp.odb   → cells snapped to rows, legal
  Experiment: select 2 nearby cells, measure Manhattan distance
EOF
  if ui_confirm "Open gui_3_3_place_gp.odb?"; then learn_gui 3_3_place_gp.odb; fi
  ui_pause
  if ui_confirm "Open gui_3_5_place_dp.odb?"; then learn_gui 3_5_place_dp.odb; fi
  ui_pause

  ui_section "Exercise 4-E — Pre-CTS timing"
  ui_print_file "Resizer log" "$(learn_log 3_4_place_resized.log)" 30
  ui_tip "Instance annotations: hold*, rebuffer*, fanout* indicate cells inserted by the resizer."
  ui_pause

  ui_section "Summary"
  cat <<'EOF'
  • Global place optimizes wirelength + density
  • Resizer adds buffer/upsize for timing (area cost)
  • Detailed place legalizes without ruining timing too much
  Next: 05-cts
EOF
}
