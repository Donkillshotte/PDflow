#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "03" "Floorplanning — die, core, PDN" "60–90 min"
  learn_orfs_env

  ui_section "Theory"
  ui_note "Read: learn/lessons/03-floorplan/README.md and golden-metrics.md (Floorplan row)."
  learn_atlas "win_floorplan.png, win_pdn.png, 03_pdn_labeled.png"
  ui_print_file "PDN Tcl" "${FLOW}/designs/nangate45/gcd/grid_strategy-M1-M4-M7.tcl" 25
  learn_make_hint floorplan
  ui_pause

  ui_section "Exercise 3-A — Ensure synth exists"
  if [[ ! -f "$(learn_artifact 1_synth.odb)" ]]; then
    ui_note "Missing 1_synth.odb — running synth..."
    learn_make synth
  fi

  ui_section "Exercise 3-B — Run full floorplan"
  learn_make clean_floorplan 2>/dev/null || true
  CORE_UTILIZATION=35 learn_make floorplan
  learn_validate_stage floorplan || return 1
  ui_print_file "Floorplan init log" "$(learn_log 2_1_floorplan.log)" 25
  ui_pause

  ui_section "Exercise 3-C — Compare utilization 25 vs 45"
  ui_note "Mental exercise: CORE_UTILIZATION changes core area."
  ui_code "# Floorplan at 25% (larger core):
CORE_UTILIZATION=25 ./scripts/learn_physical_design.sh --auto --lesson 03
# Compare logs/.../2_1_floorplan.log → Core area"
  ui_tip "Larger core area → easier placement, larger die."
  ui_pause

  ui_section "Exercise 3-D — Floorplan GUI"
  cat <<'EOF'
  Open in sequence:
  1. gui_2_1_floorplan.odb  → die + core + rows
  2. gui_2_4_floorplan_pdn.odb → power stripes (atlas 03_pdn_labeled.png)
  In Display Control: metal1/4/7, not the name "Rows" (GUI-0013).
EOF
  if ui_confirm "Open gui_2_1_floorplan.odb?"; then learn_gui 2_1_floorplan.odb; fi
  ui_pause
  if ui_confirm "Open gui_2_4_floorplan_pdn.odb?"; then learn_gui 2_4_floorplan_pdn.odb; fi
  ui_pause

  ui_section "Exercise 3-E — Read floorplan metrics"
  learn_grep_metric "$(learn_log 2_1_floorplan.log)" "Core area|Effective utilization|Design area" || true
  learn_golden
  ui_note "Reference: Core area 1712.5 um^2, effective util 0.367."
  ui_pause

  ui_section "Summary"
  cat <<'EOF'
  • Floorplan defines *where* cells can sit (rows/sites)
  • PDN brings power to the entire core
  • Low utilization = more room for later timing repair
  Next: 04-placement
EOF
}
