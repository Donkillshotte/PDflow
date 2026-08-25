#!/usr/bin/env bash
# Validazioni per checkpoint del corso.

learn_require_file() {
  local path="$1" desc="$2"
  if [[ -f "${path}" ]]; then
    ui_ok "${desc}: $(basename "${path}") ($(du -h "${path}" | awk '{print $1}'))"
    return 0
  fi
  ui_fail "${desc} mancante: ${path}"
  return 1
}

learn_require_cmd() {
  local cmd="$1"
  if command -v "${cmd}" >/dev/null 2>&1; then
    ui_ok "Tool disponibile: ${cmd}"
    return 0
  fi
  ui_fail "Tool mancante: ${cmd}"
  return 1
}

learn_check_prerequisites() {
  local ok=0
  ui_section "Verifica prerequisiti"
  learn_require_cmd openroad || ok=1
  learn_require_cmd yosys || ok=1
  learn_require_cmd sta || ok=1
  learn_require_cmd klayout || ok=1
  learn_orfs_env
  [[ -d "${FLOW}" ]] || { ui_fail "ORFS non trovato in ${FLOW}"; ok=1; }
  [[ -f "${TUTORIAL_SRC}/config.mk" ]] || { ui_fail "Config tutorial mancante in ${TUTORIAL_SRC}"; ok=1; }
  [[ -e "${TUTORIAL_ORFS}/config.mk" ]] || { ui_fail "Symlink ORFS tutorial mancante: ${TUTORIAL_ORFS}"; ok=1; }
  return "${ok}"
}

learn_validate_stage() {
  local stage="$1"
  learn_orfs_env
  case "${stage}" in
    synth)
      learn_require_file "$(learn_artifact 1_synth.odb)" "Synth ODB" &&
      learn_require_file "$(learn_artifact 1_2_yosys.v)" "Netlist post-synth"
      ;;
    floorplan)
      learn_require_file "$(learn_artifact 2_floorplan.odb)" "Floorplan ODB" &&
      learn_require_file "$(learn_artifact 2_4_floorplan_pdn.odb)" "PDN ODB"
      ;;
    place)
      learn_require_file "$(learn_artifact 3_place.odb)" "Placement ODB" &&
      learn_require_file "$(learn_artifact 3_5_place_dp.odb)" "Detailed placement ODB"
      ;;
    cts)
      learn_require_file "$(learn_artifact 4_cts.odb)" "CTS ODB"
      ;;
    route)
      learn_require_file "$(learn_artifact 5_route.odb)" "Route ODB" &&
      learn_require_file "$(learn_artifact route.guide)" "Route guide"
      ;;
    finish)
      learn_require_file "$(learn_artifact 6_final.gds)" "GDS finale" &&
      learn_require_file "$(learn_artifact 6_final.spef)" "SPEF finale"
      ;;
    *)
      ui_fail "Stage sconosciuto: ${stage}"
      return 1
      ;;
  esac
}

learn_grep_metric() {
  local report="$1" pattern="$2"
  if [[ -f "${report}" ]]; then
    rg -n "${pattern}" "${report}" | head -5 | sed 's/^/  /' || ui_note "Pattern non trovato in ${report}"
  fi
}
