#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "05" "CTS — Clock Tree Synthesis" "60–90 min"
  learn_orfs_env

  ui_section "Teoria"
  ui_note "Leggi: learn/lessons/05-cts/README.md, walkthrough-cts.tcl.md, golden-metrics.md (righe CTS)."
  learn_atlas "win_cts.png, orfs_cts_clock_tree.png"
  learn_make_hint cts
  ui_pause

  ui_section "Esercizio 5-A — Prerequisiti placement"
  [[ -f "$(learn_artifact 3_place.odb)" ]] || learn_make place
  ui_pause

  ui_section "Esercizio 5-B — Esegui CTS"
  learn_make clean_cts 2>/dev/null || true
  if learn_make cts; then
    learn_validate_stage cts
  else
    ui_warn "CTS fallito — esercizio di debug:"
    ui_print_file "Log CTS" "$(learn_log 4_1_cts.log)" 40
    ui_tip "Cerca DPL-0038 o RSZ-0062; spesso causati da utilization/timing aggressivo."
    [[ -f "$(learn_artifact 4_1_error.odb)" ]] && ui_note "Apri gui_4_1_error.odb per ispezionare lo stato al fallimento."
  fi
  ui_pause

  ui_section "Esercizio 5-C — Report CTS"
  ui_print_file "CTS final report" "$(learn_report 4_cts_final.rpt)" 40
  learn_grep_metric "$(learn_log 4_1_cts.log)" "DPL-0006|Inserted|RSZ-0062" || true
  learn_grep_metric "$(learn_report 4_cts_final.rpt)" "worst slack|setup violation|setup skew" || true
  learn_golden
  ui_note "Riferimento: util 40.5%→48.3%, Inserted 45, WNS -0.04, possibile RSZ-0062 (non è DPL-0038)."
  ui_pause

  ui_section "Esercizio 5-D — GUI Clock Tree"
  cat <<'EOF'
  Con gui_4_1_cts.odb (o gui_4_cts.odb):
  • Display Control → layer metal; Tcl `select -name "clkbuf*"`
  • Clock tree: View → Clock Tree Viewer **oppure** PNG
    learn/reference/gui-shots/orfs_cts_clock_tree.png
  • Confronta con gui_3_place.odb: quante celle in più?
EOF
  if ui_confirm "Aprire gui_4_cts.odb?"; then learn_gui 4_cts.odb; fi
  ui_pause

  ui_section "Esercizio 5-E — Tcl interattivo (opzionale)"
  ui_code "openroad -gui
# Poi in console:
# read_db results/nangate45/gcd/learn/4_cts.odb
# report_clock_skew"
  ui_pause

  ui_section "Riepilogo"
  cat <<'EOF'
  • CTS distribuisce il clock minimizzando skew
  • Aggiunge buffer → consuma area → sensibile al floorplan
  Prossima: 06-routing
EOF
}
