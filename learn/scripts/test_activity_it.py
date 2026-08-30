#!/usr/bin/env python3
"""Activity → I(t): name-join only. Missing stays missing. No RTL→ITerm map."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "learn"))
sys.path.insert(0, str(REPO / "learn" / "scripts"))

from dse.activity import load_activity  # noqa: E402
from dse.f4_oracle import attach_activity_flags  # noqa: E402
from pdn_activity import parse_saif, parse_vcd, plan_events  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("ok  " if cond else "FAIL") + " " + msg)
    if not cond:
        FAILS.append(msg)


def main() -> int:
    check(load_activity(design_id="aes") is None, "missing aes waveform stays missing")
    bare = attach_activity_flags(["w"], variant="aes", design_id="aes")
    check(bare == ["w"], "no --saif/--vcd when the waveform file is absent")

    tmp = Path(tempfile.mkdtemp(prefix="dse-act-"))
    saif_path = tmp / "aes.saif"
    saif_path.write_text(
        "(SAIFILE\n"
        "(TIMESCALE 1 ps)\n"
        "(INSTANCE top\n"
        "  (INSTANCE _20803_\n"
        "    (NET\n"
        "      (Z (T0 10000) (T1 0) (TC 0) (IG 0))\n"
        "    )\n"
        "  )\n"
        "  (INSTANCE _20800_\n"
        "    (NET\n"
        "      (Z (T0 4000) (T1 6000) (TC 4) (IG 0))\n"
        "    )\n"
        "  )\n"
        ")\n"
        ")\n"
    )
    vcd_path = tmp / "gate.vcd"
    vcd_path.write_text(
        "$date now $end\n$timescale 1ps $end\n"
        "$scope module _479_ $end\n$var wire 1 ! ZN $end\n$upscope $end\n"
        "$enddefinitions $end\n$dumpvars\n0!\n$end\n#250\n1!\n"
    )

    prev = os.environ.get("DSE_ACTIVITY")
    os.environ["DSE_ACTIVITY"] = str(saif_path)
    try:
        flagged = attach_activity_flags(["w"], variant="aes", design_id="aes")
    finally:
        if prev is None:
            os.environ.pop("DSE_ACTIVITY", None)
        else:
            os.environ["DSE_ACTIVITY"] = prev
    check(flagged[1:] == ["--saif", str(saif_path)], f"existing SAIF is passed through, got {flagged}")

    insts = [
        {"name": "_20803_", "x": 100.0, "y": 0.0, "seq": False, "filler": False},
        {"name": "_20800_", "x": 200.0, "y": 0.0, "seq": False, "filler": False},
    ]
    currents = {
        "ITermNode_metal1_100_0": 1e-3,
        "ITermNode_metal1_200_0": 1e-3,
    }
    idx = {"ITermNode_metal1_100_0": 0, "ITermNode_metal1_200_0": 1}
    base = plan_events(
        currents,
        idx,
        insts,
        mode="clock",
        peak_factor=8,
        leak_frac=0.2,
        period_s=0.82e-9,
        dur_s=0.08e-9,
        t50_s=0.12e-9,
    )
    saif = parse_saif(saif_path)
    idle = plan_events(
        currents,
        idx,
        insts,
        mode="clock",
        peak_factor=8,
        leak_frac=0.2,
        period_s=0.82e-9,
        dur_s=0.08e-9,
        t50_s=0.12e-9,
        saif=saif,
    )
    by_inst = {e.get("inst"): e for e in idle}
    check(by_inst["_20803_"]["i_pulse"] == 0.0 and by_inst["_20803_"].get("saif_idle") is True,
          "SAIF TC=0 idle-zeros the matched pulse")
    check(by_inst["_20800_"]["i_pulse"] == base[1]["i_pulse"] and by_inst["_20800_"].get("saif_idle") is False,
          "SAIF TC>0 keeps the existing triangle — does not invent t50 or rescale I_avg")
    check(by_inst["_20803_"]["t50_via"] == "synthetic", "SAIF never invents t50")

    vcd = parse_vcd(vcd_path)
    ev_v = plan_events(
        {"ITermNode_metal1_100_0": 1e-3},
        {"ITermNode_metal1_100_0": 0},
        [{"name": "_479_", "x": 100.0, "y": 0.0, "seq": False, "filler": False}],
        mode="clock",
        peak_factor=8,
        leak_frac=0.2,
        period_s=0.82e-9,
        dur_s=0.08e-9,
        t50_s=0.12e-9,
        vcd=vcd,
    )
    check(ev_v[0]["t50_via"] == "vcd_name_join", "VCD name-join overwrites t50")
    check(abs(ev_v[0]["t50_s"] - 250e-12) < 1e-18, "VCD first edge 250 ps")

    miss = plan_events(
        currents,
        idx,
        insts,
        mode="clock",
        peak_factor=8,
        leak_frac=0.2,
        period_s=0.82e-9,
        dur_s=0.08e-9,
        t50_s=0.12e-9,
        vcd=None,
        saif=None,
    )
    check(all(e["t50_via"] == "synthetic" for e in miss), "missing waveform leaves synthetic I(t)")

    if FAILS:
        print(f"{len(FAILS)} FAILED")
        return 1
    print("ALL test_activity_it PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
