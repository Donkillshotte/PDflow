#!/usr/bin/env python3
"""Recapture View menu, Tools menu, Timing Report tab, Find dialog."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

DISPLAY = os.environ.get("DISPLAY", ":1")
ROOT = Path("/workspace")
RESULTS = ROOT / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn"
SHOT = ROOT / "learn/reference/gui-shots"
TCL = ROOT / "learn/scripts/gui_session.tcl"
ENV = {**os.environ, "DISPLAY": DISPLAY, "QT_QPA_PLATFORM": "xcb",
       "XDG_RUNTIME_DIR": "/tmp/runtime-ubuntu"}


def run(cmd):
    return subprocess.run(cmd, env=ENV, check=False, text=True, capture_output=True)


def kill():
    run(["pkill", "-x", "openroad"])
    time.sleep(1)


def launch(odb):
    kill()
    env = {**ENV, "ODB_FILE": str(odb), "GUI_VIEW": "all"}
    subprocess.Popen(
        ["openroad", "-gui", "-no_splash", "-no_init", str(TCL)],
        env=env,
        stdout=open("/tmp/or-gui-session.log", "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    for _ in range(50):
        time.sleep(0.3)
        wid = find_wid()
        if wid:
            time.sleep(1.0)
            return wid
    raise RuntimeError("no window")


def find_wid():
    ids = run(["xdotool", "search", "--name", "OpenROAD -"]).stdout.split()
    best, area = None, -1
    for wid in ids:
        geo = run(["xdotool", "getwindowgeometry", wid]).stdout
        for line in geo.splitlines():
            if "Geometry:" in line:
                part = line.split(":", 1)[1].strip().split("+", 1)[0]
                w, h = map(int, part.split("x"))
                if w * h > area:
                    best, area = wid, w * h
    return best


def prep(wid):
    run(["xdotool", "windowactivate", "--sync", wid])
    run(["xdotool", "windowsize", wid, "1680", "1000"])
    run(["xdotool", "windowmove", wid, "20", "40"])
    time.sleep(0.7)


def click(wid, x, y, pause=0.45):
    run(["xdotool", "windowactivate", "--sync", wid])
    run(["xdotool", "mousemove", "--window", wid, str(x), str(y)])
    run(["xdotool", "click", "1"])
    time.sleep(pause)


def tcl(wid, cmd, pause=0.4):
    geo = run(["xdotool", "getwindowgeometry", "--shell", wid]).stdout
    vals = dict(line.split("=", 1) for line in geo.splitlines() if "=" in line)
    h = int(vals["HEIGHT"])
    click(wid, 420, h - 48, 0.15)
    run(["xdotool", "key", "ctrl+a"])
    run(["xdotool", "key", "BackSpace"])
    run(["xdotool", "type", "--delay", "5", cmd])
    run(["xdotool", "key", "Return"])
    time.sleep(pause)


def shot(wid, name):
    dest = SHOT / name
    run(["import", "-display", DISPLAY, "-window", wid, str(dest)])
    print("WROTE", dest, dest.stat().st_size)


def main():
    wid = launch(RESULTS / "6_final.odb")
    prep(wid)
    tcl(wid, "gui::fit", 0.8)
    tcl(wid, 'select -name "clk" -type Net', 0.5)

    # Menu bar y≈12 on this theme; File≈30, View≈78, Tools≈145, Windows≈230
    click(wid, 78, 12, 0.5)
    shot(wid, "win_view_menu.png")
    run(["xdotool", "key", "Escape"])
    time.sleep(0.2)

    click(wid, 145, 12, 0.5)
    shot(wid, "win_tools_menu.png")
    run(["xdotool", "key", "Escape"])
    time.sleep(0.2)

    click(wid, 230, 12, 0.5)
    shot(wid, "win_windows_menu.png")
    run(["xdotool", "key", "Escape"])
    time.sleep(0.2)

    # Toolbar Timing button
    click(wid, 248, 44, 0.7)
    shot(wid, "win_timing_toolbar.png")

    # Right-panel tabs sit above the console. Try Timing Report then Charts.
    for x, y, name in [
        (1430, 742, "win_tab_inspector.png"),
        (1520, 742, "win_tab_hierarchy.png"),
        (1610, 742, "win_tab_timing.png"),
        (1430, 768, "win_tab_charts.png"),
        (1550, 768, "win_tab_help.png"),
    ]:
        click(wid, x, y, 0.45)
        shot(wid, name)

    # Find dialog via toolbar
    click(wid, 95, 44, 0.6)
    shot(wid, "win_find_dialog.png")
    run(["xdotool", "key", "Escape"])

    tcl(wid, "report_checks -path_delay max -max_paths 3", 1.2)
    shot(wid, "win_report_checks.png")

    kill()
    print("RECAPTURE_DONE")


if __name__ == "__main__":
    main()
