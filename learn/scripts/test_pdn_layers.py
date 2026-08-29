#!/usr/bin/env python3
"""Layer contracts: CCS interpolator is real; NLDM is never mapped to CCS."""

from __future__ import annotations

import math
import subprocess
import sys
import tempfile
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from pdn_activity import plan_events, probe_activity_trace  # noqa: E402
from pdn_current import (  # noqa: E402
    SYNTHETIC_CCS_LIB,
    current_source_for_event,
    interpolate_ccs_current,
    parse_ccs_output_current,
    probe_liberty_current_model,
    triangle_above_leak,
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

    # 1-node descriptor RLC MOR vs Solver A hist (native or SciPy).
    if "/usr/lib/python3/dist-packages" not in sys.path:
        sys.path.insert(0, "/usr/lib/python3/dist-packages")
    import numpy as np
    from scipy import sparse
    from pdn_dynamic import assemble_be, timestep_be
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

    from pdn_solvers import RASDD

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
    from pdn_extract import extract_pdn, parse_tech_lef, probe_spef
    from pdn_em import em_thermal_snapshot

    tech = parse_tech_lef(lef)
    check(tech["status"] == "READY", f"tech LEF READY ({tech.get('path')})")
    m1 = (tech.get("layers") or {}).get("metal1") or {}
    check(abs(float(m1.get("width_um", 0)) - 0.07) < 1e-12, "metal1 WIDTH 0.07 µm (not SPACINGTABLE)")
    check(abs(float(m1.get("rpersq", 0)) - 0.38) < 1e-12, "metal1 RPERSQ 0.38")
    check(abs(float(m1.get("thickness_um", 0)) - 0.13) < 1e-12, "metal1 THICKNESS 0.13 µm")

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
    print(
        f"    EM J={em['j_absmax_a_m2']:.4e} A/m² TTF_rel={em['ttf_rel_min']:.4e} "
        f"ΔT={em['dT_absmax_k']:.4e} K w/min={em['hottest_j'].get('w_over_min')}"
    )

    from pdn_solvers import native_descriptor

    sysd = compact_vrm_die(
        vdd=1.1, r_vrm=0.015, l_vrm=2e-10, c_vrm=50e-12, r_pkg=0.05, l_pkg=2e-10, c_die=50e-12
    )
    t50, dur, i_peak, dt, t_end, vdd = 0.2e-9, 0.2e-9, 5e-3, 10e-12, 0.4e-9, 1.1
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
        [{"idx": 0, "t50_s": t50, "dur_s": dur, "i_pulse": i_peak, "i_leak": 0.0}],
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

    print("ALL test_pdn_layers PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
