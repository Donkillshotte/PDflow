#!/usr/bin/env bash
# P5: ibex clock sweep.  {1.98, 2.75, 3.52} ns × {base yosys, abc_speed yosys}.
# 2.2 ns already in P0/P2. Never FLOW_VARIANT=flowlab/learn/base.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
A_NET="$ROOT/tools/OpenROAD-flow-scripts/flow/results/nangate45/ibex/camp_ibex_base/1_2_yosys.v"
S_NET="$ROOT/tools/OpenROAD-flow-scripts/flow/results/nangate45/ibex/camp_ibex_abcspeed/1_2_yosys.v"
LOGDIR=/tmp/campaign
mkdir -p "$LOGDIR"
SUMMARY="$LOGDIR/p5_ibex_clock.txt"
: > "$SUMMARY"

run_one() {
  local clk="$1" tag="$2" role="$3" net="$4"
  local clkkey
  clkkey="$(python3 -c "print(f'{float('$clk'):.2f}'.replace('.',''))")"
  local variant="camp_ibex_clk${clkkey}_${tag}"
  echo "=== P5 $variant clk=${clk} ===" | tee -a "$SUMMARY"
  if PYTHONPATH=learn python3 -c "from dse.experiments import ExperimentLog; import sys; sys.exit(0 if ExperimentLog().has('$variant','P5') else 1)"; then
    echo "skip already recorded $variant" | tee -a "$SUMMARY"
    return 0
  fi
  [[ -f "$net" ]] || { echo "missing netlist $net" | tee -a "$SUMMARY"; return 1; }
  date -u +%Y-%m-%dT%H:%M:%SZ > "$LOGDIR/${variant}.start"
  set +e
  DESIGN=ibex FLOW_VARIANT="$variant" SDC_NS="$clk" \
    SYNTH_NETLIST_FILES="$net" \
    /usr/bin/time -f "elapsed_s %e" bash "$ROOT/scripts/run_design_finish.sh" finish \
    > "$LOGDIR/${variant}.log" 2>&1
  local ec=$?
  set -e
  echo "EXIT:${ec}" >> "$LOGDIR/${variant}.log"
  date -u +%Y-%m-%dT%H:%M:%SZ > "$LOGDIR/${variant}.end"
  local elapsed
  elapsed="$(awk '/^elapsed_s /{print $2}' "$LOGDIR/${variant}.log" | tail -1)"
  local extra=()
  if [[ "$ec" -ne 0 ]]; then extra=(--status failed); fi
  PYTHONPATH=learn:learn/scripts python3 "$ROOT/learn/scripts/record_experiment.py" \
    --phase P5 --design ibex --variant "$variant" --role "$role" --clock "$clk" \
    --netlist "$net" --runtime-s "${elapsed:-0}" --exit-code "$ec" \
    --notes "P5 ibex clock sweep. Netlist $tag." \
    "${extra[@]}" | tee -a "$SUMMARY" || true
}

for clk in 1.98 2.75 3.52; do
  run_one "$clk" a base "$A_NET"
  run_one "$clk" s abc_speed "$S_NET"
done
echo P5_DONE | tee -a "$SUMMARY"
