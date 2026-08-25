#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "02" "Synthesis — RTL verso netlist" "45–75 min"
  learn_orfs_env

  ui_section "Teoria"
  ui_note "Leggi: learn/lessons/02-synthesis/README.md"
  ui_pause

  ui_section "Esercizio 2-A — Esegui synthesis"
  learn_make clean_synth 2>/dev/null || true
  learn_make synth
  learn_validate_stage synth || return 1
  learn_show_tree
  ui_pause

  ui_section "Esercizio 2-B — Leggi il netlist"
  ui_print_file "Netlist post-synth" "$(learn_artifact 1_2_yosys.v)" 35
  ui_print_file "Statistiche synth" "$(learn_report synth_stat.txt)" 30
  ui_tip "Cerca moduli *_reg, porte clk/rst, istanze di celle standard."
  ui_pause

  ui_section "Esercizio 2-C — Analizza log Yosys"
  ui_print_file "Log Yosys" "$(learn_log 1_2_yosys.log)" 40
  ui_tip "Cerca 'Printing statistics', 'Chip area', warning su latch/unmapped."
  ui_pause

  ui_section "Esercizio 2-D — GUI post-synth"
  ui_note "In OpenROAD GUI con 1_synth.odb:"
  cat <<'EOF'
  • Display Control → Instances → tutte visibili
  • Zoom out: le celle sono sovrapposte (nessun placement ancora)
  • Seleziona un'istanza → Inspector mostra master cell (es. DFF_X1)
  • Prova: highlight net del clock
EOF
  if ui_confirm "Aprire gui_1_synth.odb adesso? (richiede Desktop)"; then
    learn_gui 1_synth.odb
  fi
  ui_pause

  ui_section "Esercizio 2-E — OpenSTA standalone sul netlist"
  ui_note "OpenSTA può analizzare il netlist pre-layout (timing ideale):"
  ui_code "cd tools/OpenROAD-flow-scripts/flow
sta -no_init -exit -c 'read_liberty platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib; read_verilog results/nangate45/gcd/learn/1_2_yosys.v; link_design gcd; read_sdc designs/nangate45/gcd-tutorial/constraint.sdc; report_checks'"
  ui_pause

  ui_section "Riepilogo"
  cat <<'EOF'
  • Synth = RTL → gate-level + import ODB
  • 1_2_yosys.v è leggibile e ispezionabile
  • 1_synth.odb è il punto di partenza del floorplan
  Prossima: 03-floorplan
EOF
}
