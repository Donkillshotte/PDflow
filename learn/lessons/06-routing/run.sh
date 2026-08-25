#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "06" "Routing — global e detailed" "75–90 min"
  learn_orfs_env

  ui_section "Teoria"
  ui_note "Leggi: learn/lessons/06-routing/README.md"
  ui_pause

  ui_section "Esercizio 6-A — Prerequisiti CTS"
  [[ -f "$(learn_artifact 4_cts.odb)" ]] || { ui_warn "Eseguo CTS..."; learn_make cts || true; }
  ui_pause

  ui_section "Esercizio 6-B — Esegui routing"
  learn_make clean_route 2>/dev/null || true
  learn_make route
  learn_validate_stage route || return 1
  learn_show_tree
  ui_pause

  ui_section "Esercizio 6-C — Guide e DRC"
  ui_note "Route guide (estratto):"
  head -30 "$(learn_artifact route.guide)" 2>/dev/null | sed 's/^/  /' || true
  ui_print_file "DRC report" "$(learn_report 5_route_drc.rpt)" 20
  ui_print_file "Global route report" "$(learn_report 5_global_route.rpt)" 30
  ui_pause

  ui_section "Esercizio 6-D — GUI routing"
  cat <<'EOF'
  Sequenza GUI:
  1. gui_5_1_grt.odb → routing guides (non wire finali)
  2. gui_5_2_route.odb → wire reali su tutti i layer
  Attiva/disattiva metal1..metal10 nel Display Control
  Heatmap: Routing Congestion (View menu)
EOF
  if ui_confirm "Aprire gui_5_1_grt.odb?"; then learn_gui 5_1_grt.odb; fi
  ui_pause
  if ui_confirm "Aprire gui_5_2_route.odb?"; then learn_gui 5_2_route.odb; fi
  ui_pause

  ui_section "Esercizio 6-E — KLayout guides (opzionale)"
  ui_code "cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk FLOW_VARIANT=learn klayout_guides"
  ui_tip "Mostra le guide di routing sovrapposte al DEF — utile per capire GRT."
  ui_pause

  ui_section "Riepilogo"
  cat <<'EOF'
  • GRT crea guide; DRT realizza wire rispettando design rules
  • DRC report vuoto = nessuna violazione geometrica rilevata
  Prossima: 07-finish — GDS, SPEF, signoff timing
EOF
}
