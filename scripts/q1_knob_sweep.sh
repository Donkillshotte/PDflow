#!/usr/bin/env bash
# Q1 physical-knob sweep. Sequential. Never FLOW_VARIANT=flowlab.
# Offsets from each design's config default:
#   PLACE_DENSITY_LB_ADDON default 0.20 → {0.15, 0.20, 0.25}
#   gcd CORE_UTILIZATION default 35 → {25, 35, 45}; skip the known center.
#   ibex: LB ±0.05 at util 50; util ±10 at LB 0.20.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
GCD_NET="$ROOT/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/1_2_yosys.v"
IBEX_NET="$ROOT/tools/OpenROAD-flow-scripts/flow/results/nangate45/ibex/camp_ibex_base/1_2_yosys.v"
LOGDIR=/tmp/campaign
mkdir -p "$LOGDIR"
SUMMARY="$LOGDIR/q1_knob_sweep.txt"
: > "$SUMMARY"
SCOPE="${1:-all}"

run_one() {
  local design="$1" variant="$2" clk="$3" net="$4" lb="$5" util="$6"
  echo "=== Q1 $variant design=${design} lb=${lb} util=${util} ===" | tee -a "$SUMMARY"
  if PYTHONPATH=learn python3 -c "from dse.experiments import ExperimentLog; import sys; sys.exit(0 if ExperimentLog().has('$variant','Q1') else 1)"; then
    echo "skip already recorded $variant" | tee -a "$SUMMARY"
    return 0
  fi
  if [[ ! -f "$net" ]]; then
    echo "REFUSED missing netlist $net" | tee -a "$SUMMARY"
    return 2
  fi
  date -u +%Y-%m-%dT%H:%M:%SZ > "$LOGDIR/${variant}.start"
  set +e
  DESIGN="$design" FLOW_VARIANT="$variant" SDC_NS="$clk" \
    CORE_UTILIZATION="$util" PLACE_DENSITY_LB_ADDON="$lb" \
    SYNTH_NETLIST_FILES="$net" \
    /usr/bin/time -f "elapsed_s %e" bash "$ROOT/scripts/run_design_finish.sh" finish \
    > "$LOGDIR/${variant}.log" 2>&1
  local ec=$?
  set -e
  echo "EXIT:${ec}" >> "$LOGDIR/${variant}.log"
  date -u +%Y-%m-%dT%H:%M:%SZ > "$LOGDIR/${variant}.end"
  local elapsed
  elapsed="$(awk '/^elapsed_s /{print $2}' "$LOGDIR/${variant}.log" | tail -1)"
  local status_flag=()
  if [[ "$ec" -ne 0 ]]; then
    status_flag=(--status failed)
  fi
  PYTHONPATH=learn:learn/scripts python3 "$ROOT/learn/scripts/record_experiment.py" \
    --phase Q1 --design "$design" --variant "$variant" --role knob --clock "$clk" \
    --netlist "$net" --runtime-s "${elapsed:-0}" --exit-code "$ec" \
    --extra "{\"place_density_lb_addon\": ${lb}, \"core_utilization\": ${util}}" \
    --notes "Q1 knob sweep. LB=${lb} UTIL=${util}. Base yosys netlist." \
    "${status_flag[@]}" | tee -a "$SUMMARY"
  if [[ "$ec" -ne 0 ]]; then
    echo "FAIL $variant ec=$ec (recorded, not retried)" | tee -a "$SUMMARY"
    return 0
  fi
}

if [[ "$SCOPE" == "all" || "$SCOPE" == "gcd" ]]; then
  [[ -f "$GCD_NET" ]] || { echo "REFUSED missing $GCD_NET" >&2; exit 2; }
  for lb in 0.15 0.20 0.25; do
    for util in 25 35 45; do
      if [[ "$lb" == "0.20" && "$util" == "35" ]]; then
        echo "skip gcd center lb=0.20 util=35 (camp_gcd_base)" | tee -a "$SUMMARY"
        continue
      fi
      key="$(python3 -c "print(f'd{int(float('$lb')*100):02d}u{int('$util')}')")"
      run_one gcd "camp_gcd_q1_${key}" 0.46 "$GCD_NET" "$lb" "$util"
    done
  done
fi

if [[ "$SCOPE" == "all" || "$SCOPE" == "ibex" ]]; then
  [[ -f "$IBEX_NET" ]] || { echo "REFUSED missing $IBEX_NET" >&2; exit 2; }
  run_one ibex camp_ibex_q1_d15u50 2.2 "$IBEX_NET" 0.15 50
  run_one ibex camp_ibex_q1_d25u50 2.2 "$IBEX_NET" 0.25 50
  run_one ibex camp_ibex_q1_d20u40 2.2 "$IBEX_NET" 0.20 40
  run_one ibex camp_ibex_q1_d20u60 2.2 "$IBEX_NET" 0.20 60
fi

echo "Q1_SCOPE_${SCOPE}_DONE" | tee -a "$SUMMARY"
