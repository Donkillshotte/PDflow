#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "04" "Placement — global, resize, detailed" "75–90 min"
  learn_orfs_env

  ui_section "Teoria"
  ui_note "Leggi: learn/lessons/04-placement/README.md e golden-metrics.md (riga Place)."
  learn_atlas "win_place_gp.png, win_place_dp.png, 04_place_gp_labeled.png"
  learn_make_hint place
  ui_pause

  ui_section "Esercizio 4-A — Prerequisiti"
  [[ -f "$(learn_artifact 2_floorplan.odb)" ]] || { learn_make floorplan; }
  ui_pause

  ui_section "Esercizio 4-B — Esegui placement"
  learn_make clean_place 2>/dev/null || true
  learn_make place
  learn_validate_stage place || return 1
  learn_show_tree
  ui_pause

  ui_section "Esercizio 4-C — Report global place e resizer"
  ui_print_file "Global place report" "$(learn_report 3_global_place.rpt)" 35
  ui_print_file "Resizer report" "$(learn_report 3_resizer.rpt)" 35
  learn_grep_metric "$(learn_report 3_resizer.rpt)" "worst slack|wns max|period_min|setup violation" || true
  learn_grep_metric "$(learn_log 3_4_place_resized.log)" "Design area" || true
  learn_golden
  ui_note "Riferimento: worst slack +0.01 ns, Design area 684 um^2 40%."
  ui_pause

  ui_section "Esercizio 4-D — Confronto GUI global vs detailed"
  cat <<'EOF'
  1. gui_3_3_place_gp.odb   → posizioni approssimative, possibile overlap visivo
  2. gui_3_5_place_dp.odb   → celle snap alle rows, legali
  Esperimenta: seleziona 2 celle vicine, misura distanza Manhattan
EOF
  if ui_confirm "Aprire gui_3_3_place_gp.odb?"; then learn_gui 3_3_place_gp.odb; fi
  ui_pause
  if ui_confirm "Aprire gui_3_5_place_dp.odb?"; then learn_gui 3_5_place_dp.odb; fi
  ui_pause

  ui_section "Esercizio 4-E — Timing pre-CTS"
  ui_print_file "Log resizer" "$(learn_log 3_4_place_resized.log)" 30
  ui_tip "Annotazioni istanze: hold*, rebuffer*, fanout* indicano celle inserite dal resizer."
  ui_pause

  ui_section "Riepilogo"
  cat <<'EOF'
  • Global place ottimizza wirelength + density
  • Resizer aggiunge buffer/upsize per timing (costo in area)
  • Detailed place legalizza senza rovinare troppo il timing
  Prossima: 05-cts
EOF
}
