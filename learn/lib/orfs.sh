#!/usr/bin/env bash
# Helper to invoke ORFS from the tutorial course.

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
  ui_step "GUI" "Opening ${target} (use the Desktop button on cursor.com/agents/...)"
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
  ui_section "Current artifact tree (results/${FLOW_VARIANT})"
  if [[ -d "${RESULTS}" ]]; then
    ls -lh "${RESULTS}" 2>/dev/null | tail -n +2 | sed 's/^/  /' || true
  else
    ui_note "No results yet — will be created during exercises."
  fi
}

# One-liner the student can copy (never "make ...").
learn_make_hint() {
  local tgt="${*:-<target>}"
  ui_note "Equivalent command from flow/ (copy entire line — never «make ...»):"
  ui_code "cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \\
     FLOW_VARIANT=learn CORE_UTILIZATION=35 ${tgt}"
}

learn_golden() {
  ui_tip "Compare reports with learn/reference/golden-metrics.md (util 35, SDC 0.46 ns)."
}

learn_atlas() {
  ui_tip "GUI atlas: learn/reference/gui-atlas.md — PNG: $*"
}
