"""DSE live F4 contracts: DirectLU / AMG / RAS / Krylov + extract.

Extracted from test_dse.py (passo D.5). Imported last by test_dse.main().
One process, one heavy F4 job. Same check() messages as the inlined block.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from dse.f4_oracle import GOLD_MV, available as f4_ok, solve_f4
from dse.memory import DesignMemory
from dse.openroad_f2 import extract_available, extract_pdn


def check_live_f4(check, *, root: Path) -> None:
    _ROOT = root
    mapped_ok = _ROOT / "learn/sim/dse/netlists/4628a15dbc9a.v"

    gold_json = _ROOT / "learn/sim/reports/dynamic_ir_flowlab.json"
    gold_before = gold_json.read_text() if gold_json.is_file() else None
    if f4_ok("flowlab"):
        base = solve_f4(variant="flowlab")
        check(base.get("status") == "ok", f"F4 oracle Solver A ({base.get('reason')})")
        check(base.get("gold") is False, "candidate F4 is not marked gold")
        check(base.get("extract") == "finish", "default F4 uses the finish extract")
        check(base.get("solver_kind") == "direct", f"default F4 solver is DirectLU, got {base.get('solver_kind')}")
        check(
            abs(float(base["worst_droop_mv"]) - GOLD_MV) > 1.0,
            f"current finish mesh is not the 45.298 reference_run, got {base.get('worst_droop_mv')}",
        )
        check(
            abs(float(base["worst_droop_mv"]) - 6.075) < 0.05,
            f"current FlowLab DirectLU ~6.075 mV, got {base.get('worst_droop_mv')}",
        )
        check(
            isinstance(base.get("solve"), dict) and base["solve"].get("role") == "reference",
            f"SolveResult stamps DirectLU as numerical reference, got {base.get('solve')}",
        )
        scen = base.get("current_scenario") or {}
        check(scen.get("source") == "sta_t50", f"GCD 6.075 uses sta_t50 scenario, got {scen}")
        check(
            ((base.get("solve") or {}).get("activity_via") or {}).get("scenario", {}).get("source") == "sta_t50",
            "SolveResult.activity_via points at the sta_t50 scenario",
        )
        amg = solve_f4(variant="flowlab", solver="amg")
        check(amg.get("status") == "ok", f"F4 AMG residual ({amg.get('reason')})")
        check(amg.get("gold") is False, "AMG residual is not marked gold")
        check(amg.get("solver_kind") == "amg", f"AMG solver_kind, got {amg.get('solver_kind')}")
        check(
            abs(float(amg["worst_droop_mv"]) - float(base["worst_droop_mv"])) < 0.05,
            f"AMG matches DirectLU on this mesh, got {amg.get('worst_droop_mv')}",
        )
        print(f"    F4 AMG {amg['worst_droop_mv']:.3f} mV vs DirectLU {base['worst_droop_mv']:.3f} mV ({amg.get('cost_s', 0):.2f}s)")
        ras = solve_f4(variant="flowlab", solver="ras")
        check(ras.get("status") == "ok", f"F4 RAS residual ({ras.get('reason')})")
        check(ras.get("gold") is False, "RAS residual is not marked gold")
        check(ras.get("solver_kind") == "ras", f"RAS solver_kind, got {ras.get('solver_kind')}")
        check(
            abs(float(ras["worst_droop_mv"]) - float(base["worst_droop_mv"])) < 0.05,
            f"RAS matches DirectLU on this mesh, got {ras.get('worst_droop_mv')}",
        )
        print(f"    F4 RAS {ras['worst_droop_mv']:.3f} mV vs DirectLU {base['worst_droop_mv']:.3f} mV ({ras.get('cost_s', 0):.2f}s)")
        kry = solve_f4(variant="flowlab", solver="krylov")
        check(kry.get("status") == "ok", f"F4 Krylov/MOR residual ({kry.get('reason')})")
        check(kry.get("gold") is False, "Krylov residual is not marked gold")
        check(kry.get("solver_kind") == "krylov", f"Krylov solver_kind, got {kry.get('solver_kind')}")
        check((kry.get("m") or 0) >= 1, f"Krylov reports reduced order m, got {kry.get('m')}")
        check(
            abs(float(kry["worst_droop_mv"]) - float(base["worst_droop_mv"])) < 5.0,
            f"Krylov/MOR stays within 5 mV of DirectLU {kry.get('worst_droop_mv')}",
        )
        check(
            (kry.get("solve") or {}).get("abs_err_vs_reference_mv") is not None
            or abs(float(kry["worst_droop_mv"]) - float(base["worst_droop_mv"])) < 5.0,
            "Krylov SolveResult can carry |A-C|",
        )
        print(
            f"    F4 Krylov {kry['worst_droop_mv']:.3f} mV m={kry.get('m')} "
            f"vs DirectLU {base['worst_droop_mv']:.3f} mV ({kry.get('cost_s', 0):.2f}s)"
        )
        from dse.controller import admit_paid_f4
        from heavy_analysis import AES_F4_N_NODES, AES_F4_N_R

        _alog: list[dict] = []

        def _admit_step(kind: str, **kw):
            _alog.append({"kind": kind, **kw})

        mem_gate = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-gate-")) / "m.jsonl")
        g_a = admit_paid_f4(mem_gate, solver="direct", n_r=int(base["n_r"]), step=_admit_step)
        check(
            g_a["admitted"] is True and (base.get("solve") or {}).get("role") == "reference",
            f"controller-paid DirectLU is reference, gate={g_a} solve={base.get('solve')}",
        )
        g_c = admit_paid_f4(mem_gate, solver="krylov", n_r=int(base["n_r"]), step=_admit_step)
        check(
            g_c["admitted"] is True and (kry.get("solve") or {}).get("role") == "accelerator",
            f"controller-paid Krylov is accelerator, gate={g_c} solve={kry.get('solve')}",
        )
        g_aes = admit_paid_f4(
            mem_gate, solver="krylov", n_r=AES_F4_N_R, n_nodes=AES_F4_N_NODES, step=_admit_step
        )
        check(g_aes["admitted"] is False, f"controller gate still refuses AES Krylov, got {g_aes}")
        check(
            any(x.get("kind") == "admit" and x.get("pay") is False for x in _alog),
            "refused admit is logged on the controller step",
        )
        check(base.get("static_ir_mv") is not None, "F4 restamp reports static IR")
        check(float(base["static_ir_mv"]) > 1.0, f"static IR is a real mV drop, got {base.get('static_ir_mv')}")
        check(
            abs(float(base["static_ir_mv"]) - float(base["worst_droop_mv"])) > 0.5,
            "static IR is not a copy of dynamic droop",
        )
        em0 = base.get("em") or {}
        check(em0.get("j_absmax_a_m2") is not None, f"F4 restamp reports EM J ({em0})")
        extra_c = solve_f4(variant="flowlab", c_decap=200e-15)
        check(extra_c["worst_droop_mv"] < base["worst_droop_mv"] - 0.5, "more decap lowers droop on the same extract")
        hot = solve_f4(variant="flowlab", i_scale=1.2)
        check(hot["worst_droop_mv"] > base["worst_droop_mv"] + 0.5, "I(t)×1.2 raises droop (same spatial pattern)")
        print(
            f"    F4 oracle base {base['worst_droop_mv']:.3f}  decap200 {extra_c['worst_droop_mv']:.3f}  "
            f"iscale1.2 {hot['worst_droop_mv']:.3f} mV  J={em0.get('j_absmax_a_m2'):.3e} ({base['cost_s']:.2f}s)"
        )
        mapped_ext = _ROOT / "learn/sim/dse/netlists/ab9f115d5a67.v"
        if not mapped_ext.is_file() and mapped_ok.is_file():
            mapped_ext = mapped_ok
        if extract_available() and mapped_ext.is_file():
            dest = Path(tempfile.mkdtemp(prefix="dse-ext-"))
            ext = extract_pdn(mapped_ext, dest, timeout_s=60)
            check(ext.get("status") == "ok", f"candidate write_pg_spice ({ext.get('reason')})")
            check((ext.get("n_r") or 0) > 200, f"candidate spice has an R mesh, n_r={ext.get('n_r')}")
            check(ext.get("n_r") != base.get("n_r"), "candidate extract is not the finish mesh")
            check(ext.get("gold") is False, "candidate extract is not gold")
            cand = solve_f4(variant="flowlab", spice=ext["spice"], insts=ext["insts"])
            check(cand.get("status") == "ok", f"Solver A on candidate extract ({cand.get('reason')})")
            check(cand.get("extract") == "candidate", "override spice is labeled candidate")
            check(cand.get("gold") is False, "candidate solve is not gold")
            check(abs(float(cand["worst_droop_mv"]) - GOLD_MV) > 0.2, "candidate mesh droop is not the finish gold")
            check(cand.get("static_ir_mv") is not None, "candidate F4 reports static IR")
            cem = cand.get("em") or {}
            check(cem.get("j_absmax_a_m2") is not None, "candidate F4 reports EM J")
            print(
                f"    F4 candidate extract n_r={ext['n_r']} n_i={ext.get('n_i')} "
                f"droop={cand['worst_droop_mv']:.3f} mV J={cem.get('j_absmax_a_m2'):.3e} "
                f"({ext['cost_s']:.2f}+{cand.get('cost_s', 0):.2f}s)"
            )
            dest_r = Path(tempfile.mkdtemp(prefix="dse-rext-"))
            ext_r = extract_pdn(
                mapped_ext, dest_r, timeout_s=60, x_dbu=70896.0, y_dbu=39429.0, region="r31"
            )
            check(ext_r.get("status") == "ok", f"region write_pg_spice ({ext_r.get('reason')})")
            check(ext_r.get("region_bin"), f"region extract names the bin, got {ext_r.get('region_bin')}")
            check((ext_r.get("n_r") or 0) > 200, f"region spice has an R mesh, n_r={ext_r.get('n_r')}")
            check(ext_r.get("gold") is False, "region extract is not gold")
            check(ext_r.get("n_r") != base.get("n_r"), "region extract is not the finish mesh")
            print(
                f"    F4 region extract bin={ext_r.get('region_bin')} n_r={ext_r['n_r']} "
                f"({ext_r['cost_s']:.2f}s)"
            )
        else:
            print("    skip candidate PDN extract (no openroad or mapped netlist)")
    else:
        print("    skip F4 oracle (no cached extract)")
    if gold_before is not None:
        check(gold_json.read_text() == gold_before, "F4 oracle does not restamp dynamic_ir_flowlab.json gold")
