#!/usr/bin/env python3
"""Drive the OpenROAD Qt GUI and capture window screenshots for the course atlas."""
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
ENV = {
    **os.environ,
    "DISPLAY": DISPLAY,
    "QT_QPA_PLATFORM": "xcb",
    "XDG_RUNTIME_DIR": "/tmp/runtime-ubuntu",
}


def run(cmd, **kw):
    return subprocess.run(cmd, env=ENV, check=False, text=True, capture_output=True, **kw)


def kill_openroad():
    run(["pkill", "-x", "openroad"])
    time.sleep(1)


def launch(odb: Path) -> None:
    kill_openroad()
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
        if find_main_window():
            time.sleep(1.2)
            return
    raise RuntimeError(f"OpenROAD window did not appear for {odb}")


def find_main_window() -> str | None:
    out = run(["xdotool", "search", "--name", "OpenROAD -"]).stdout.strip().split()
    best, best_area = None, -1
    for wid in out:
        geo = run(["xdotool", "getwindowgeometry", wid]).stdout
        w = h = 0
        for line in geo.splitlines():
            if "Geometry:" in line:
                part = line.split(":", 1)[1].strip().split("+", 1)[0]
                w, h = (int(x) for x in part.split("x"))
        area = w * h
        if area > best_area:
            best, best_area = wid, area
    return best


def prepare_window() -> str:
    wid = find_main_window()
    if not wid:
        raise RuntimeError("no OpenROAD window")
    run(["xdotool", "windowactivate", "--sync", wid])
    run(["xdotool", "windowsize", wid, "1680", "1000"])
    run(["xdotool", "windowmove", wid, "20", "40"])
    time.sleep(0.8)
    return wid


def click_tcl(wid: str) -> None:
    geo = run(["xdotool", "getwindowgeometry", "--shell", wid]).stdout
    vals = dict(line.split("=", 1) for line in geo.splitlines() if "=" in line)
    h = int(vals["HEIGHT"])
    run(["xdotool", "windowactivate", "--sync", wid])
    run(["xdotool", "mousemove", "--window", wid, "420", str(h - 48)])
    run(["xdotool", "click", "1"])
    time.sleep(0.15)


def tcl(wid: str, cmd: str, pause: float = 0.35) -> None:
    click_tcl(wid)
    # Clear leftover text
    run(["xdotool", "key", "ctrl+a"])
    run(["xdotool", "key", "BackSpace"])
    run(["xdotool", "type", "--delay", "5", cmd])
    run(["xdotool", "key", "Return"])
    time.sleep(pause)


def shot(wid: str, name: str) -> Path:
    dest = SHOT / name
    run(["import", "-display", DISPLAY, "-window", wid, str(dest)])
    print(f"WROTE {dest} ({dest.stat().st_size} bytes)")
    return dest


def click_xy(wid: str, x: int, y: int) -> None:
    run(["xdotool", "windowactivate", "--sync", wid])
    run(["xdotool", "mousemove", "--window", wid, str(x), str(y)])
    run(["xdotool", "click", "1"])
    time.sleep(0.4)


def main() -> None:
    SHOT.mkdir(parents=True, exist_ok=True)

    # --- 6_final: window anatomy + display filters + inspector/timing ---
    launch(RESULTS / "6_final.odb")
    wid = prepare_window()
    tcl(wid, "gui::fit", 0.8)
    shot(wid, "win_anatomy.png")

    # Hide metals one-by-one demo: only metal2+metal3 (typical signal)
    for layer in [
        "metal1",
        "metal4",
        "metal5",
        "metal6",
        "metal7",
        "metal8",
        "metal9",
        "metal10",
        "via1",
        "via3",
        "via4",
        "via5",
        "via6",
        "via7",
        "via8",
        "via9",
    ]:
        tcl(wid, f'gui::set_display_controls "Layers/{layer}" visible false', 0.08)
    tcl(wid, "gui::fit", 0.5)
    shot(wid, "win_layers_m2m3.png")

    # Restore layers, hide signal nets, keep clock
    tcl(wid, 'gui::set_display_controls "Layers/*" visible true', 0.4)
    tcl(wid, 'gui::set_display_controls "Nets/Signal" visible false', 0.3)
    tcl(wid, 'gui::set_display_controls "Nets/Clock" visible true', 0.3)
    tcl(wid, "gui::fit", 0.5)
    shot(wid, "win_clock_filter.png")

    tcl(wid, 'gui::set_display_controls "Nets/*" visible true', 0.3)
    tcl(wid, 'select -name "clk" -type Net', 0.5)
    tcl(wid, "gui::fit", 0.4)
    shot(wid, "win_net_clk_selected.png")

    # Toolbar: Inspect is the 3rd word button (~ x=145, y=58)
    click_xy(wid, 155, 58)
    shot(wid, "win_inspector_tab.png")

    # Toolbar Timing (~ x=230)
    click_xy(wid, 230, 58)
    time.sleep(0.6)
    shot(wid, "win_timing_tab.png")

    # Charts tab on the right panel bottom. Approx x=1580 y=780
    click_xy(wid, 1540, 790)
    time.sleep(0.5)
    shot(wid, "win_charts_tab.png")

    # View menu
    click_xy(wid, 55, 18)
    time.sleep(0.4)
    shot(wid, "win_view_menu.png")
    run(["xdotool", "key", "Escape"])
    time.sleep(0.2)

    # Display Control: click Nets row to expand (~ x=40, y=430)
    click_xy(wid, 36, 455)
    time.sleep(0.3)
    shot(wid, "win_display_nets_expanded.png")

    # --- stage windows ---
    stages = [
        ("win_synth.png", RESULTS / "1_synth.odb"),
        ("win_floorplan.png", RESULTS / "2_1_floorplan.odb"),
        ("win_tapcell.png", RESULTS / "2_3_floorplan_tapcell.odb"),
        ("win_pdn.png", RESULTS / "2_4_floorplan_pdn.odb"),
        ("win_place_gp.png", RESULTS / "3_3_place_gp.odb"),
        ("win_place_dp.png", RESULTS / "3_5_place_dp.odb"),
        ("win_cts.png", RESULTS / "4_cts.odb"),
        ("win_grt.png", RESULTS / "5_1_grt.odb"),
        ("win_route.png", RESULTS / "5_2_route.odb"),
        ("win_final.png", RESULTS / "6_final.odb"),
    ]
    for name, odb in stages:
        if not odb.exists():
            print(f"SKIP {odb}")
            continue
        launch(odb)
        wid = prepare_window()
        tcl(wid, "gui::fit", 1.0)
        if "cts" in name:
            tcl(wid, 'gui::set_display_controls "Nets/Signal" visible false', 0.2)
            tcl(wid, 'gui::set_display_controls "Nets/Clock" visible true', 0.2)
            tcl(wid, "gui::fit", 0.5)
        if "floorplan" in name:
            tcl(wid, 'gui::set_display_controls "Rows" visible true', 0.2)
            tcl(wid, "gui::fit", 0.5)
        if "pdn" in name:
            tcl(wid, 'gui::set_display_controls "Nets/Signal" visible false', 0.2)
            tcl(wid, 'gui::set_display_controls "Nets/Power" visible true', 0.2)
            tcl(wid, 'gui::set_display_controls "Nets/Ground" visible true', 0.2)
            tcl(wid, "gui::fit", 0.5)
        shot(wid, name)

    kill_openroad()
    print("QT_GALLERY_DONE")
    for p in sorted(SHOT.glob("win_*.png")):
        print(f"  {p.name:32s} {p.stat().st_size:8d}")


if __name__ == "__main__":
    main()
