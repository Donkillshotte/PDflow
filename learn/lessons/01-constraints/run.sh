#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "01" "Constraints (SDC) and config.mk" "60–90 min"
  learn_orfs_env

  ui_section "Theory — SDC and config"
  ui_note "Read: learn/lessons/01-constraints/README.md and golden-metrics.md (master table)."
  ui_print_file "Default SDC" "${TUTORIAL_SRC}/constraint.sdc"
  ui_print_file "Config" "${TUTORIAL_SRC}/config.mk"
  learn_make_hint synth floorplan place
  ui_pause

  ui_section "Exercise 1-A — Clock anatomy"
  cat <<'EOF'
  In constraint.sdc you find:
  • clk_period 0.46  → target frequency ≈ 2.17 GHz
  • clk_io_pct 0.2   → I/O delay = 20% of period
  • create_clock      → defines the timing domain
  • set_input/output_delay → budget toward pad/logical I/O
EOF
  ui_tip "Try: mentally recalculate I/O delay = 0.46 × 0.2 = 0.092 ns"
  ui_pause

  ui_section "Exercise 1-B — Relaxed clock (2.0 ns)"
  ui_note "Backup current SDC and switch to the relaxed variant."
  cp -a "${TUTORIAL_SRC}/constraint.sdc" "${TUTORIAL_SRC}/constraint.sdc.bak"
  cp -a "${TUTORIAL_SRC}/constraint_relaxed.sdc" "${TUTORIAL_SRC}/constraint.sdc"
  ui_ok "SDC updated to constraint_relaxed.sdc (2.0 ns)"
  if ui_confirm "Run synth + floorplan + place with relaxed clock?"; then
    learn_make clean_synth clean_floorplan clean_place 2>/dev/null || true
    learn_make synth floorplan place
    learn_validate_stage place
    learn_grep_metric "$(learn_report 3_resizer.rpt)" "worst slack|period_min" || true
    learn_golden
    ui_note "With a 2.0 ns clock expect comfortable slack and fewer buffers vs default 0.46 ns."
  fi
  ui_pause

  ui_section "Exercise 1-C — Aggressive clock (0.25 ns) — optional"
  ui_warn "This exercise may fail at CTS due to area overflow: it is *educational*."
  if ui_confirm "Try constraint_tight.sdc (0.25 ns)?"; then
    cp -a "${TUTORIAL_SRC}/constraint_tight.sdc" "${TUTORIAL_SRC}/constraint.sdc"
    learn_make clean_synth clean_floorplan clean_place clean_cts 2>/dev/null || true
    learn_make synth floorplan place || true
    learn_make cts || ui_warn "CTS failed — compare log 4_1_cts.log with utilization >100%"
    ui_tip "Open gui_4_1_error.odb if created, or gui_3_place.odb to see pre-CTS density"
  fi
  ui_pause

  ui_section "Exercise 1-D — Restore default SDC"
  if [[ -f "${TUTORIAL_SRC}/constraint.sdc.bak" ]]; then
    cp -a "${TUTORIAL_SRC}/constraint.sdc.bak" "${TUTORIAL_SRC}/constraint.sdc"
    ui_ok "Restored original constraint.sdc (0.46 ns)"
  fi

  ui_section "Exercise 1-E — GUI inspection"
  ui_note "Useful GUI commands:"
  ui_code "./scripts/learn_physical_design.sh --lesson 04   # placement + GUI
# or manually:
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk FLOW_VARIANT=learn gui_3_place.odb"
  ui_tip "In GUI: Charts → Endpoint Slack; click an endpoint to see the path."
  ui_pause

  ui_section "Summary"
  cat <<'EOF'
  • SDC = timing contract of the design
  • config.mk = physical parameters (utilization, PDN, variant)
  • Tight clock + high utilization → more buffers, more area, legalization risk
  Next: 02-synthesis — from Verilog to netlist + 1_synth.odb
EOF
}
