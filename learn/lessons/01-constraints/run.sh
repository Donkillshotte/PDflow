#!/usr/bin/env bash
lesson_main() {
  ui_lesson_header "01" "Constraints (SDC) e config.mk" "60–90 min"
  learn_orfs_env

  ui_section "Teoria — SDC e config"
  ui_note "Leggi: learn/lessons/01-constraints/README.md e golden-metrics.md (tabella maestra)."
  ui_print_file "SDC default" "${TUTORIAL_SRC}/constraint.sdc"
  ui_print_file "Config" "${TUTORIAL_SRC}/config.mk"
  learn_make_hint synth floorplan place
  ui_pause

  ui_section "Esercizio 1-A — Anatomia del clock"
  cat <<'EOF'
  Nel file constraint.sdc trovi:
  • clk_period 0.46  → frequenza target ≈ 2.17 GHz
  • clk_io_pct 0.2   → I/O delay = 20% del periodo
  • create_clock      → definisce il dominio temporale
  • set_input/output_delay → budget verso pad/pad logici
EOF
  ui_tip "Prova: ricalcola a mente I/O delay = 0.46 × 0.2 = 0.092 ns"
  ui_pause

  ui_section "Esercizio 1-B — Clock rilassato (2.0 ns)"
  ui_note "Backup dell'SDC corrente e switch alla variante rilassata."
  cp -a "${TUTORIAL_SRC}/constraint.sdc" "${TUTORIAL_SRC}/constraint.sdc.bak"
  cp -a "${TUTORIAL_SRC}/constraint_relaxed.sdc" "${TUTORIAL_SRC}/constraint.sdc"
  ui_ok "SDC aggiornato a constraint_relaxed.sdc (2.0 ns)"
  if ui_confirm "Eseguire synth + floorplan + place con clock rilassato?"; then
    learn_make clean_synth clean_floorplan clean_place 2>/dev/null || true
    learn_make synth floorplan place
    learn_validate_stage place
    learn_grep_metric "$(learn_report 3_resizer.rpt)" "worst slack|period_min" || true
    learn_golden
    ui_note "Con clock 2.0 ns attendi slack comodo e pochi buffer vs default 0.46 ns."
  fi
  ui_pause

  ui_section "Esercizio 1-C — Clock aggressivo (0.25 ns) — opzionale"
  ui_warn "Questo esercizio può fallire al CTS per overflow di area: è *didattico*."
  if ui_confirm "Provare constraint_tight.sdc (0.25 ns)?"; then
    cp -a "${TUTORIAL_SRC}/constraint_tight.sdc" "${TUTORIAL_SRC}/constraint.sdc"
    learn_make clean_synth clean_floorplan clean_place clean_cts 2>/dev/null || true
    learn_make synth floorplan place || true
    learn_make cts || ui_warn "CTS fallito — confronta log 4_1_cts.log con utilization >100%"
    ui_tip "Apri gui_4_1_error.odb se creato, oppure gui_3_place.odb per vedere densità pre-CTS"
  fi
  ui_pause

  ui_section "Esercizio 1-D — Ripristino SDC default"
  if [[ -f "${TUTORIAL_SRC}/constraint.sdc.bak" ]]; then
    cp -a "${TUTORIAL_SRC}/constraint.sdc.bak" "${TUTORIAL_SRC}/constraint.sdc"
    ui_ok "Ripristinato constraint.sdc originale (0.46 ns)"
  fi

  ui_section "Esercizio 1-E — Ispezione GUI"
  ui_note "Comandi GUI utili:"
  ui_code "./scripts/learn_physical_design.sh --lesson 04   # placement + GUI
# oppure manualmente:
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk FLOW_VARIANT=learn gui_3_place.odb"
  ui_tip "In GUI: Charts → Endpoint Slack; clicca un endpoint per vedere il path."
  ui_pause

  ui_section "Riepilogo"
  cat <<'EOF'
  • SDC = contratto temporale del design
  • config.mk = parametri fisici (utilization, PDN, variant)
  • Clock stretto + utilization alta → più buffer, più area, rischio legalizzazione
  Prossima: 02-synthesis — da Verilog a netlist + 1_synth.odb
EOF
}
