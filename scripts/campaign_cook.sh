#!/usr/bin/env bash
# Sequential campaign cook helper. One heavy job. Never flowlab/learn/base.
# Usage: DESIGN=spi FLOW_VARIANT=camp_spi_base ROLE=base PHASE=P0 [SDC_NS=1.0] \
#        [SYNTH_NETLIST_FILES=...] [ABC_SPEED=1] bash scripts/campaign_cook.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESIGN="${DESIGN:?}"
VARIANT="${FLOW_VARIANT:?}"
ROLE="${ROLE:?}"
PHASE="${PHASE:?}"
SDC_NS="${SDC_NS:-}"
LOGDIR="${LOGDIR:-/tmp/campaign}"
mkdir -p "${LOGDIR}"
STAMP="${LOGDIR}/${VARIANT}"
date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP}.start"
set +e
/usr/bin/time -f "elapsed_s %e" \
  env DESIGN="${DESIGN}" FLOW_VARIANT="${VARIANT}" SDC_NS="${SDC_NS}" \
      SYNTH_NETLIST_FILES="${SYNTH_NETLIST_FILES:-}" \
      ABC_SPEED="${ABC_SPEED:-}" DIE_AREA="${DIE_AREA:-}" CORE_AREA="${CORE_AREA:-}" \
      CORE_UTILIZATION="${CORE_UTILIZATION:-}" SWAP_ARITH_OPERATORS="${SWAP_ARITH_OPERATORS:-}" \
  bash "${ROOT}/scripts/run_design_finish.sh" finish > "${STAMP}.log" 2>&1
EC=$?
set -e
echo "EXIT:${EC}" >> "${STAMP}.log"
date -u +%Y-%m-%dT%H:%M:%SZ > "${STAMP}.end"
ELAPSED="$(awk '/^elapsed_s /{print $2}' "${STAMP}.log" | tail -1)"
NOTE="${NOTES:-}"
cd "${ROOT}"
PYTHONPATH=learn:learn/scripts python3 learn/scripts/record_experiment.py \
  --phase "${PHASE}" --design "${DESIGN}" --variant "${VARIANT}" --role "${ROLE}" \
  ${SDC_NS:+--clock "${SDC_NS}"} \
  ${SYNTH_NETLIST_FILES:+--netlist "${SYNTH_NETLIST_FILES}"} \
  --runtime-s "${ELAPSED:-0}" --exit-code "${EC}" \
  ${NOTE:+--notes "${NOTE}"}
exit "${EC}"
