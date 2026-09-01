#!/usr/bin/env bash
# Q4: recook the Q1 gcd §5 winner at a clock where the base already closes.
# camp_gcd_clk055_a closed at 0.55 ns. Same netlist (A yosys), knobs LB=0.25 util=35.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
A_NET="$ROOT/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/1_2_yosys.v"
VARIANT=camp_gcd_q4_d25u35_c055
LOGDIR=/tmp/campaign
mkdir -p "$LOGDIR"
if PYTHONPATH=learn python3 -c "from dse.experiments import ExperimentLog; import sys; sys.exit(0 if ExperimentLog().has('$VARIANT','Q4') else 1)"; then
  echo "skip already recorded $VARIANT"
  exit 0
fi
[[ -f "$A_NET" ]] || { echo "REFUSED missing $A_NET" >&2; exit 2; }
set +e
DESIGN=gcd FLOW_VARIANT="$VARIANT" SDC_NS=0.55 \
  CORE_UTILIZATION=35 PLACE_DENSITY_LB_ADDON=0.25 \
  SYNTH_NETLIST_FILES="$A_NET" \
  /usr/bin/time -f "elapsed_s %e" bash "$ROOT/scripts/run_design_finish.sh" finish \
  > "$LOGDIR/${VARIANT}.log" 2>&1
ec=$?
set -e
echo "EXIT:${ec}" >> "$LOGDIR/${VARIANT}.log"
elapsed="$(awk '/^elapsed_s /{print $2}' "$LOGDIR/${VARIANT}.log" | tail -1)"
status_flag=()
if [[ "$ec" -ne 0 ]]; then status_flag=(--status failed); fi
PYTHONPATH=learn:learn/scripts python3 "$ROOT/learn/scripts/record_experiment.py" \
  --phase Q4 --design gcd --variant "$VARIANT" --role knob --clock 0.55 \
  --netlist "$A_NET" --runtime-s "${elapsed:-0}" --exit-code "$ec" \
  --extra '{"place_density_lb_addon": 0.25, "core_utilization": 35}' \
  --notes "Q4 area-regime: Q1 winner knobs at 0.55 ns where camp_gcd_clk055_a closes." \
  "${status_flag[@]}"
echo "Q4_DONE ec=$ec"
