#!/usr/bin/env python3
"""Layer contracts: CCS interpolator is real; NLDM is never mapped to CCS."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from pdn_activity import (  # noqa: E402
    apply_saif_activity,
    apply_sta_t50,
    expand_windows,
    load_sta_arrivals,
    load_sta_path,
    nearest_inst,
    parse_saif,
    parse_vcd,
    plan_events,
    probe_activity_trace,
    shift_events_to_window,
    t50_via_counts,
    windows_from_itot,
)
from pdn_current import (  # noqa: E402
    SYNTHETIC_CCS_LIB,
    SYNTHETIC_ECSM_LIB,
    current_source_for_event,
    interpolate_ccs_current,
    interpolate_ecsm_current,
    parse_ccs_output_current,
    parse_ecsm_waveforms,
    probe_liberty_current_model,
    triangle_above_leak,
    events_use_ccs,
    events_use_ecsm,
)


def check(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"FAIL {msg}")
    print(f"ok  {msg}")


def main() -> int:
    tri = triangle_above_leak(0.1, 0.1, 0.2, 1.0)
    check(abs(tri - 1.0) < 1e-12, "triangle peak")
    check(triangle_above_leak(0.0, 0.1, 0.2, 1.0) == 0.0, "triangle outside")

    nldm = probe_liberty_current_model(None)
    check(nldm["status"] == "GAP" and nldm["n_ccs_tables"] == 0, "missing liberty is GAP")

    with tempfile.NamedTemporaryFile("w", suffix=".lib", delete=False) as f:
        f.write(
            """
library (nldm_only) {
  cell (INV) {
    pin (ZN) { direction : output;
      timing () { cell_rise (t) { values ("0.01"); } rise_transition (t) { values ("0.02"); } }
    }
  }
}
"""
        )
        nldm_path = Path(f.name)
    probe = probe_liberty_current_model(nldm_path)
    nldm_path.unlink()
    check(probe["kind"] == "nldm" and probe["status"] == "GAP", "NLDM is GAP not fake CCS")
    check(probe["n_ccs_tables"] == 0, "NLDM yields zero CCS tables")
    check(probe.get("n_ecsm_tables", 0) == 0, "NLDM yields zero ECSM tables")

    tables = parse_ccs_output_current(SYNTHETIC_CCS_LIB)
    check(len(tables) == 1 and tables[0]["direction"] == "fall", "parse synthetic CCS")
    i00 = interpolate_ccs_current(tables[0], 0.01, 0.0)
    check(abs(i00 - 1e-3) < 1e-15, "CCS corner (slew0, v0)")
    imid = interpolate_ccs_current(tables[0], 0.03, 0.55)
    check(abs(imid - 3e-3) < 1e-12, "CCS bilinear mid")

    with tempfile.NamedTemporaryFile("w", suffix=".lib", delete=False) as f:
        f.write(SYNTHETIC_CCS_LIB)
        ccs_path = Path(f.name)
    ccs = probe_liberty_current_model(ccs_path)
    ccs_path.unlink()
    check(ccs["status"] == "READY" and ccs["n_ccs_tables"] == 1, "synthetic CCS probe READY")

    ev_tri = {"t50_s": 0.1, "dur_s": 0.2, "i_pulse": 5e-3}
    check(
        abs(current_source_for_event(ev_tri, 0.1) - 5e-3) < 1e-15,
        "event without slew uses triangle",
    )
    ev_ccs = {**ev_tri, "slew_s": 0.01, "vout": 0.0, "direction": "fall"}
    check(
        abs(current_source_for_event(ev_ccs, 0.1, ccs_tables=tables) - 1e-3) < 1e-15,
        "event with slew+vout uses CCS table",
    )
    check(
        current_source_for_event(ev_ccs, 0.0, ccs_tables=tables) == 0.0,
        "CCS current is zero outside the event window",
    )

    wfs = parse_ecsm_waveforms(SYNTHETIC_ECSM_LIB)
    check(len(wfs) == 1 and wfs[0]["direction"] == "fall", "parse synthetic ECSM waveform")
    i_ec = interpolate_ecsm_current(wfs[0], 0.02, 1e-12)
    check(abs(i_ec - 1e-12 * 0.55 / 0.04) < 1e-18, "ECSM |C dV/dt| on first segment")
    check(interpolate_ecsm_current(wfs[0], -0.01, 1e-12) == 0.0, "ECSM zero before waveform")
    with tempfile.NamedTemporaryFile("w", suffix=".lib", delete=False) as f:
        f.write(SYNTHETIC_ECSM_LIB)
        ecsm_path = Path(f.name)
    ecsm_p = probe_liberty_current_model(ecsm_path)
    ecsm_path.unlink()
    check(ecsm_p["status"] == "READY" and ecsm_p["kind"] == "ecsm_waveform", "synthetic ECSM probe READY")
    check(ecsm_p["n_ecsm_tables"] == 1 and ecsm_p["n_ccs_tables"] == 0, "ECSM is not counted as CCS")
    ev_ec = {"t50_s": 0.04, "dur_s": 0.08, "i_pulse": 5e-3, "c_load": 1e-12, "direction": "fall"}
    check(
        abs(current_source_for_event(ev_ec, 0.02, ecsm_tables=wfs) - 1e-12 * 0.55 / 0.04) < 1e-18,
        "event with c_load uses ECSM |C dV/dt|",
    )
    check(
        abs(current_source_for_event(ev_ec, 0.02) - triangle_above_leak(0.02, 0.04, 0.08, 5e-3)) < 1e-18,
        "without ECSM tables the same event stays triangle (no NLDM→ECSM)",
    )
    check(events_use_ecsm([ev_ec], wfs), "ECSM tables + c_load ⇒ TRAN must skip native triangle")
    check(not events_use_ecsm([{"t50_s": 0.1, "i_pulse": 1e-3}], wfs), "no c_load ⇒ ECSM stays out of the TRAN loop")

    act = probe_activity_trace(None)
    check(act["status"] == "GAP", "missing VCD is GAP")
    ev = plan_events(
        {"n1": 1e-3},
        {"n1": 0},
        [],
        mode="simultaneous",
        peak_factor=8,
        leak_frac=0.2,
        period_s=0.46e-9,
        dur_s=0.08e-9,
        t50_s=0.12e-9,
    )
    check(len(ev) == 1 and math.isclose(ev[0]["t50_s"], 0.12e-9), "synthetic simultaneous t50")
    check(ev[0]["t50_via"] == "synthetic", "no STA → synthetic t50_via")

    from export_sta_arrivals import parse_arrival_log

    arr_log = """PIN _479_/ZN activity=0.0 duty=0.5 origin=propagated
  (core_clock ^) r 0.1104:0.1104 f 0.117:0.117
PIN ctrl.state.out\\[0\\]$_DFF_P_/QN activity=0.0 duty=0.5 origin=propagated
  (core_clock ^) r 0.150:0.150 f ---:---
STA_ARRIVALS_DONE n=2
"""
    pins = parse_arrival_log(arr_log)
    check(len(pins) == 2, "parse_arrival_log two PIN rows")
    check(abs(pins[0]["rise_ns"] - 0.1104) < 1e-12, "rise max of min:max")
    check(pins[1]["inst_key"] == "ctrl.state.out[0]$_DFF_P_", "Verilog backslash stripped")
    check(pins[1]["fall_ns"] is None, "--- fall is missing not zero")

    sta_ev = [{"inst": "_479_", "t50_s": 0.12e-9, "dur_s": 0.08e-9}]
    sta_meta = apply_sta_t50(
        sta_ev, {"_479_": {"rise_ns": 0.11, "fall_ns": 0.12, "full": "_479_/ZN"}}, 0.46e-9
    )
    check(sta_meta["status"] == "READY" and sta_meta["n_applied"] == 1, "apply_sta_t50 READY")
    check(abs(sta_ev[0]["t50_s"] - 0.11e-9) < 1e-18, "STA rise overwrites synthetic t50")
    check(sta_ev[0]["t50_via"] == "sta_arrival", "t50_via sta_arrival")

    insts_sta = [
        {"name": "_479_", "x": 100.0, "y": 0.0, "seq": False, "cell": "AND2_X1", "filler": False}
    ]
    ev_clk = plan_events(
        {"ITermNode_metal1_100_0": 1e-3},
        {"ITermNode_metal1_100_0": 0},
        insts_sta,
        mode="clock",
        peak_factor=8,
        leak_frac=0.2,
        period_s=0.46e-9,
        dur_s=0.08e-9,
        t50_s=0.12e-9,
        sta_arrivals={"_479_": {"rise_ns": 0.20, "full": "_479_/ZN"}},
    )
    check(ev_clk[0]["t50_via"] == "sta_arrival", "plan_events clock applies STA")
    check(abs(ev_clk[0]["t50_s"] - 0.20e-9) < 1e-15, "clock STA t50 is rise arrival")

    from pdn_extract import parse_pg_sinks, pair_pg_rails, remap_events_to_rail, extract_pdn

    spice_dir = Path(tempfile.mkdtemp(prefix="dpn_vss_"))
    vdd_sp = spice_dir / "vdd.sp"
    vss_sp = spice_dir / "vss.sp"
    vdd_sp.write_text(
        """* Netlist for VDD
R0 ITermNode_metal1_0_0 Node_pad_vdd R=1.0
R1 ITermNode_metal1_100_0 Node_pad_vdd R=1.0
R2 ITermNode_metal1_200_0 Node_pad_vdd R=1.0
V0 Node_pad_vdd 0 DC 1.1
* Sinks
* Sink for _479_/VDD
I0 ITermNode_metal1_0_0 0 DC 1.0e-3
* Sink for _480_/VDD
I1 ITermNode_metal1_100_0 0 DC 2.0e-3
* Sink for _orphan_/VDD
I2 ITermNode_metal1_200_0 0 DC 1.0e-6
"""
    )
    vss_sp.write_text(
        """* Netlist for VSS
R0 ITermNode_metal1_0_1 Node_pad_vss R=1.0
R1 ITermNode_metal1_100_1 Node_pad_vss R=1.0
V0 Node_pad_vss 0 DC 0
* Sinks
* Sink for _479_/VSS
I0 ITermNode_metal1_0_1 0 DC 1.0e-3
* Sink for _480_/VSS
I1 ITermNode_metal1_100_1 0 DC 2.0e-3
"""
    )
    vdd_sinks = parse_pg_sinks(vdd_sp)
    vss_sinks = parse_pg_sinks(vss_sp)
    check(len(vdd_sinks) == 3 and vdd_sinks["ITermNode_metal1_0_0"]["inst"] == "_479_", "parse VDD Sink-for")
    check(vss_sinks["ITermNode_metal1_0_1"]["pin"].upper() == "VSS", "parse VSS Sink-for")
    paired = pair_pg_rails(vdd_sinks, vss_sinks)
    check(paired["status"] == "READY" and paired["n_pairs"] == 2, "pair by instance, skip orphan")
    vdd_idx = {"ITermNode_metal1_0_0": 0, "ITermNode_metal1_100_0": 1, "Node_pad_vdd": 2}
    vss_idx = {"ITermNode_metal1_0_1": 10, "ITermNode_metal1_100_1": 11, "Node_pad_vss": 12}
    remapped = remap_events_to_rail(
        [{"idx": 0, "t50_s": 0.1e-9}, {"idx": 1, "t50_s": 0.2e-9}, {"idx": 2, "t50_s": 0.0}],
        vdd_idx,
        vss_idx,
        paired["pairs"],
    )
    check(len(remapped) == 2 and remapped[0]["idx"] == 10 and remapped[1]["idx"] == 11, "remap VDD idx → VSS idx")
    check(all(r.get("rail") == "VSS" for r in remapped), "remapped events tagged VSS")

    from pdn_transient import build_system
    from pdn_dynamic import run_return_rail

    ext_vdd = extract_pdn(vdd_sp)
    _ord, idx_vdd, _G = build_system(ext_vdd["resistors"], ext_vdd["currents"], ext_vdd["voltages"])
    vss_run = run_return_rail(
        vdd_sp,
        vss_sp,
        [
            {
                "idx": idx_vdd["ITermNode_metal1_0_0"],
                "t50_s": 0.2e-9,
                "dur_s": 0.2e-9,
                "i_pulse": 5e-3,
                "i_leak": 0.0,
            },
            {
                "idx": idx_vdd["ITermNode_metal1_100_0"],
                "t50_s": 0.2e-9,
                "dur_s": 0.2e-9,
                "i_pulse": 5e-3,
                "i_leak": 0.0,
            },
        ],
        idx_vdd,
        pkg_r=0.05,
        pkg_l=0.0,
        c_decap=50e-15,
        dt=10e-12,
        t_end=0.4e-9,
        lef=None,
        spef=None,
    )
    check(vss_run["status"] == "READY" and vss_run["n_pairs"] == 2, "VSS return TRAN pairs")
    check(vss_run["n_events"] == 2, "orphan VDD sink is not remapped")
    check(vss_run["worst_bounce_mv"] > 0.0, "VSS bounce is -Vmin > 0")
    print(
        f"    VSS return bounce={vss_run['worst_bounce_mv']:.4f} mV "
        f"pairs={vss_run['n_pairs']} backend={vss_run.get('backend')}"
    )

    ev_sp = plan_events(
        {"ITermNode_metal1_100_0": 1e-3},
        {"ITermNode_metal1_100_0": 0},
        insts_sta,
        mode="spatial",
        peak_factor=8,
        leak_frac=0.2,
        period_s=0.46e-9,
        dur_s=0.08e-9,
        t50_s=0.12e-9,
        sta_arrivals={"_479_": {"rise_ns": 0.20, "full": "_479_/ZN"}},
    )
    check(ev_sp[0]["t50_via"] == "synthetic", "spatial ranking stays synthetic (no STA)")

    vcd_txt = """$date
now
$end
$timescale 1ps $end
$scope module _479_ $end
$var wire 1 ! ZN $end
$upscope $end
$enddefinitions $end
$dumpvars
0!
$end
#250
1!
"""
    vcd_path = Path(tempfile.mkdtemp(prefix="vcd-join-")) / "gate.vcd"
    vcd_path.write_text(vcd_txt)
    probe_ok = probe_activity_trace(vcd_path, insts_sta)
    check(probe_ok["status"] == "READY" and probe_ok["n_matched"] >= 1, "synthetic VCD name-join READY")
    parsed = parse_vcd(vcd_path)
    ev_v = plan_events(
        {"ITermNode_metal1_100_0": 1e-3},
        {"ITermNode_metal1_100_0": 0},
        insts_sta,
        mode="clock",
        peak_factor=8,
        leak_frac=0.2,
        period_s=0.46e-9,
        dur_s=0.08e-9,
        t50_s=0.12e-9,
        vcd=parsed,
    )
    check(ev_v[0]["t50_via"] == "vcd_name_join", "VCD name-join overwrites t50")
    check(abs(ev_v[0]["t50_s"] - 250e-12) < 1e-18, "VCD first edge 250 ps")

    gcd_vcd = Path(__file__).resolve().parents[2] / "learn/sim/gcd/gcd.vcd"
    if gcd_vcd.is_file():
        gap = probe_activity_trace(
            gcd_vcd,
            [
                {"name": "_479_"},
                {"name": r"ctrl.state.out[0]$_DFF_P_"},
                {"name": r"ctrl.state.out\[0\]$_DFF_P_"},
            ],
        )
        check(gap["status"] == "GAP" and (gap.get("n_matched") or 0) == 0, "GCD RTL VCD does not join gate insts")
    else:
        print("    skip GCD VCD (missing learn/sim/gcd/gcd.vcd)")

    tmp_sta = Path(tempfile.mkdtemp(prefix="sta-json-")) / "arr.json"
    tmp_sta.write_text(
        '{"by_inst": {"_479_": {"rise_ns": 0.09, "fall_ns": 0.10, "full": "_479_/ZN"}}}\n'
    )
    loaded = load_sta_arrivals(tmp_sta)
    check("_479_" in loaded and loaded["_479_"]["rise_ns"] == 0.09, "load_sta_arrivals by_inst")
    check(t50_via_counts(ev_clk)["sta_arrival"] == 1, "t50_via_counts")

    from export_sta_arrivals import parse_sta_path_report

    path_dump = """STA_PATH_BEGIN
Startpoint: ff1
Endpoint: ff2
      Delay        Time   Description
-----------------------------------------------------------------
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
    wp = parse_sta_path_report(path_dump)
    check(wp is not None, "parse_sta_path_report finds a path")
    check(wp["startpoint"] == "ff1" and wp["endpoint"] == "ff2", "path start/end")
    check(abs(wp["slack_ns"] - 0.0235) < 1e-12, "slack from indented slack (MET) line")
    check(wp["n_gates"] == 2, f"two gate stages (Q, ZN), got {wp['n_gates']}")
    check(abs(wp["gate_delay_ns"] - 0.15) < 1e-12, "gate delay 0.10+0.05")
    check(all("/CK" not in (s.get("pin") or "") for s in wp["stages"] if s["kind"] == "gate"), "CK is net not gate")
    check(not any(s["inst"] == "ff2" and s["pin"] == "CK" for s in wp["stages"]), "required-time CK excluded")

    from pdn_dynamic import path_ir_timing

    vdd_p, alpha_p = 1.1, 1.3
    Vw_p = [0.9, 1.1]
    ev_path = [{"inst": "ff1", "idx": 0}, {"inst": "other", "idx": 1}]
    tir = path_ir_timing(wp, ev_path, Vw_p, vdd_p, 0.46, alpha=alpha_p)
    check(tir["status"] == "READY", "path IR READY when a gate joins")
    check(tir["path"]["n_joined"] == 1, "only ff1 joins")
    d_ff = 0.1 * (vdd_p / 0.9) ** alpha_p
    d_g2 = 0.05  # unjoined stays at Vdd
    expect_deg_ps = (d_ff + d_g2 - 0.15) * 1e3
    check(abs(tir["degradation_ps"] - expect_deg_ps) < 1e-9, f"gate delay scaled at V=0.9 ({tir['degradation_ps']})")
    check(abs(tir["path"]["slack_ir_ns"] - (0.0235 - (d_ff + d_g2 - 0.15))) < 1e-12, "IR slack = STA slack − extra gate delay")
    tap_only = path_ir_timing(None, ev_path, Vw_p, vdd_p, 0.46)
    check(tap_only["status"] == "PARTIAL" and tap_only["path"]["status"] == "GAP", "no path → tap-scale PARTIAL")

    saif_txt = """(SAIFILE
(SAIFVERSION "2.0")
(DIRECTION "backward")
(TIMESCALE 1 ps)
(DURATION 10000)
(INSTANCE top
  (NET
    (req_val (T0 10000) (T1 0) (TC 99) (IG 0))
  )
  (INSTANCE _479_
    (NET
      (ZN (T0 4000) (T1 6000) (TC 4) (IG 0))
    )
  )
  (INSTANCE idle_buf
    (NET
      (Z (T0 10000) (T1 0) (TC 0) (IG 0))
    )
  )
)
)
"""
    saif_path = Path(tempfile.mkdtemp(prefix="saif-join-")) / "gate.saif"
    saif_path.write_text(saif_txt)
    insts_saif = [
        {"name": "_479_", "x": 100.0, "y": 0.0, "seq": False, "cell": "AND2_X1", "filler": False},
        {"name": "idle_buf", "x": 200.0, "y": 0.0, "seq": False, "cell": "BUF_X1", "filler": False},
        {"name": "ghost", "x": 300.0, "y": 0.0, "seq": False, "cell": "INV_X1", "filler": False},
    ]
    probe_saif = probe_activity_trace(saif_path, insts_saif)
    check(probe_saif["kind"] == "saif" and probe_saif["status"] == "READY", "SAIF probe READY")
    check(probe_saif["n_matched"] == 2, f"SAIF joins _479_ and idle_buf not ghost ({probe_saif['n_matched']})")
    parsed_saif = parse_saif(saif_path)
    check(parsed_saif["n_nets"] == 3, "SAIF three NET records (req_val + ZN + Z)")
    ev_saif = plan_events(
        {
            "ITermNode_metal1_100_0": 1e-3,
            "ITermNode_metal1_200_0": 1e-3,
            "ITermNode_metal1_300_0": 1e-3,
        },
        {
            "ITermNode_metal1_100_0": 0,
            "ITermNode_metal1_200_0": 1,
            "ITermNode_metal1_300_0": 2,
        },
        insts_saif,
        mode="clock",
        peak_factor=8,
        leak_frac=0.2,
        period_s=0.46e-9,
        dur_s=0.08e-9,
        t50_s=0.12e-9,
        sta_arrivals={"_479_": {"rise_ns": 0.20, "full": "_479_/ZN"}},
        saif=parsed_saif,
    )
    by_inst_ev = {e["inst"]: e for e in ev_saif}
    check(by_inst_ev["_479_"]["t50_via"] == "sta_arrival", "SAIF TC>0 keeps STA t50")
    check(abs(by_inst_ev["_479_"]["t50_s"] - 0.20e-9) < 1e-15, "SAIF does not invent t50")
    check(by_inst_ev["_479_"]["i_pulse"] > 0, "toggled SAIF keeps pulse")
    check(by_inst_ev["idle_buf"]["i_pulse"] == 0.0, "SAIF TC=0 idle-zeros pulse")
    check(by_inst_ev["idle_buf"]["t50_via"] == "synthetic", "idle SAIF does not invent t50")
    pulse_before = by_inst_ev["_479_"]["i_pulse"]
    check(by_inst_ev["ghost"].get("saif_tc") is None, "unrelated instance does not join SAIF")
    meta_saif = apply_saif_activity(
        [{"inst": "idle_buf", "i_pulse": 1e-3, "i_leak": 0.0, "i_peak": 1e-3, "t50_via": "synthetic"}],
        parsed_saif,
    )
    check(meta_saif["n_idle"] == 1, "apply_saif_activity idle count")

    ev_vcd_saif = plan_events(
        {"ITermNode_metal1_100_0": 1e-3},
        {"ITermNode_metal1_100_0": 0},
        insts_sta,
        mode="clock",
        peak_factor=8,
        leak_frac=0.2,
        period_s=0.46e-9,
        dur_s=0.08e-9,
        t50_s=0.12e-9,
        vcd=parsed,
        saif={"toggle_count": {"_479_": 0}},
    )
    check(ev_vcd_saif[0]["t50_via"] == "vcd_name_join", "VCD name-join wins over SAIF")
    check(ev_vcd_saif[0]["i_pulse"] > 0, "VCD-matched ITerm is not idle-zeroed by SAIF TC=0")
    check(abs(pulse_before - by_inst_ev["_479_"]["i_pulse"]) < 1e-18, "SAIF TC does not rescale I_avg/pulse")

    tmp_path_json = Path(tempfile.mkdtemp(prefix="sta-path-")) / "arr.json"
    tmp_path_json.write_text(json.dumps({"by_inst": {"_479_": {"rise_ns": 0.09}}, "worst_path": wp}) + "\n")
    check(load_sta_path(tmp_path_json)["n_gates"] == 2, "load_sta_path worst_path")
    check(load_sta_path(tmp_sta) is None, "arrivals without worst_path → None")

    near = nearest_inst(1100.0, 0.0, [{"name": "c", "x": 0.0, "y": 0.0, "seq": True, "filler": False}])
    check(near is not None and near["name"] == "c", "ITerm 1100 dbu from origin still joins")
    far = nearest_inst(9000.0, 0.0, [{"name": "c", "x": 0.0, "y": 0.0, "seq": True, "filler": False}])
    check(far is None, "far ITerm is not silently mapped")

    wins_m = windows_from_itot([0.0, 0.1, 0.2, 1.0, 1.1, 1.2], [0.0, 1.0, 0.0, 0.0, 1.0, 0.0], 0.5)
    check(len(wins_m) == 2, "two I_tot peaks → two windows")
    merged = expand_windows(wins_m, pad_s=0.05, t_end=1.2)
    check(len(merged) == 2, "padding does not merge isolated peaks")
    sh = shift_events_to_window(
        [{"t50_s": 0.1, "dur_s": 0.04, "idx": 0}, {"t50_s": 1.1, "dur_s": 0.04, "idx": 0}],
        1.0,
        1.2,
    )
    check(len(sh) == 1 and abs(sh[0]["t50_s"] - 0.1) < 1e-12, "shift_events_to_window")

    # 1-node descriptor RLC MOR vs Solver A hist (native or SciPy).
    if "/usr/lib/python3/dist-packages" not in sys.path:
        sys.path.insert(0, "/usr/lib/python3/dist-packages")
    import numpy as np
    from scipy import sparse
    from pdn_dynamic import assemble_be, timestep_be, windowed_timestep_be
    from pdn_solvers import DirectLU, RationalKrylov

    vdd, dt, t_end = 1.1, 10e-12, 0.4e-9
    G = sparse.csr_matrix((1, 1), dtype=np.float64)
    idx = {"n": 0}
    voltages = {"n": vdd}
    events = [
        {
            "idx": 0,
            "t50_s": 0.2e-9,
            "dur_s": 0.2e-9,
            "i_pulse": 5e-3,
            "i_leak": 0.0,
            "x": 0.0,
            "seq": True,
        }
    ]
    sys_be = assemble_be(
        G, idx, voltages, vdd, events, pkg_r=0.05, pkg_l=2e-10, c_decap=50e-12, dt=dt
    )
    gold = timestep_be(sys_be, events, DirectLU(sys_be["A"]), vdd, ["n"], t_end)
    starts = np.ones((1, 1), dtype=np.float64, order="F")
    shifts = np.array([0.0, 1e9, 1.0 / dt], dtype=np.float64)
    mor = RationalKrylov(sys_be["G_mesh"], sys_be["C"], starts, shifts, n_moments=4, sys=sys_be)
    red = mor.timestep(sys_be, events, vdd, t_end)
    err_mv = abs(gold["worst_droop"] - red["worst_droop"]) * 1e3
    check("rlc" in mor.name, f"MOR name is RLC ({mor.name})")
    check(err_mv < 1.0, f"1-node Python RLC MOR vs hist |A−C|={err_mv:.4f} mV")
    print(f"    python RLC MOR m={mor.m} backend={mor.backend} |A-C|={err_mv:.4e} mV")

    vdd_w, dt_w, t_end_w = 1.1, 10e-12, 2.0e-9
    G_w = sparse.csr_matrix((1, 1), dtype=np.float64)
    ev_iso = [
        {
            "idx": 0,
            "t50_s": 0.2e-9,
            "dur_s": 0.1e-9,
            "i_pulse": 5e-3,
            "i_leak": 0.0,
            "x": 0.0,
            "seq": True,
        },
        {
            "idx": 0,
            "t50_s": 1.5e-9,
            "dur_s": 0.1e-9,
            "i_pulse": 5e-3,
            "i_leak": 0.0,
            "x": 0.0,
            "seq": True,
        },
    ]
    sys_w = assemble_be(
        G_w, {"n": 0}, {"n": vdd_w}, vdd_w, ev_iso, pkg_r=2.0, pkg_l=0.0, c_decap=50e-12, dt=dt_w
    )
    gold_w = timestep_be(sys_w, ev_iso, DirectLU(sys_w["A"]), vdd_w, ["n"], t_end_w)
    win_w = windowed_timestep_be(
        sys_w,
        ev_iso,
        DirectLU(sys_w["A"]),
        vdd_w,
        ["n"],
        t_end_w,
        gold_w["wave_t"],
        gold_w["wave_itot"],
        gold_w,
    )
    check(win_w.get("isolated") is True, "L=0 isolated windows")
    check((win_w.get("n_windows") or 0) >= 2, f"two isolated pulses → n_windows={win_w.get('n_windows')}")
    check(int(win_w.get("steps") or 0) < int(gold_w["steps"]), "windowed BE uses fewer steps than full TRAN")
    check(
        (win_w.get("abs_err_vs_A_mv") or 99) < 0.5,
        f"windowed vs full |A−W|={win_w.get('abs_err_vs_A_mv')} mV",
    )
    print(
        f"    windowed RC steps {win_w.get('steps')}/{gold_w['steps']} "
        f"|A−W|={win_w.get('abs_err_vs_A_mv'):.4e} mV nwin={win_w.get('n_windows')}"
    )

    from pdn_vrm import compact_vrm_die, ngspice_vrm_die_gold, timestep_descriptor

    n4 = ngspice_vrm_die_gold(
        vdd=1.1,
        r_vrm=0.015,
        l_vrm=2e-10,
        c_vrm=50e-12,
        r_pkg=0.05,
        l_pkg=2e-10,
        c_die=50e-12,
        i_peak=5e-3,
        t50=0.2e-9,
        dur=0.2e-9,
        dt=10e-12,
        t_end=0.4e-9,
    )
    check(n4.get("ok") is True, f"N4 compact vs ngspice ({n4})")
    print(f"    N4 compact |BE−ng|={n4.get('abs_err_mv'):.4f} mV droop={n4.get('be_droop_mv'):.3f} mV")

    from pdn_solvers import RASDD, BicgSTAB, native_index_width

    widx = native_index_width()
    if widx is None:
        print("    skip native Index width (no libdpn)")
    else:
        check(widx == 64, f"native Index width is 64 (got {widx})")

    n_poi = 200
    A_poi = sparse.diags(
        [-np.ones(n_poi - 1), 2 * np.ones(n_poi), -np.ones(n_poi - 1)],
        [-1, 0, 1],
        shape=(n_poi, n_poi),
        format="csr",
    )
    b_poi = np.ones(n_poi, dtype=np.float64)
    xa = DirectLU(A_poi).solve(b_poi)
    ras = RASDD(A_poi)
    xd = ras.solve(b_poi)
    err_ras = float(np.max(np.abs(xa - xd)))
    check(ras.n_levels >= 2, f"RAS multi-domain n=200 ndom={ras.n_levels}")
    check(err_ras < 1e-6, f"RAS vs LU poisson n=200 max|A-D|={err_ras:.3e}")
    print(f"    RAS poisson ndom={ras.n_levels} backend={ras.backend} max|A-D|={err_ras:.3e}")

    bicg = BicgSTAB(A_poi)
    xe = bicg.solve(b_poi)
    err_bicg = float(np.max(np.abs(xa - xe)))
    check(err_bicg < 1e-6, f"BiCGSTAB vs LU poisson n=200 max|A-E|={err_bicg:.3e}")
    print(f"    BiCGSTAB poisson backend={bicg.backend} max|A-E|={err_bicg:.3e} name={bicg.name}")

    # Lagged CCS I(slew, V^n) on 1-node RC vs ngspice implicit B-source.
    from shutil import which
    from pdn_current import events_use_ccs

    vdd, r, c, dt, t_end = 1.1, 2.0, 50e-12, 10e-12, 0.8e-9
    t50, dur, slew = 0.2e-9, 0.2e-9, 0.01
    ev_iv = {
        "idx": 0,
        "t50_s": t50,
        "dur_s": dur,
        "i_pulse": 0.0,
        "i_leak": 0.0,
        "slew_s": slew,
        "direction": "fall",
        "x": 0.0,
        "seq": True,
    }
    check(events_use_ccs([ev_iv], tables), "slew+tables ⇒ CCS in the TRAN loop")
    G0 = sparse.csr_matrix((1, 1), dtype=np.float64)
    sys_ccs = assemble_be(
        G0, {"n": 0}, {"n": vdd}, vdd, [ev_iv], pkg_r=r, pkg_l=0.0, c_decap=c, dt=dt
    )
    ccs_run = timestep_be(sys_ccs, [ev_iv], DirectLU(sys_ccs["A"]), vdd, ["n"], t_end, ccs_tables=tables)
    check(ccs_run.get("ccs_in_loop") is True, "timestep_be reports ccs_in_loop")
    check(str(ccs_run.get("timestep_loop", "")).startswith("python_ccs"), "CCS skips native triangle loop")
    print(
        f"    CCS lagged BE droop={ccs_run['worst_droop']*1e3:.4f} mV loop={ccs_run['timestep_loop']}"
    )

    if which("ngspice"):
        t0w = t50 - 0.5 * dur
        t1w = t50 + 0.5 * dur
        tmp = Path(tempfile.mkdtemp(prefix="ccs-iv-"))
        sp = tmp / "ccs.sp"
        dat = tmp / "ccs.dat"
        # slew=0.01 table is I = 1e-3 + V/550 (linear in Vout).
        sp.write_text(
            f"""* lagged CCS I(V) gold — B-source is implicit; BE uses V^n
Vpad pad 0 DC {vdd}
R1 pad n {r}
C1 n 0 {c}
B1 n 0 I = {{ (time > {t0w:.12e}) && (time < {t1w:.12e}) ? (1.0e-3 + v(n)/550.0) : 0 }}
.control
option method=gear maxord=1
set filetype=ascii
tran {dt:.6e} {t_end:.6e}
wrdata {dat} v(n)
quit
.endc
.end
"""
        )
        subprocess.run(["ngspice", "-b", str(sp)], capture_output=True, text=True, timeout=30)
        vmin_ng = None
        for extra in [dat, *sorted(tmp.glob("ccs.dat*"))]:
            if not extra.is_file():
                continue
            xs = []
            for line in extra.read_text().splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        xs.append(float(parts[1]))
                    except ValueError:
                        continue
            if xs:
                vmin_ng = min(xs)
                break
        check(vmin_ng is not None, "ngspice CCS wrdata")
        err_ccs = abs(ccs_run["worst_voltage"] - vmin_ng) * 1e3
        check(err_ccs < 5.0, f"CCS lagged BE vs ngspice B-source |err|={err_ccs:.4f} mV")
        print(f"    CCS |BE−ng|={err_ccs:.4f} mV ng_vmin={vmin_ng:.6f} be_vmin={ccs_run['worst_voltage']:.6f}")
    else:
        print("    skip CCS ngspice (no ngspice)")

    _ROOT = Path(__file__).resolve().parents[2]
    lef = (
        _ROOT
        / "tools"
        / "OpenROAD-flow-scripts"
        / "flow"
        / "platforms"
        / "nangate45"
        / "lef"
        / "NangateOpenCellLibrary.tech.lef"
    )
    from pdn_extract import extract_pdn, parse_spice, parse_tech_lef, probe_spef, stamp_spef_pg_c
    from pdn_em import em_thermal_snapshot

    tech = parse_tech_lef(lef)
    check(tech["status"] == "READY", f"tech LEF READY ({tech.get('path')})")
    m1 = (tech.get("layers") or {}).get("metal1") or {}
    check(abs(float(m1.get("width_um", 0)) - 0.07) < 1e-12, "metal1 WIDTH 0.07 µm (not SPACINGTABLE)")
    check(abs(float(m1.get("rpersq", 0)) - 0.38) < 1e-12, "metal1 RPERSQ 0.38")
    check(abs(float(m1.get("thickness_um", 0)) - 0.13) < 1e-12, "metal1 THICKNESS 0.13 µm")
    check(abs(float(m1.get("height_um", 0)) - 0.37) < 1e-12, "metal1 HEIGHT 0.37 µm")
    v1 = (tech.get("cuts") or {}).get("via1") or {}
    check(abs(float(v1.get("width_um", 0)) - 0.07) < 1e-12, "via1 CUT WIDTH 0.07 µm")
    check(abs(float(v1.get("r_ohm", 0)) - 5.0) < 1e-12, "via1 CUT R 5 Ω")

    spef_path = (
        _ROOT
        / "tools"
        / "OpenROAD-flow-scripts"
        / "flow"
        / "results"
        / "nangate45"
        / "gcd"
        / "flowlab"
        / "6_final.spef"
    )
    spef = probe_spef(spef_path if spef_path.is_file() else None)
    check(spef["status"] == "GAP", "SPEF PDN C stays GAP (never stamped)")
    check(not spef.get("has_pg_net"), "GCD signal SPEF has no VDD net")

    tmp_sp = Path(tempfile.mkdtemp(prefix="extract-")) / "mesh.sp"
    tmp_sp.write_text(
        "R0 p1 ITermNode_metal1_0_0 R=0.05\n"
        "R1 ITermNode_metal1_0_0 ITermNode_metal1_2000_0 R=0.38\n"
        "I0 ITermNode_metal1_2000_0 0 DC 0.001\n"
        "V0 p1 0 DC 1.1\n"
    )
    ext = extract_pdn(tmp_sp, lef=lef, spef=spef_path if spef_path.is_file() else None)
    check(ext["backend"] == "write_pg_spice", "extract backend write_pg_spice")
    check(ext["spef"]["status"] == "GAP", "extract SPEF status GAP")
    check(ext["n_r"] == 2, "extract two resistors")

    syn_spef = Path(tempfile.mkdtemp(prefix="spef-pg-")) / "vdd.spef"
    syn_spef.write_text(
        '*SPEF "ieee 1481-1999"\n'
        "*C_UNIT 1 PF\n"
        "*D_NET VDD 0.002\n"
        "*CONN\n"
        "*CAP\n"
        "1 ITermNode_metal1_0_0 0.001\n"
        "2 ITermNode_metal1_2000_0 0.001\n"
        "3 ITermNode_metal1_0_0 ITermNode_metal1_2000_0 0.0004\n"
        "*END\n"
        "*D_NET req_val 9.0\n"
        "*CAP\n"
        "1 ITermNode_metal1_0_0 9.0\n"
        "*END\n"
    )
    from pdn_transient import build_system

    stamped = stamp_spef_pg_c(
        syn_spef, {"ITermNode_metal1_0_0", "ITermNode_metal1_2000_0", "p1"}
    )
    check(stamped["status"] == "READY", "synthetic PG SPEF stamps READY")
    check(stamped["n_stamped"] == 2, "two PDN nodes received PG C")
    check(abs(stamped["node_c"]["ITermNode_metal1_0_0"] - 0.0012e-12) < 1e-24, "grounded + half coupling on node 0")
    check(abs(stamped["node_c"]["ITermNode_metal1_2000_0"] - 0.0012e-12) < 1e-24, "grounded + half coupling on node 1")
    check(stamped["n_pg_net"] == 1, "only VDD counts as PG *D_NET")
    check(abs(stamped["c_sum_f"] - 0.0024e-12) < 1e-24, "signal *D_NET C is not in the sum")
    ext_pg = extract_pdn(tmp_sp, lef=lef, spef=syn_spef)
    check(ext_pg["spef"]["status"] == "READY", "extract_pdn READY when C is stamped")
    _, idx_be, G_be = build_system(ext_pg["resistors"], ext_pg["currents"], ext_pg["voltages"])
    ev_be = [{"idx": idx_be["ITermNode_metal1_2000_0"], "i_leak": 0.0}]
    sys_lumped = assemble_be(
        G_be, idx_be, ext_pg["voltages"], 1.1, ev_be, pkg_r=0.05, pkg_l=0.0, c_decap=50e-15, dt=10e-12
    )
    sys_pgc = assemble_be(
        G_be,
        idx_be,
        ext_pg["voltages"],
        1.1,
        ev_be,
        pkg_r=0.05,
        pkg_l=0.0,
        c_decap=50e-15,
        dt=10e-12,
        spef_c=ext_pg["spef"]["node_c"],
    )
    i0 = idx_be["ITermNode_metal1_0_0"]
    check(sys_pgc["C"][i0] > sys_lumped["C"][i0], "SPEF C is added to lumped c_decap, not a replacement")
    check(abs(sys_pgc["C"][i0] - sys_lumped["C"][i0] - 0.0012e-12) < 1e-24, "assemble_be adds stamped Farads")

    from pdn_em import grover_partial_L, grover_partial_M, estimate_on_die_L

    Lg = grover_partial_L(1e-6, 0.07e-6, 0.13e-6)
    check(abs(Lg - 5.6943e-13) / 5.6943e-13 < 1e-3, f"Grover 1 µm metal1 bar ({Lg:.4e} H)")
    Mg = grover_partial_M(1e-6, 0.2e-6)
    M_expect = 2e-7 * 1e-6 * (math.log(2.0 * 1e-6 / 0.2e-6) - 1.0 + 0.2e-6 / 1e-6)
    check(abs(Mg - M_expect) / M_expect < 1e-12, f"Grover partial M 1 µm / 0.2 µm ({Mg:.4e} H)")
    onl = estimate_on_die_L(
        [("ITermNode_metal1_0_0", "ITermNode_metal1_2000_0", 0.38)],
        tech,
    )
    check(onl["status"] == "READY" and onl["n_stamped"] == 1, "estimate_on_die_L READY on one strap")
    check(onl["L_max_h"] > 0, "Grover L_max > 0")
    check(onl["n_mutual"] == 0, "single strap has no mutual pair")
    two_par = estimate_on_die_L(
        [
            ("ITermNode_metal1_0_0", "ITermNode_metal1_2000_0", 0.38),
            ("ITermNode_metal1_0_400", "ITermNode_metal1_2000_400", 0.38),
        ],
        tech,
    )
    check(two_par["n_stamped"] == 2, "two parallel 1 µm straps")
    check(two_par["n_mutual"] == 1, f"parallel straps pair once (n_mutual={two_par['n_mutual']})")
    check(two_par["M_max_h"] > 0, "M_max > 0")
    via_r = estimate_on_die_L(
        [("ITermNode_metal1_0_0", "ITermNode_metal2_0_0", 1.0)],
        tech,
    )
    check(via_r["status"] == "GAP" and via_r["n_stamped"] == 0, "vias are not Grover-stamped")
    ext_l = extract_pdn(tmp_sp, lef=lef)
    check((ext_l.get("on_die_l") or {}).get("status") == "READY", "extract_pdn includes Grover L")
    gcd_sp = (
        _ROOT
        / "tools"
        / "OpenROAD-flow-scripts"
        / "flow"
        / "results"
        / "nangate45"
        / "gcd"
        / "flowlab"
        / "pdn"
        / "pg_vdd_bumps.sp"
    )
    if gcd_sp.is_file():
        gcd_l = estimate_on_die_L(parse_spice(gcd_sp)[0], tech)
        check(gcd_l["n_stamped"] > 1000, f"GCD Grover straps n={gcd_l['n_stamped']}")
        check("metal1" in (gcd_l.get("by_layer") or {}), "GCD metal1 straps have Grover L")
        check(gcd_l["n_mutual"] > 0, f"GCD cutoff mutual n={gcd_l['n_mutual']}")
        print(
            f"    GCD Grover n_stamped={gcd_l['n_stamped']} n_mutual={gcd_l['n_mutual']} "
            f"M_max={gcd_l['M_max_h']*1e12:.3f} pH"
        )
    else:
        print("    skip GCD Grover (no pg_vdd_bumps.sp)")

    from pdn_vrm import assemble_strap_rlc, ngspice_coupled_l_gold, ngspice_strap_rlc_gold, xyce_vrm_die_gold
    from pdn_transient import build_system as _bs
    from shutil import which as _which

    rs, ls = 0.38, 1e-12
    _, idx2, G2 = _bs([("n0", "n1", rs)], {"n1": 0.0}, {"n0": 1.1})
    C2 = np.array([50e-12, 50e-12])
    sys_st = assemble_strap_rlc(
        G2,
        C2,
        idx2,
        {"n0": 1.1},
        [{"a": "n0", "b": "n1", "r_ohm": rs, "L_h": ls}],
        pkg_r=0.05,
        pkg_l=2e-10,
        dt=10e-12,
        vdd=1.1,
        pad="inductor",
    )
    check(sys_st["n_straps"] == 1 and sys_st["iv"] == 2, "strap descriptor: 1 L + bump L")
    check(sys_st["A"].shape[0] == 4, "2 voltages + i_pkg + i_strap")
    check(sys_st.get("n_iv") == 1, "single-bump inductor pad n_iv=1")
    _, idx3, G3 = _bs(
        [("n0", "n1", rs), ("n2", "n1", rs)],
        {"n1": 0.0},
        {"n0": 1.1, "n2": 1.1},
    )
    sys_2p = assemble_strap_rlc(
        G3,
        np.array([50e-12, 50e-12, 50e-12]),
        idx3,
        {"n0": 1.1, "n2": 1.1},
        [{"a": "n0", "b": "n1", "r_ohm": rs, "L_h": ls}],
        pkg_r=0.05,
        pkg_l=2e-10,
        dt=10e-12,
        vdd=1.1,
        pad="inductor",
    )
    check(sys_2p.get("n_iv") == 2, f"two-bump inductor pad n_iv={sys_2p.get('n_iv')}")
    check(len(sys_2p.get("iv_list") or []) == 2, "iv_list has both bump KVL rows")
    if _which("ngspice"):
        gold_st = ngspice_strap_rlc_gold()
        check(gold_st.get("ok") is True, f"2-node Grover strap vs ngspice ({gold_st})")
        print(
            f"    strap RLC |BE−ng|={gold_st.get('abs_err_mv'):.4f} mV "
            f"backend={gold_st.get('backend')} droop={gold_st.get('be_droop_mv'):.3f} mV"
        )
        gold_k = ngspice_coupled_l_gold()
        check(gold_k.get("ok") is True, f"coupled straps vs ngspice K ({gold_k})")
        check(gold_k.get("n_mutual") == 1, "coupled gold stamps one M pair")
        print(
            f"    strap K |BE−ng|={gold_k.get('abs_err_mv'):.4f} mV "
            f"backend={gold_k.get('backend')} n_mutual={gold_k.get('n_mutual')}"
        )
    else:
        print("    skip strap RLC ngspice")
    xyce = xyce_vrm_die_gold()
    check(xyce.get("deck_ok") is True, f"Xyce N4 deck has R/L/C/PWL/.TRAN ({xyce})")
    if xyce.get("status") == "READY":
        check(xyce.get("ok") is True, f"Xyce N4 vs BE ({xyce})")
        print(f"    Xyce |BE−xy|={xyce.get('abs_err_mv'):.4f} mV")
    else:
        print(f"    Xyce GAP ({xyce.get('reason')}) — deck contract kept")

    # w = RPERSQ·L/R. L = 2000 dbu / 2000 dbu_per_um = 1 µm → w = 1 µm (not min WIDTH 0.07).
    order = ["ITermNode_metal1_0_0", "ITermNode_metal1_2000_0"]
    idx_em = {n: i for i, n in enumerate(order)}
    Vem = np.array([1.10, 1.09], dtype=np.float64)
    em = em_thermal_snapshot(
        [("ITermNode_metal1_0_0", "ITermNode_metal1_2000_0", 0.38)],
        idx_em,
        order,
        Vem,
        bump=[],
        bump_v=[],
        i_L=None,
        pkg_r=0.05,
        pkg_l=0.0,
        tech=tech,
    )
    check(em["status"] == "READY" and em["n_with_j"] == 1, "EM J READY on same-layer metal1")
    w_m = em["hottest_j"]["w_m"]
    check(abs(w_m - 1e-6) < 1e-12, f"w from RPERSQ·L/R = 1 µm, not min WIDTH ({w_m})")
    i_br = 0.01 / 0.38
    area = 1e-6 * 0.13e-6
    j_expect = i_br / area
    check(abs(em["j_absmax_a_m2"] - j_expect) / j_expect < 1e-9, "J = I/(w t)")
    check(not em["hottest_j"].get("w_clamped"), "wide inferred strap is not clamped")
    # Skinny inferred w from lumped via-ish R → clamp to min WIDTH 0.07 µm.
    em_c = em_thermal_snapshot(
        [("ITermNode_metal1_0_0", "ITermNode_metal1_330_0", 12.54)],
        {"ITermNode_metal1_0_0": 0, "ITermNode_metal1_330_0": 1},
        ["ITermNode_metal1_0_0", "ITermNode_metal1_330_0"],
        np.array([1.10, 1.09], dtype=np.float64),
        bump=[],
        bump_v=[],
        i_L=None,
        pkg_r=0.05,
        pkg_l=0.0,
        tech=tech,
    )
    em_c.pop("_scaled_resistors", None)
    check(em_c["hottest_j"]["w_clamped"] is True, "inferred w < min WIDTH is clamped")
    check(abs(em_c["hottest_j"]["w_m"] - 0.07e-6) < 1e-15, "clamped w equals metal1 min WIDTH")
    em.pop("_scaled_resistors", None)
    check((em.get("thermal_mesh") or {}).get("status") == "GAP", "no pads → thermal mesh GAP")
    print(
        f"    EM J={em['j_absmax_a_m2']:.4e} A/m² TTF_rel={em['ttf_rel_min']:.4e} "
        f"ΔT={em['dT_absmax_k']:.4e} K w/min={em['hottest_j'].get('w_over_min')}"
    )

    from pdn_em import (
        K_CU_W_M_K,
        RTH_PAD_K_PER_W,
        assemble_thermal_mesh,
        ngspice_thermal_1node_gold,
        rac_over_rdc,
        solve_thermal_steady,
        timestep_thermal_be,
        via_geometry,
    )

    em_m = em_thermal_snapshot(
        [("ITermNode_metal1_0_0", "ITermNode_metal1_2000_0", 0.38)],
        idx_em,
        order,
        Vem,
        bump=[0],
        bump_v=[1.1],
        i_L=None,
        pkg_r=0.05,
        pkg_l=0.0,
        tech=tech,
        f_hz=1.0 / 0.46e-9,
    )
    em_m.pop("_scaled_resistors", None)
    check((em_m.get("thermal_mesh") or {}).get("status") == "READY", "2-node thermal mesh READY with a pad")
    P = em_m["p_joule_w"]
    geo = em_m["hottest_j"]
    gth = K_CU_W_M_K * geo["area_m2"] / geo["L_m"]
    gamb = 1.0 / RTH_PAD_K_PER_W
    t1 = P / gamb + 0.5 * P / gth
    check(abs(em_m["dT_mesh_absmax_k"] - t1) / t1 < 1e-6, "2-node mesh ΔT vs G_th series (split I²R)")
    t0_gold = P / gamb
    t0 = float((em_m.get("thermal_mesh") or {}).get("dT_pad_max_k") or 0.0)
    check(abs(t0 - t0_gold) / t0_gold < 1e-6, "pad T0 = P/G_amb")
    check(t0 < em_m["dT_lumped_absmax_k"], "pad node cooler than isolated lumped Rth")
    # Far-node T1 can exceed lumped Rth when G_th ≪ G_lumped (tiny A/L). Not a spreading theorem.
    sk = em_m.get("skin") or {}
    check(sk.get("status") == "READY", "skin depth reported")
    check(sk["rac_rdc"] < 1.01, "Nangate metal1 t ≪ δ at GCD clock → Rac/Rdc≈1")
    check(abs(rac_over_rdc(0.13e-6, 1.0 / 0.46e-9) - sk["rac_rdc"]) < 1e-12, "skin helper matches snapshot")
    print(
        f"    thermal mesh ΔT={em_m['dT_mesh_absmax_k']:.4e} K lumped={em_m['dT_lumped_absmax_k']:.4e} K "
        f"pad={t0:.4e} K δ={sk['delta_m']*1e6:.2f} µm Rac/Rdc={sk['rac_rdc']:.4f}"
    )

    vg = via_geometry("ITermNode_metal1_0_0", "ITermNode_metal2_0_0", 5.0 / 3.0, tech)
    check(vg is not None and vg["kind"] == "via", "via_geometry on adjacent metals")
    L_via = (0.62 - 0.37 - 0.13) * 1e-6
    check(abs(vg["L_m"] - L_via) / L_via < 1e-12, "via L = HEIGHT_m2 − HEIGHT_m1 − t_m1")
    check(abs(vg["n_cuts"] - 3.0) < 1e-6, "n_cuts = R_cut/R = 5/(5/3) = 3")
    check(via_geometry("ITermNode_metal1_0_0", "ITermNode_metal3_0_0", 1.0, tech) is None, "non-adjacent via is GAP")

    order_v = ["ITermNode_metal1_0_0", "ITermNode_metal2_0_0"]
    idx_v = {n: i for i, n in enumerate(order_v)}
    r_via = 5.0 / 3.0
    Vvia = np.array([1.10, 1.09], dtype=np.float64)
    em_v = em_thermal_snapshot(
        [("ITermNode_metal1_0_0", "ITermNode_metal2_0_0", r_via)],
        idx_v,
        order_v,
        Vvia,
        bump=[1],
        bump_v=[1.1],
        i_L=None,
        pkg_r=0.05,
        pkg_l=0.0,
        tech=tech,
    )
    em_v.pop("_scaled_resistors", None)
    check((em_v.get("thermal_mesh") or {}).get("status") == "READY", "via-only mesh READY (pad on metal2)")
    check((em_v.get("thermal_mesh") or {}).get("n_vias") == 1, "one via thermal edge")
    Pv = em_v["p_joule_w"]
    gv = K_CU_W_M_K * vg["area_m2"] / vg["L_m"]
    t1_via = Pv / gamb + 0.5 * Pv / gv
    check(abs(em_v["dT_mesh_absmax_k"] - t1_via) / t1_via < 1e-6, "via mesh ΔT vs G_th series")
    print(f"    via mesh ΔT={em_v['dT_mesh_absmax_k']:.4e} K n_cuts={vg['n_cuts']:.2f} G_th={gv:.4e} W/K")

    th_gap = assemble_thermal_mesh(
        [("ITermNode_metal1_0_0", "ITermNode_metal1_2000_0", 0.38)],
        {"ITermNode_metal1_0_0": 0, "ITermNode_metal1_2000_0": 1, "ITermNode_metal7_0_0": 2},
        [2],
        tech,
    )
    check(th_gap is None, "strap with pad on another layer and no via → GAP (no invented island ambient)")

    gcd_sp = (
        _ROOT
        / "tools"
        / "OpenROAD-flow-scripts"
        / "flow"
        / "results"
        / "nangate45"
        / "gcd"
        / "flowlab"
        / "pdn"
        / "pg_vdd_bumps.sp"
    )
    if gcd_sp.is_file():
        from pdn_transient import build_system as _bs_th

        Rg, Ig, Vg = parse_spice(gcd_sp)
        order_g, idx_g, _Gg = _bs_th(Rg, Ig, Vg)
        pads_g = [idx_g[n] for n in Vg if n in idx_g]
        th_g = assemble_thermal_mesh(Rg, idx_g, pads_g, tech)
        check(th_g is not None, "GCD VDD thermal mesh is pad-reachable (vias couple layers)")
        check(th_g["n_vias"] > 0, f"GCD stamps via G_th (n_vias={th_g.get('n_vias')})")
        P_g = np.full(th_g["n"], 1e-8, dtype=np.float64)
        sol_g = solve_thermal_steady(th_g["G"], P_g)
        check(np.isfinite(sol_g["T"]).all(), "GCD thermal T finite")
        check(sol_g["rel_res"] < 1e-4, f"GCD thermal G_th rel_res={sol_g['rel_res']}")
        print(
            f"    GCD thermal n={th_g['n']} straps={th_g['n_straps']} vias={th_g['n_vias']} "
            f"pads={th_g['n_pads']} rel_res={sol_g['rel_res']:.2e}"
        )
    else:
        print("    skip GCD thermal mesh (no pg_vdd_bumps.sp)")

    g_amb, c_th, p_w = 0.02, 1e-6, 0.01
    tau = c_th / g_amb
    dt_th, t_end_th = tau / 25.0, 8.0 * tau
    Gth = sparse.csr_matrix([[g_amb]], dtype=np.float64)
    tr = timestep_thermal_be({"G": Gth, "C": np.array([c_th])}, np.array([p_w]), dt_th, t_end_th)
    t_inf = p_w / g_amb
    check(abs(tr["T"][0] - t_inf) / t_inf < 0.02, "1-node thermal BE settles to P/G_amb")
    gold_th = ngspice_thermal_1node_gold(g_amb, c_th, p_w, dt_th, t_end_th)
    if gold_th.get("ok"):
        err_th = abs(gold_th["ngspice_dT_k"] - tr["dT_absmax_k"])
        check(err_th / t_inf < 0.05, f"ngspice thermal analogue |BE−ng|/T∞={err_th/t_inf:.3e}")
        print(f"    thermal BE vs ngspice |ΔT|={err_th:.4e} K T∞={t_inf:.4f} K")
    else:
        print(f"    ngspice thermal GAP ({gold_th.get('reason')})")

    from pdn_solvers import native_descriptor, native_descriptor_adaptive, native_mor_descriptor

    sysd = compact_vrm_die(
        vdd=1.1, r_vrm=0.015, l_vrm=2e-10, c_vrm=50e-12, r_pkg=0.05, l_pkg=2e-10, c_die=50e-12
    )
    t50, dur, i_peak, dt, t_end, vdd = 0.2e-9, 0.2e-9, 5e-3, 10e-12, 0.4e-9, 1.1
    ev_n4 = [{"idx": 0, "t50_s": t50, "dur_s": dur, "i_pulse": i_peak, "i_leak": 0.0}]
    py_n4 = timestep_descriptor(
        sysd,
        lambda t: triangle_above_leak(t, t50, dur, i_peak),
        dt,
        t_end,
        vdd,
    )
    check(py_n4.get("backend") == "python", f"descriptor without events is Python ({py_n4.get('via')})")
    nat_n4 = native_descriptor(
        sysd,
        ev_n4,
        vdd,
        t_end,
        dt,
    )
    if nat_n4 is None:
        print("    skip native descriptor (no libdpn)")
    else:
        err_n4 = abs(py_n4["worst_droop"] - nat_n4["worst_droop"]) * 1e3
        check(err_n4 < 1e-6, f"native N4 vs Python SparseLU |err|={err_n4:.4e} mV")
        print(
            f"    native N4 droop={nat_n4['worst_droop']*1e3:.4f} mV "
            f"python={py_n4['worst_droop']*1e3:.4f} mV |N-P|={err_n4:.4e} mV"
        )
        bicg_n4 = native_descriptor(sysd, ev_n4, vdd, t_end, dt, solver_kind=3)
        if bicg_n4 is None:
            print("    skip descriptor BiCGSTAB (no workhorse symbol)")
        else:
            err_b = abs(nat_n4["worst_droop"] - bicg_n4["worst_droop"]) * 1e3
            check(err_b < 1e-5, f"descriptor BiCGSTAB vs LU |err|={err_b:.4e} mV")
            print(f"    descriptor BiCGSTAB |A-E|={err_b:.4e} mV via={bicg_n4.get('via')}")
        ras_n4 = native_descriptor(sysd, ev_n4, vdd, t_end, dt, solver_kind=2)
        if ras_n4 is None:
            print("    skip descriptor RAS (no workhorse symbol)")
        else:
            err_r = abs(nat_n4["worst_droop"] - ras_n4["worst_droop"]) * 1e3
            check(err_r < 1e-5, f"descriptor RAS vs LU (ndom=1 compact) |err|={err_r:.4e} mV")
            print(f"    descriptor RAS compact |A-D|={err_r:.4e} mV via={ras_n4.get('via')}")
        check(
            native_descriptor(sysd, ev_n4, vdd, t_end, dt, solver_kind=1) is None,
            "descriptor AMG kind=1 is refused",
        )
        ad_n4 = native_descriptor_adaptive(sysd, ev_n4, vdd, t_end, dt)
        if ad_n4 is None:
            print("    skip descriptor adaptive (no symbol)")
        else:
            err_a = abs(nat_n4["worst_droop"] - ad_n4["worst_droop"]) * 1e3
            check(err_a < 2.0, f"adaptive descriptor vs gold (1 mV-class) |err|={err_a:.4f} mV")
            print(
                f"    adaptive descriptor steps={ad_n4['steps']} |A-ad|={err_a:.4f} mV "
                f"(not gold when L>0)"
            )
        sysd["dt"] = dt
        starts = np.zeros((2, 1), dtype=np.float64, order="F")
        starts[1, 0] = 1.0
        shifts = np.array([0.0, 1e9, 1.0 / dt], dtype=np.float64)
        mor = native_mor_descriptor(sysd, starts, shifts, n_moments=4)
        red = mor.timestep(sysd, ev_n4, vdd, t_end)
        err_m = abs(nat_n4["worst_droop"] - red["worst_droop"]) * 1e3
        check(err_m < 5.0, f"gen MOR vs N4 descriptor |A-C|={err_m:.4f} mV")
        print(
            f"    gen MOR m={mor.m} backend={mor.backend} |A-C|={err_m:.4e} mV"
        )
        sys_st["dt"] = dt
        st_ev = [{"idx": 1, "t50_s": t50, "dur_s": dur, "i_pulse": i_peak, "i_leak": 0.0}]
        st_lu = native_descriptor(sys_st, st_ev, vdd, t_end, dt)
        st_wh = native_descriptor(sys_st, st_ev, vdd, t_end, dt, solver_kind=3)
        if st_lu is not None and st_wh is not None:
            err_st = abs(st_lu["worst_droop"] - st_wh["worst_droop"]) * 1e3
            check(err_st < 1e-4, f"strap descriptor BiCGSTAB vs LU |err|={err_st:.4e} mV")
            print(f"    strap BiCGSTAB |A-E|={err_st:.4e} mV")
        if st_lu is not None:
            n_v_st = int(sys_st["n_v"])
            starts_st = np.zeros((n_v_st, 1), dtype=np.float64, order="F")
            starts_st[-1, 0] = 1.0
            mor_st = native_mor_descriptor(sys_st, starts_st, shifts, n_moments=4)
            red_st = mor_st.timestep(sys_st, st_ev, vdd, t_end)
            err_stm = abs(st_lu["worst_droop"] - red_st["worst_droop"]) * 1e3
            check(err_stm < 5.0, f"strap gen MOR vs descriptor |A-C|={err_stm:.4f} mV")
            print(f"    strap gen MOR m={mor_st.m} backend={mor_st.backend} |A-C|={err_stm:.4e} mV")
        from scipy import sparse as sp

        nv = 32
        g = 1.0 / 0.2
        Gch = sp.lil_matrix((nv, nv))
        for i in range(nv):
            if i > 0:
                Gch[i, i] += g
                Gch[i, i - 1] -= g
            if i + 1 < nv:
                Gch[i, i] += g
                Gch[i, i + 1] -= g
        Nch = nv + 1
        Ach = sp.lil_matrix((Nch, Nch))
        Ach[:nv, :nv] = Gch
        Ach[0, nv] = -1.0
        Ach[nv, 0] = 1.0
        Ach[nv, nv] = 0.05
        Ed = np.zeros(Nch)
        Ed[:nv] = 50e-12
        Ed[nv] = 2e-10
        sys_ch = {
            "A": Ach.tocsr(),
            "E": sp.diags(Ed, format="csr"),
            "n_v": nv,
            "n_die": nv,
            "die_idx": -1,
            "iv_list": [nv],
            "n_iv": 1,
            "dt": dt,
        }
        ch_ev = [{"idx": nv - 1, "t50_s": t50, "dur_s": dur, "i_pulse": i_peak, "i_leak": 0.0}]
        ch_lu = native_descriptor(sys_ch, ch_ev, vdd, t_end, dt)
        ch_ras = native_descriptor(sys_ch, ch_ev, vdd, t_end, dt, solver_kind=2)
        if ch_lu is not None and ch_ras is not None:
            err_ch = abs(ch_lu["worst_voltage"] - ch_ras["worst_voltage"])
            check(err_ch < 1e-6, f"32-node descriptor RAS vs LU |err|={err_ch:.3e} V")
            print(f"    32-node descriptor RAS |A-D|={err_ch:.3e} V")

    print("ALL test_pdn_layers PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
