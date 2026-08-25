#!/usr/bin/env bash
# Capture the real OpenROAD Qt window (menus, Display Control, canvas, console).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RESULTS="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn"
SHOT_DIR="${ROOT}/learn/reference/gui-shots"
TCL="${ROOT}/learn/scripts/gui_session.tcl"
export DISPLAY="${DISPLAY:-:1}"
export QT_QPA_PLATFORM=xcb
export QT_QPA_PLATFORMTHEME=gtk2
mkdir -p "${SHOT_DIR}"

kill_or() {
  pkill -f '/usr/bin/openroad' 2>/dev/null || true
  sleep 1
}

wait_window() {
  local i
  for i in $(seq 1 40); do
    if xdotool search --onlyvisible --class openroad >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.4
  done
  return 1
}

largest_openroad_id() {
  python3 - <<'PY'
import os, subprocess
ids = subprocess.check_output(
    ["xdotool", "search", "--onlyvisible", "--class", "openroad"],
    text=True,
).split()
best = None
best_area = -1
for wid in ids:
    geo = subprocess.check_output(["xdotool", "getwindowgeometry", wid], text=True)
    w = h = 0
    for line in geo.splitlines():
        if "Geometry:" in line:
            # Geometry: 800x600+10+10
            part = line.split(":", 1)[1].strip().split("+", 1)[0]
            w, h = map(int, part.split("x"))
    area = w * h
    if area > best_area:
        best_area = area
        best = wid
print(best or "")
PY
}

shot_window() {
  local dest="$1"
  local wid
  wid="$(largest_openroad_id)"
  if [[ -z "${wid}" ]]; then
    echo "NO_WINDOW for ${dest}" >&2
    return 1
  fi
  xdotool windowactivate --sync "${wid}"
  sleep 0.3
  # Maximize / size for a readable anatomy shot
  xdotool windowsize "${wid}" 1680 1000 || true
  xdotool windowmove "${wid}" 20 40 || true
  sleep 0.8
  # Fit again after resize via key F if the GUI supports it
  xdotool key --window "${wid}" F || true
  sleep 0.4
  import -display "${DISPLAY}" -window "${wid}" "${dest}"
  echo "WROTE ${dest} ($(stat -c%s "${dest}") bytes) window=${wid}"
}

launch() {
  local odb="$1" view="$2"
  kill_or
  export ODB_FILE="${odb}" GUI_VIEW="${view}"
  openroad -gui -no_splash -no_init "${TCL}" >/tmp/or-gui-session.log 2>&1 &
  echo $! > /tmp/or-gui-session.pid
  wait_window
  sleep 2.5
}

capture_pair() {
  local stem="$1" odb="$2" view="$3"
  [[ -f "${odb}" ]] || { echo "SKIP missing ${odb}"; return 0; }
  echo "== Qt ${stem} view=${view} =="
  launch "${odb}" "${view}"
  shot_window "${SHOT_DIR}/${stem}.png"
}

# Full-window anatomy + stage gallery
capture_pair win_anatomy "${RESULTS}/6_final.odb" all
capture_pair win_pdn "${RESULTS}/2_4_floorplan_pdn.odb" pdn
capture_pair win_place_gp "${RESULTS}/3_3_place_gp.odb" instances
capture_pair win_place_dp "${RESULTS}/3_5_place_dp.odb" instances
capture_pair win_cts_clock "${RESULTS}/4_cts.odb" clock
capture_pair win_route "${RESULTS}/5_2_route.odb" signal
capture_pair win_final "${RESULTS}/6_final.odb" all
capture_pair win_floorplan_rows "${RESULTS}/2_1_floorplan.odb" rows
capture_pair win_synth "${RESULTS}/1_synth.odb" all

# Also try save_image from a live GUI for stages that fail headless
python3 - <<'PY'
import os, subprocess, time
# leftover process is fine; next launch kills it
print("qt capture script python side idle")
PY

kill_or
ls -lh "${SHOT_DIR}"/win_*.png 2>/dev/null || true
echo QT_CAPTURE_DONE
