#!/usr/bin/env bash
# P1: GCD clock sweep. Sequential. Never FLOW_VARIANT=flowlab.
# Clocks 0.40/0.55/0.70/0.90 × netlists A/B/C. 0.46 already in P0.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
A_NET="$ROOT/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/1_2_yosys.v"
B_NET="$ROOT/learn/sim/dse/netlists/54142494d890.v"
C_NET="$ROOT/learn/sim/dse/netlists/52e0ecacb19b.v"
LOGDIR=/tmp/campaign
mkdir -p "$LOGDIR"
SUMMARY="$LOGDIR/p1_gcd_clock_sweep.txt"
: > "$SUMMARY"

run_one() {
  local clk="$1" tag="$2" role="$3" net="$4"
  local clkkey
  clkkey="$(python3 -c "print(f'{float('$clk'):.2f}'.replace('.',''))")"
  local variant="camp_gcd_clk${clkkey}_${tag}"
  echo "=== P1 $variant clk=${clk} role=${role} ===" | tee -a "$SUMMARY"
  if PYTHONPATH=learn python3 -c "from dse.experiments import ExperimentLog; import sys; sys.exit(0 if ExperimentLog().has('$variant','P1') else 1)"; then
    echo "skip already recorded $variant" | tee -a "$SUMMARY"
    return 0
  fi
  date -u +%Y-%m-%dT%H:%M:%SZ > "$LOGDIR/${variant}.start"
  set +e
  DESIGN=gcd FLOW_VARIANT="$variant" SDC_NS="$clk" CORE_UTILIZATION=35 \
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
    --phase P1 --design gcd --variant "$variant" --role "$role" --clock "$clk" \
    --netlist "$net" --runtime-s "${elapsed:-0}" --exit-code "$ec" \
    --notes "P1 GCD clock sweep. CORE_UTILIZATION=35. Netlist $tag." \
    "${status_flag[@]}" | tee -a "$SUMMARY"
  if [[ "$ec" -ne 0 ]]; then
    echo "FAIL $variant ec=$ec" | tee -a "$SUMMARY"
    return "$ec"
  fi
}

for clk in 0.40 0.55 0.70 0.90; do
  run_one "$clk" a base "$A_NET"
  run_one "$clk" b dse_small "$B_NET"
  run_one "$clk" c dse_fast "$C_NET"
done
echo "P1_DONE" | tee -a "$SUMMARY"
