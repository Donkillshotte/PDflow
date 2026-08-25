#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "03" "Floorplanning — die, core, PDN" "60–90 min"
  learn_orfs_env

  ui_section "Teoria"
  ui_note "Leggi: learn/lessons/03-floorplan/README.md e golden-metrics.md (riga Floorplan)."
  learn_atlas "win_floorplan.png, win_pdn.png, 03_pdn_labeled.png"
  ui_print_file "PDN Tcl" "${FLOW}/designs/nangate45/gcd/grid_strategy-M1-M4-M7.tcl" 25
  learn_make_hint floorplan
  ui_pause

  ui_section "Esercizio 3-A — Assicurati di avere synth"
  if [[ ! -f "$(learn_artifact 1_synth.odb)" ]]; then
    ui_note "Manca 1_synth.odb — eseguo synth..."
    learn_make synth
  fi

  ui_section "Esercizio 3-B — Esegui floorplan completo"
  learn_make clean_floorplan 2>/dev/null || true
  CORE_UTILIZATION=35 learn_make floorplan
  learn_validate_stage floorplan || return 1
  ui_print_file "Log floorplan init" "$(learn_log 2_1_floorplan.log)" 25
  ui_pause

  ui_section "Esercizio 3-C — Confronta utilization 25 vs 45"
  ui_note "Esercizio mentale: CORE_UTILIZATION cambia l'area del core."
  ui_code "# Floorplan al 25% (core più grande):
CORE_UTILIZATION=25 ./scripts/learn_physical_design.sh --auto --lesson 03
# Confronta logs/.../2_1_floorplan.log → Core area"
  ui_tip "Area core maggiore → placement più facile, die più grande."
  ui_pause

  ui_section "Esercizio 3-D — GUI floorplan"
  cat <<'EOF'
  Apri in sequenza:
  1. gui_2_1_floorplan.odb  → die + core + rows
  2. gui_2_4_floorplan_pdn.odb → power stripes (atlante 03_pdn_labeled.png)
  In Display Control: metal1/4/7, non il nome "Rows" (GUI-0013).
EOF
  if ui_confirm "Aprire gui_2_1_floorplan.odb?"; then learn_gui 2_1_floorplan.odb; fi
  ui_pause
  if ui_confirm "Aprire gui_2_4_floorplan_pdn.odb?"; then learn_gui 2_4_floorplan_pdn.odb; fi
  ui_pause

  ui_section "Esercizio 3-E — Leggi metriche floorplan"
  learn_grep_metric "$(learn_log 2_1_floorplan.log)" "Core area|Effective utilization|Design area" || true
  learn_golden
  ui_note "Riferimento: Core area 1712.5 um^2, effective util 0.367."
  ui_pause

  ui_section "Riepilogo"
  cat <<'EOF'
  • Floorplan definisce *dove* possono stare le celle (rows/sites)
  • PDN porta alimentazione a tutto il core
  • Utilization bassa = più spazio per timing repair successivo
  Prossima: 04-placement
EOF
}
