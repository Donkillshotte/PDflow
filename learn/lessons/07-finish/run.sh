#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "07" "Finish — GDS, SPEF, signoff" "60–90 min"
  learn_orfs_env

  ui_section "Theory"
  ui_note "Read: learn/lessons/07-finish/README.md, walkthrough-finish.tcl.md, golden-metrics.md (Finish)."
  learn_atlas "win_final.png, orfs_final_worst_path.png, orfs_final_ir_drop.png"
  learn_make_hint finish
  ui_pause

  ui_section "Exercise 7-A — Route prerequisites"
  [[ -f "$(learn_artifact 5_route.odb)" ]] || learn_make route
  ui_pause

  ui_section "Exercise 7-B — Run full finish"
  learn_make clean_finish 2>/dev/null || true
  learn_make finish
  learn_validate_stage finish || return 1
  learn_show_tree
  ui_pause

  ui_section "Exercise 7-C — Final report"
  ui_print_file "Finish report" "$(learn_report 6_finish.rpt)" 50
  learn_grep_metric "$(learn_report 6_finish.rpt)" "wns max|tns max|period_min|setup violation|setup skew" || true
  learn_golden
  ui_note "Reference: WNS -0.04, TNS -0.60, period_min 0.50 ns (~2.01 GHz) vs SDC 0.46 ns."
  ui_warn "Green make finish does not mean timing closed at 2.17 GHz."
  ui_pause

  ui_section "Exercise 7-D — Inspect deliverables"
  for f in 6_final.gds 6_final.def 6_final.v 6_final.spef 6_final.sdc; do
    learn_require_file "$(learn_artifact "${f}")" "${f}" || true
  done
  ui_tip "GDS in KLayout: klayout results/.../6_final.gds"
  ui_pause

  ui_section "Exercise 7-E — Final layout GUI"
  cat <<'EOF'
  gui_final (or gui_6_final.odb):
  • All layers visible
  • Timing → Worst Path
  • IR Drop heatmap (if PWR_NETS configured)
  • Compare slack with report 6_finish.rpt
EOF
  if ui_confirm "Open gui_final?"; then learn_gui final; fi
  ui_pause

  ui_section "Exercise 7-F — GDS verification"
  if command -v klayout >/dev/null; then
    ui_note "Verify GDS structure with KLayout batch..."
    printf 'import pya\nl=pya.Layout();l.read(gds);print("cells",l.cells(),"layers",len(l.layer_indexes()))\n' > /tmp/learn_check_gds.py
    klayout -b -rd gds="$(learn_artifact 6_final.gds)" -r /tmp/learn_check_gds.py 2>/dev/null | sed 's/^/  /' || ui_warn "GDS verification failed"
  fi
  ui_pause

  ui_section "Exercise 7-G — Final project (challenge)"
  cat <<'EOF'
  Recommended challenge:
  1. Modify constraint.sdc (clock ±30%)
  2. clean_all && full path
  3. Compare WNS, area, cell count in 6_finish.rpt
  4. Document in learn/workbook/mio-progetto-finale.md (not notes/)
EOF
  ui_pause

  ui_section "Course complete"
  ui_banner "Congratulations — you completed all RTL→GDS stages"
  cat <<'EOF'
  You now know how to:
  • Read and modify SDC and config.mk
  • Run each ORFS stage separately
  • Inspect .odb in GUI at every step
  • Interpret timing, area, DRC reports
  • Generate signoff GDS

  Next steps:
  • Try sky130hd/gcd by changing DESIGN_CONFIG
  • Study flow/scripts/*.tcl modifying one parameter at a time
  • Bring your own Verilog module into the flow
EOF
}
