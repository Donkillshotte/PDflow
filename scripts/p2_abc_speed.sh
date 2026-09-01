#!/usr/bin/env bash
# P2: abc_speed vs P0 base on designs whose base was ABC_AREA.
# AES/dynamic_node ORFS default is already ABC speed — recorded as skipped.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOGDIR=/tmp/campaign
mkdir -p "$LOGDIR"
SUMMARY="$LOGDIR/p2_abc_speed.txt"
: > "$SUMMARY"

record_skip() {
  local design="$1" variant="$2" clk="$3" why="$4"
  if PYTHONPATH=learn python3 -c "from dse.experiments import ExperimentLog; import sys; sys.exit(0 if ExperimentLog().has('$variant','P2') else 1)"; then
    echo "skip already recorded $variant" | tee -a "$SUMMARY"
    return 0
  fi
  PYTHONPATH=learn:learn/scripts python3 "$ROOT/learn/scripts/record_experiment.py" \
    --phase P2 --design "$design" --variant "$variant" --role abc_speed --clock "$clk" \
    --status frozen --notes "$why" | tee -a "$SUMMARY" || true
}

run_speed() {
  local design="$1" variant="$2" clk="$3"
  echo "=== P2 $variant ===" | tee -a "$SUMMARY"
  if PYTHONPATH=learn python3 -c "from dse.experiments import ExperimentLog; import sys; sys.exit(0 if ExperimentLog().has('$variant','P2') else 1)"; then
    echo "skip already recorded $variant" | tee -a "$SUMMARY"
    return 0
  fi
  date -u +%Y-%m-%dT%H:%M:%SZ > "$LOGDIR/${variant}.start"
  set +e
  DESIGN="$design" FLOW_VARIANT="$variant" SDC_NS="$clk" ABC_SPEED=1 \
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
    --phase P2 --design "$design" --variant "$variant" --role abc_speed --clock "$clk" \
    --runtime-s "${elapsed:-0}" --exit-code "$ec" \
    --notes "P2 ABC_SPEED=1 ABC_AREA=0 vs P0 ABC_AREA base." \
    "${extra[@]}" | tee -a "$SUMMARY" || true
  return 0
}

# P0 gcd already has camp_gcd_dse_fast (orfs_abc_speed) at 0.46.
record_skip gcd camp_gcd_abc_speed 0.46 "P2 skip: P0 already has camp_gcd_dse_fast (orfs_abc_speed) at 0.46 ns."

run_speed spi camp_spi_abcspeed 1.0
run_speed ibex camp_ibex_abcspeed 2.2

# Confirm ORFS default is already speed before skipping.
record_skip dynamic_node camp_dynamic_node_abc_speed 6.0 \
  "P2 skip: P0 ORFS recipe already used ABC speed (no ABC_AREA in official config)."
record_skip aes camp_aes_abc_speed 0.82 \
  "P2 skip: P0 ORFS recipe already used ABC speed (log: Using ABC speed script). Not a new axis."

echo P2_DONE | tee -a "$SUMMARY"
