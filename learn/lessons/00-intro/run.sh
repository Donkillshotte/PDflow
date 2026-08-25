#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "00" "Introduzione al flusso RTL→GDS" "45–60 min"

  ui_section "Teoria"
  ui_note "Leggi learn/lessons/00-intro/README.md per la mappa completa."
  ui_pause "Premi INVIO dopo aver letto il README (o subito se già letto)..."

  ui_section "Esercizio 0-A — Verifica toolchain"
  learn_check_prerequisites || return 1
  ui_pause

  ui_section "Esercizio 0-B — Esplora il design GCD"
  learn_orfs_env
  ui_print_file "RTL sorgente" "${FLOW}/designs/src/gcd/gcd.v" 25
  ui_print_file "Config tutorial" "${TUTORIAL_SRC}/config.mk" 30
  ui_print_file "Constraints" "${TUTORIAL_SRC}/constraint.sdc" 20
  ui_tip "Il RTL descrive *cosa* fa il chip; l'SDC dice *quanto deve essere veloce*."
  ui_pause

  ui_section "Esercizio 0-C — Mappa degli script Tcl"
  ui_note "Script Tcl ORFS per ogni macro-fase:"
  for f in synth.tcl floorplan.tcl global_place.tcl cts.tcl global_route.tcl detail_route.tcl final_report.tcl; do
    [[ -f "${FLOW}/scripts/${f}" ]] && echo "  • ${FLOW}/scripts/${f}"
  done
  ui_tip "Apri uno script Tcl e segui i comandi OpenROAD uno per uno — è il modo migliore per imparare."
  ui_pause

  ui_section "Esercizio 0-D — Smoke test rapido (solo synth)"
  ui_note "Eseguiamo la sola sintesi per verificare yosys + OpenROAD senza attendere il flusso completo."
  if ui_confirm "Eseguire 'make synth' ora? (~30 secondi)"; then
    learn_make synth
    learn_validate_stage synth
    learn_show_tree
  fi

  ui_section "Esercizio 0-E — Apri la GUI (opzionale)"
  ui_note "Comando: ./scripts/learn_physical_design.sh --lesson 02  (include GUI synth)"
  ui_note "Oppure: cd flow && make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk FLOW_VARIANT=learn gui_1_synth.odb"
  ui_tip "Apri Desktop su cursor.com/agents, poi lancia il comando gui_*."
  ui_pause

  ui_section "Riepilogo lezione 00"
  cat <<'EOF'
  Hai imparato:
  • La sequenza RTL → GDS e dove vivono i file in ORFS
  • La differenza tra modalità file (Makefile/log/report) e GUI (.odb)
  • Che il corso usa FLOW_VARIANT=learn per non toccare i run "base"
  Prossima lezione: 01-constraints — impari SDC e config.mk
EOF
}
