#!/usr/bin/env bash
# Helper per invocare ORFS dal corso didattico.

learn_orfs_env() {
  export LEARN_ROOT="${LEARN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
  export REPO_ROOT="${REPO_ROOT:-$(cd "${LEARN_ROOT}/.." && pwd)}"
  export FLOW="${FLOW:-${REPO_ROOT}/tools/OpenROAD-flow-scripts/flow}"
  export TUTORIAL_SRC="${LEARN_ROOT}/designs/nangate45/gcd-tutorial"
  export TUTORIAL_ORFS="${FLOW}/designs/nangate45/gcd-tutorial"
  mkdir -p "$(dirname "${TUTORIAL_ORFS}")"
  ln -sfn "${TUTORIAL_SRC}" "${TUTORIAL_ORFS}"
  export DESIGN_CONFIG="${DESIGN_CONFIG:-./designs/nangate45/gcd-tutorial/config.mk}"
  export FLOW_VARIANT="${FLOW_VARIANT:-learn}"
  export CORE_UTILIZATION="${CORE_UTILIZATION:-35}"
  export OPENROAD_EXE="${OPENROAD_EXE:-$(command -v openroad)}"
  export OPENSTA_EXE="${OPENSTA_EXE:-$(command -v sta)}"
  export YOSYS_EXE="${YOSYS_EXE:-$(command -v yosys)}"
  export RESULTS="${FLOW}/results/nangate45/gcd/${FLOW_VARIANT}"
  export LOGS="${FLOW}/logs/nangate45/gcd/${FLOW_VARIANT}"
  export REPORTS="${FLOW}/reports/nangate45/gcd/${FLOW_VARIANT}"
}

learn_make() {
  learn_orfs_env
  (
    cd "${FLOW}"
    make \
      DESIGN_CONFIG="${DESIGN_CONFIG}" \
      FLOW_VARIANT="${FLOW_VARIANT}" \
      CORE_UTILIZATION="${CORE_UTILIZATION}" \
      OPENROAD_EXE="${OPENROAD_EXE}" \
      OPENSTA_EXE="${OPENSTA_EXE}" \
      YOSYS_EXE="${YOSYS_EXE}" \
      "$@"
  )
}

learn_gui() {
  local target="$1"
  ui_step "GUI" "Apertura ${target} (usa il pulsante Desktop su cursor.com/agents/...)"
  learn_make "gui_${target}" || learn_make "open_${target}" || true
}

learn_artifact() {
  local relpath="$1"
  echo "${RESULTS}/${relpath}"
}

learn_log() {
  local relpath="$1"
  echo "${LOGS}/${relpath}"
}

learn_report() {
  local relpath="$1"
  echo "${REPORTS}/${relpath}"
}

learn_show_tree() {
  ui_section "Albero artefatti attuale (results/${FLOW_VARIANT})"
  if [[ -d "${RESULTS}" ]]; then
    ls -lh "${RESULTS}" 2>/dev/null | tail -n +2 | sed 's/^/  /' || true
  else
    ui_note "Nessun risultato ancora — verrà creato durante gli esercizi."
  fi
}
