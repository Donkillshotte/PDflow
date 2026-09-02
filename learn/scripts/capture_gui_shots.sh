#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RESULTS="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn"
SHOT_DIR="${ROOT}/learn/reference/gui-shots"
TCL="${ROOT}/learn/scripts/capture_gui_shots.tcl"
export DISPLAY="${DISPLAY:-:1}" SHOT_DIR
mkdir -p "${SHOT_DIR}"

capture() {
  local stem="$1" odb="$2"
  [[ -f "${odb}" ]] || { echo "SKIP $odb"; return 0; }
  echo "== $stem =="
  ODB_FILE="${odb}" SHOT_STEM="${stem}" openroad -exit -no_init "${TCL}"
}

capture 01_synth "${RESULTS}/1_synth.odb"
capture 02_floorplan "${RESULTS}/2_1_floorplan.odb"
capture 03_pdn "${RESULTS}/2_4_floorplan_pdn.odb"
capture 04_place_gp "${RESULTS}/3_3_place_gp.odb"
capture 05_place_dp "${RESULTS}/3_5_place_dp.odb"
capture 06_cts "${RESULTS}/4_cts.odb"
capture 07_grt "${RESULTS}/5_1_grt.odb"
capture 08_route "${RESULTS}/5_2_route.odb"
capture 09_final "${RESULTS}/6_final.odb"

# Do not delete 03_pdn.png: the glob *_pdn.png is too broad.
ls -lh "${SHOT_DIR}"/*.png
echo CAPTURE_ALL_DONE
