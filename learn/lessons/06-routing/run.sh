#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "06" "Routing — global and detailed" "75–90 min"
  learn_orfs_env

  ui_section "Theory"
  ui_note "Read: learn/lessons/06-routing/README.md, walkthrough-route.tcl.md, golden-metrics.md (GRT/DRC)."
  learn_atlas "win_grt.png, win_route.png, 08_route_labeled.png, orfs_final_congestion.png"
  learn_make_hint route
  ui_pause

  ui_section "Exercise 6-A — CTS prerequisites"
  [[ -f "$(learn_artifact 4_cts.odb)" ]] || { ui_warn "Running CTS..."; learn_make cts || true; }
  ui_pause

  ui_section "Exercise 6-B — Run routing"
  learn_make clean_route 2>/dev/null || true
  learn_make route
  learn_validate_stage route || return 1
  learn_show_tree
  ui_pause

  ui_section "Exercise 6-C — Guides and DRC"
  ui_note "Route guide (excerpt):"
  head -30 "$(learn_artifact route.guide)" 2>/dev/null | sed 's/^/  /' || true
  ui_note "Guide lines: $(wc -l < "$(learn_artifact route.guide)" 2>/dev/null || echo n/a)"
  ui_print_file "DRC report" "$(learn_report 5_route_drc.rpt)" 20
  ui_print_file "Global route report" "$(learn_report 5_global_route.rpt)" 30
  learn_grep_metric "$(learn_report 5_global_route.rpt)" "worst slack|setup violation" || true
  learn_golden
  ui_note "Reference: DRC wc -l = 0, GRT WNS -0.05 ns / 43 viol."
  ui_pause

  ui_section "Exercise 6-D — Routing GUI"
  cat <<'EOF'
  GUI sequence (atlas §5.8–5.9):
  1. gui_5_1_grt.odb → routing guides (PNG win_grt.png)
  2. gui_5_2_route.odb → M2 red wire / M3 green wire
  Tcl: gui::set_display_controls "Layers/metal2" visible true
  Heatmap: orfs_final_congestion.png if View menu does not open
EOF
  if ui_confirm "Open gui_5_1_grt.odb?"; then learn_gui 5_1_grt.odb; fi
  ui_pause
  if ui_confirm "Open gui_5_2_route.odb?"; then learn_gui 5_2_route.odb; fi
  ui_pause

  ui_section "Exercise 6-E — KLayout guides (optional)"
  ui_code "cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk FLOW_VARIANT=learn klayout_guides"
  ui_tip "Shows routing guides overlaid on DEF — useful to understand GRT."
  ui_pause

  ui_section "Summary"
  cat <<'EOF'
  • GRT creates guides; DRT realizes wires respecting design rules
  • Empty DRC report = no geometric violations detected
  Next: 07-finish — GDS, SPEF, signoff timing
EOF
}
