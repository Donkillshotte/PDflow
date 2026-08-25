#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "07" "Finish — GDS, SPEF, signoff" "60–90 min"
  learn_orfs_env

  ui_section "Teoria"
  ui_note "Leggi: learn/lessons/07-finish/README.md"
  ui_pause

  ui_section "Esercizio 7-A — Prerequisiti route"
  [[ -f "$(learn_artifact 5_route.odb)" ]] || learn_make route
  ui_pause

  ui_section "Esercizio 7-B — Esegui finish completo"
  learn_make clean_finish 2>/dev/null || true
  learn_make finish
  learn_validate_stage finish || return 1
  learn_show_tree
  ui_pause

  ui_section "Esercizio 7-C — Report finale"
  ui_print_file "Finish report" "$(learn_report 6_finish.rpt)" 50
  learn_grep_metric "$(learn_report 6_finish.rpt)" "slack|WNS|TNS|power|area" || true
  ui_pause

  ui_section "Esercizio 7-D — Ispeziona deliverables"
  for f in 6_final.gds 6_final.def 6_final.v 6_final.spef 6_final.sdc; do
    learn_require_file "$(learn_artifact "${f}")" "${f}" || true
  done
  ui_tip "GDS in KLayout: klayout results/.../6_final.gds"
  ui_pause

  ui_section "Esercizio 7-E — GUI layout finale"
  cat <<'EOF'
  gui_final (o gui_6_final.odb):
  • Tutti i layer visibili
  • Timing → Worst Path
  • IR Drop heatmap (se PWR_NETS configurati)
  • Confronta slack con report 6_finish.rpt
EOF
  if ui_confirm "Aprire gui_final?"; then learn_gui final; fi
  ui_pause

  ui_section "Esercizio 7-F — Verifica GDS"
  if command -v klayout >/dev/null; then
    ui_note "Verifica struttura GDS con KLayout batch..."
    printf 'import pya\nl=pya.Layout();l.read(gds);print("cells",l.cells(),"layers",len(l.layer_indexes()))\n' > /tmp/learn_check_gds.py
    klayout -b -rd gds="$(learn_artifact 6_final.gds)" -r /tmp/learn_check_gds.py 2>/dev/null | sed 's/^/  /' || ui_warn "Verifica GDS non riuscita"
  fi
  ui_pause

  ui_section "Esercizio 7-G — Progetto finale (sfida)"
  cat <<'EOF'
  Sfida consigliata:
  1. Modifica constraint.sdc (clock ±30%)
  2. clean_all && percorso completo
  3. Confronta WNS, area, cell count in 6_finish.rpt
  4. Documenta in learn/notes/mio-esperimento.md cosa hai osservato
EOF
  ui_pause

  ui_section "Corso completato"
  ui_banner "Complimenti — hai percorso tutte le fasi RTL→GDS"
  cat <<'EOF'
  Ora sai:
  • Leggere e modificare SDC e config.mk
  • Eseguire ogni fase ORFS separatamente
  • Ispezionare .odb in GUI a ogni step
  • Interpretare report timing, area, DRC
  • Generare GDS di signoff

  Prossimi passi:
  • Prova sky130hd/gcd cambiando DESIGN_CONFIG
  • Studia flow/scripts/*.tcl modificando un parametro alla volta
  • Porta un tuo modulo Verilog nel flusso
EOF
}
