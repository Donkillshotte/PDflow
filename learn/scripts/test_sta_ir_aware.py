#!/usr/bin/env python3
"""IR-aware STA: fixture via CLI + live flowlab report. Avoids SciPy import."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
ROOT = _SCRIPTS.parents[1]
GOLD_IR_MV = 45.298

from export_sta_arrivals import parse_sta_path_report  # noqa: E402

PATH_DUMP = """Startpoint: ff1
Endpoint: ff2
  Delay     Time   Description
---------------------------------------------------------
   0.000000    0.000000   clock core_clock (rise edge)
   0.000000    0.000000 ^ ff1/CK (DFF_X1)
   0.100000    0.100000 ^ ff1/Q (DFF_X1)
   0.000000    0.100000 ^ g2/A (INV_X1)
   0.050000    0.150000 v g2/ZN (INV_X1)
   0.000000    0.150000 v ff2/D (DFF_X1)
               0.150000   data arrival time
               0.420511   data required time
               0.023500   slack (MET)
STA_PATH_END
"""


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> int:
    wp = parse_sta_path_report(PATH_DUMP)
    check(wp is not None and wp["n_gates"] == 2, "parse worst path")
    vdd, alpha = 1.1, 1.3
    d_ff = 0.1 * (vdd / 0.9) ** alpha
    slack_ir = 0.0235 - (d_ff + 0.05 - 0.15)

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{_SCRIPTS}:/usr/lib/python3/dist-packages" + (
        f":{env['PYTHONPATH']}" if env.get("PYTHONPATH") else ""
    )
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        sta_p = tdir / "sta.json"
        spice_p = tdir / "pg.sp"
        map_p = tdir / "map.csv"
        out_p = tdir / "out.json"
        sta_p.write_text(
            json.dumps(
                {
                    "worst_path": wp,
                    "pins": [
                        {"inst": "ff1", "inst_key": "ff1", "cell": "DFF_X1", "pin": "Q", "rise_ns": 0.1},
                        {"inst": "g2", "inst_key": "g2", "cell": "INV_X1", "pin": "ZN", "rise_ns": 0.15},
                    ],
                }
            )
        )
        spice_p.write_text("* Sink for ff1/VDD\nI1 n1 0 DC 1e-6\n")
        map_p.write_text("node,x_dbu,y_dbu,v,ir_mv,seq\nn1,0,0,0.9,200,0\n")
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "sta_ir_aware.py"),
                "--sta",
                str(sta_p),
                "--spice",
                str(spice_p),
                "--map",
                str(map_p),
                "--out",
                str(out_p),
                "--variant",
                "fixture",
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        check(proc.returncode == 0, f"fixture CLI exit 0 ({proc.stderr[-200:]})")
        check("STA_IR_AWARE_DONE" in proc.stdout, "fixture prints DONE")
        rep = json.loads(out_p.read_text())
        check(rep["ok"] is True, "fixture READY")
        check(rep["sta"]["n_joined"] == 1, "fixture joins ff1")
        check(abs(rep["sta"]["slack_ir_ns"] - slack_ir) < 1e-12, "fixture slack_ir")
        check(len(rep["path_gates"]) == 2, "per-gate table")
        check(any(g["inst"] == "ff1" and g["joined"] for g in rep["path_gates"]), "joined gate in table")
        stages = (rep.get("timing") or {}).get("path") or {}
        check(len(stages.get("stages") or []) == len(wp["stages"]), "stages attached on path")

    live = ROOT / "learn/sim/reports/sta_ir_aware_flowlab.json"
    if live.is_file():
        blob = json.loads(live.read_text())
        check(blob.get("ok") is True, "live flowlab report ok")
        check(abs(float(blob["sta"]["slack_ns"]) - 0.004644) < 1e-9, "live slack")
        check(abs(float(blob["sta"]["slack_ir_ns"]) - 0.004023) < 2e-6, "live slack_ir")
        check(blob["sta"]["n_joined"] == 18 and blob["sta"]["n_gates"] == 18, "live 18/18 gates")
        check(len(blob.get("path_gates") or []) == 18, "live path_gates")
        check(all(g.get("joined") for g in blob["path_gates"]), "live all path gates joined")
        check(abs(float(blob["ir"]["worst_cell_ir_mv"]) - 6.075) < 0.02, "live worst cell is current_run 6.075 mV")
        check(str(blob["ir"]["map"]).endswith("dynamic_ir_flowlab_direct.map.csv"), "live map is current_run")
        check(not str(blob["sta"]["arrivals"]).startswith("/"), "report paths are repo-relative")
    wrapper = (_SCRIPTS / "run_sta_ir_aware.sh").read_text()
    check('dynamic_ir_${VARIANT}_direct.map.csv' in wrapper, "wrapper pins current_run map")
    check('dynamic_ir_${VARIANT}.map.csv' not in wrapper, "wrapper has no gold map fallback")
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        gold_map = tdir / "dynamic_ir_flowlab.map.csv"
        gold_map.write_text("node,x_dbu,y_dbu,v,ir_mv,seq\nn1,0,0,0.9,200,0\n")
        sta_p = tdir / "sta.json"
        spice_p = tdir / "pg.sp"
        out_p = tdir / "out.json"
        sta_p.write_text(json.dumps({"worst_path": wp, "pins": []}))
        spice_p.write_text("* Sink\nI1 n1 0 DC 1e-6\n")
        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "sta_ir_aware.py"),
                "--sta",
                str(sta_p),
                "--spice",
                str(spice_p),
                "--map",
                str(gold_map),
                "--out",
                str(out_p),
                "--variant",
                "fixture",
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        check(proc.returncode == 2, f"refuses gold map exit 2 ({proc.returncode})")
        check("will not scale STA from locked gold Dynamic IR map" in proc.stderr, "refuses gold map in stderr")
        check(not out_p.is_file(), "gold map does not write a report")
    gold = json.loads((ROOT / "learn/sim/reports/dynamic_ir_flowlab.json").read_text())
    check(gold.get("gold") is True, "gold sentinel")
    check(abs(float(gold["worst_droop_mv"]) - GOLD_IR_MV) < 0.02, "gold 45.298 mV untouched")
    print("ALL test_sta_ir_aware PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
