"""Phase 4/5 gate: aes is a first-class design, not a GCD leftover.

No oracle. Planner / attribution / dispatch / activity / LLM mock / bandit.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "learn"))

from dse.activity import _parse_saif, _parse_vcd, load_activity  # noqa: E402
from dse.attribute import _cones_of, _module_of, inspect_f4  # noqa: E402
from dse.bandit import choose, context, reward_catalog_vs_pdn  # noqa: E402
from dse.designs import rtl_inputs, resolve  # noqa: E402
from dse.f4_oracle import attach_activity_flags, build_worker_cmd, solve_f4, solver_devices  # noqa: E402
from dse.inspect import inspect_and_choose  # noqa: E402
from dse.fidelity import _read_verilog_block, evaluate_f1_abc  # noqa: E402
from dse.dispatch import run_next_refine  # noqa: E402
from dse.frame import leftover_cells, next_stage, refine_chain  # noqa: E402
from dse.memory import Candidate, DesignMemory  # noqa: E402
from dse.metrics import QoR  # noqa: E402
from dse.planner import plan_search  # noqa: E402
from dse.proposer import llm_propose, symbolic_propose  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("ok  " if cond else "FAIL") + " " + msg)
    if not cond:
        FAILS.append(msg)


def _boom(*_a, **_k):
    raise AssertionError("aes fixture must not evaluate an oracle")


def main() -> int:
    gcd = resolve("gcd")
    aes = resolve("aes")
    check(gcd.arch_extracts and gcd.has_cone("dpath") and gcd.has_cone("ctrl"), "GCD keeps cone fixtures")
    check(not aes.arch_extracts and not aes.has_cone("dpath") and not aes.has_cone("ctrl"),
          "aes has no dpath/ctrl cones")
    check(aes.top == "aes_cipher_top", f"aes top is aes_cipher_top, got {aes.top}")
    check(aes.rtl.is_file() and len(aes.rtl_files) == 4, f"aes cipher-top closure is 4 files, got {aes.rtl_files}")
    check(aes.clk_period_ns == 0.82 and gcd.clk_period_ns == 0.46,
          f"clock periods stay design-local, aes={aes.clk_period_ns} gcd={gcd.clk_period_ns}")
    check(aes.constraint.is_file() and "aes" in str(aes.constraint) and "gcd" not in str(aes.constraint),
          f"aes SDC is the 0.82 ns ORFS constraint, got {aes.constraint}")
    check(gcd.constraint.is_file() and "gcd" in str(gcd.constraint),
          f"GCD SDC stays the 0.46 ns ORFS constraint, got {gcd.constraint}")
    check(all(p.name != "aes_inv_cipher_top.v" for p in aes.rtl_files), "aes F1 does not pull the inverse-cipher top")
    ibex = resolve("ibex")
    check(ibex.top == "ibex_core" and ibex.hdl == "systemverilog" and not ibex.f1_ready,
          "ibex is registered as SV/slang — F1 is not a fake Verilog remap")
    try:
        evaluate_f1_abc(
            rtl=ibex.rtl,
            liberty=Path("/dev/null"),
            knobs={"name": "liberty_default"},
            mem=DesignMemory(Path(tempfile.mkdtemp(prefix="dse-ibex-")) / "e.jsonl"),
            design_id="ibex",
            top=ibex.top,
        )
        check(False, "ibex F1 must refuse rather than remap SystemVerilog as Verilog")
    except ValueError as e:
        check("frontend" in str(e).lower(), f"ibex F1 is a loud GAP, got {e}")

    empty = DesignMemory(Path(tempfile.mkdtemp(prefix="dse-empty-")) / "e.jsonl")
    mem_g = DesignMemory(REPO / "learn" / "sim" / "dse" / "golden" / "memory_flowlab.golden.jsonl")
    planned_g = plan_search(
        {"modules": ["dpath"], "combo_frac": 0.8, "scope": "logic_cone"},
        empty,
        f2_cong=None,
        design_id="gcd",
    )
    check(any(s["level"] == "architecture" for s in planned_g["steps"]), "GCD still schedules architecture extracts")
    planned_ctrl = plan_search(
        {"modules": ["ctrl"], "combo_frac": 0.2, "scope": "logic_cone"},
        mem_g,
        f2_cong=None,
        design_id="gcd",
    )
    check(any(s["level"] == "logic_ctrl" for s in planned_ctrl["steps"]),
          "GCD planner still schedules ctrl-cone ABC when STA names the FSM")

    planned_a = plan_search(
        {"modules": ["aes_cipher_top"], "combo_frac": 0.9, "scope": "logic_cone"},
        mem_g,
        f2_cong=None,
        design_id="aes",
    )
    levels_a = [s["level"] for s in planned_a["steps"]]
    check("architecture" not in levels_a, f"aes does not inherit GCD e-graph extracts, got {levels_a}")
    check("logic_ctrl" not in levels_a, f"aes does not invent a ctrl cone, got {levels_a}")
    check("winning_ir_region_cell_leftover2" in levels_a, "aes still gets the generic refine plan levels")

    check(_module_of("aes_cipher_top/sa00/sbox") == "aes_cipher_top", "aes instance maps to the top block")
    check(_module_of("dpath/sub/_122_") == "dpath", "GCD dpath mapping is unchanged")
    cones = _cones_of("aes_cipher_top/sa00/sbox")
    check(cones[:2] == ["aes_cipher_top", "aes_cipher_top/sa00"], f"aes cones are hierarchical, got {cones}")
    check("dpath" not in cones and "ctrl" not in cones, "aes cones never invent dpath/ctrl")

    tmp = Path(tempfile.mkdtemp(prefix="dse-aes-")) / "m.jsonl"
    mem_a = DesignMemory(tmp)
    mem_a.add(
        Candidate(
            id="aes_pdn",
            design_id="aes",
            parent_id=None,
            level="pdn",
            knobs={"source": "f4_solver_a", "name": "decap_200f", "extract_id": "aesxt", "pkg_r": 0.05, "pkg_l": 2e-10, "c_decap": 2e-13},
            knobs_fp="aes_pdn",
            rtl_fp="aes",
            netlist_fp=None,
            fidelity="F4",
            qor=QoR(dynamic_ir_mv=12.0, fidelity="F4"),
            cost_s=1.0,
            status="ok",
            attr={
                "via": "active_f4_winning_ir_region_pdn",
                "region": "r11",
                "combo_frac": 0.7,
                "cells": ["aes_cipher_top/sa00/sbox", "aes_cipher_top/sa01/sbox"],
                "modules": ["aes_cipher_top"],
            },
        )
    )
    nxt = next_stage(mem_a)
    check(nxt is not None and nxt.get("stage") == "sizeup" and nxt.get("depth") == 0,
          f"aes refine starts at refine[0] size-up, got {nxt}")
    check(all("dpath" not in str(c) and "ctrl" not in str(c) for c in (nxt or {}).get("cells") or []),
          "aes size-up cells are not GCD names")
    paid = run_next_refine(
        mem_a,
        budget_left=1.0,
        plan_levels=set(),
        design_id="aes",
        variant="aes",
        rtl=None,
        liberty=None,
        step=lambda *_a, **_k: None,
        t_end=0.0,
        ensure_mapped_netlist=_boom,
        evaluate_cell_size=_boom,
        evaluate_f4_extract=_boom,
        evaluate_f4_pdn=_boom,
        extract_on_disk=_boom,
        persist_hotspot_join=_boom,
        flowlab_params=_boom,
        gpl_density=_boom,
        winning_host_pdn=_boom,
    )
    check(not paid, "aes dispatch refuses without a planned level / budget — no oracle")

    saif = _parse_saif('(SAIFILE\nINSTANCE aes_cipher_top/sa00\n(TC 10)\n', path=Path("x.saif"))
    check(saif["via"] == "saif_tc" and saif["n_toggle"] == 10, f"SAIF TC parses, got {saif}")
    vcd = _parse_vcd("$var wire 1 ! clk $end\n#0\n0!\n#1\n1!\n#2\n0!\n", path=Path("x.vcd"))
    check(vcd["via"] == "vcd_edges" and vcd["n_toggle"] >= 1, f"VCD edges parse, got {vcd}")
    check(load_activity(design_id="aes") is None, "missing aes waveform stays missing")
    files, incs = rtl_inputs(aes.rtl, "aes")
    ys = _read_verilog_block(files, incs)
    check("aes_sbox.v" in ys and "aes_rcon.v" in ys and any(str(d) in ys for d in incs),
          f"aes F1 reads the cipher closure with include dirs, got {ys}")
    gfiles, _gincs = rtl_inputs(gcd.rtl, "gcd")
    check(gfiles == [gcd.rtl], f"GCD F1 stays single-file, got {gfiles}")
    dev = solver_devices()
    check(dev.get("cpu") is True and dev.get("default_solver") == "direct", f"F4 default stays DirectLU, got {dev}")
    if not dev.get("cuda"):
        gap = solve_f4(device="cuda")
        check(gap.get("status") == "GAP" and gap.get("gold") is False, f"CUDA gap is loud, not a fake GPU solve ({gap})")

    os.environ["DSE_LLM"] = "mock"
    mock = llm_propose(mem_g, focus="aes_cipher_top", design_id="aes")
    os.environ.pop("DSE_LLM", None)
    check(mock is not None and mock[0]["via"] == "llm_proposer_mock", f"LLM mock is CI-safe, got {mock}")
    check("pkg_l" not in mock[0] and "coreUtilization" not in mock[0], "LLM mock does not flatten physical knobs")
    sym_aes = symbolic_propose(mem_g, focus="aes_cipher_top", design_id="aes")
    check(all(p.get("level") != "architecture" for p in sym_aes),
          "aes symbolic proposer does not emit GCD extracts")

    ctx = context(mem_g)
    check(ctx.get("stage") == "catalog" and ctx.get("depth") == 2, f"bandit context follows next_stage, got {ctx}")
    check(choose(mem_g) is not None, "bandit chooses the generic next refine stage")
    live = REPO / "learn" / "sim" / "dse" / "memory_flowlab.jsonl"
    if live.is_file():
        lmem = DesignMemory(live)
        r = reward_catalog_vs_pdn(lmem, 2)
        check(r is not None and abs(r - (3.942 - 3.935)) < 0.02, f"depth-2 catalog reward is leftover2 unused L, got {r}")
        check(choose(lmem) is None, "closed live chain has no bandit arm")
        check(leftover_cells(lmem, 2) == [] and len(refine_chain(lmem)) == 3, "live refine[0..2] still holds")

    aes_mem = REPO / "learn" / "sim" / "dse" / "memory_aes.jsonl"
    if aes_mem.is_file():
        am = DesignMemory(aes_mem)
        check(all(c.design_id == "aes" for c in am.all()), "aes memory is not a GCD leftover")
        f3s = [c for c in am.all() if c.fidelity == "F3" and c.status == "ok"]
        check(bool(f3s), "live aes F3 is on disk")
        if f3s:
            sdc = str((f3s[-1].artifacts or {}).get("sdc") or "")
            check("aes" in sdc and "gcd" not in sdc, f"live aes F3 used the 0.82 ns SDC, got {sdc}")
            check((f3s[-1].artifacts or {}).get("wns_ns") is not None, "live aes F3 recorded WNS")
        gpls = [c for c in am.by_level("physical") if (c.knobs or {}).get("source") == "f2_openroad_gpl" and c.status == "ok"]
        check(bool(gpls), "live aes OpenROAD GPL is on disk")
        f4s = [c for c in am.by_level("pdn") if c.status == "ok" and c.qor.static_ir_mv is not None]
        check(bool(f4s), "live aes F4 static IR is on disk")
        legacy = [c for c in f4s if int((c.artifacts or {}).get("n_r") or 0) == 73139]
        check(bool(legacy), "73k-R AES static extract still recorded")
        if legacy:
            ir = float(legacy[-1].qor.static_ir_mv)
            check(abs(ir - 6.954) < 0.05, f"aes on-die static IR is 6.954 mV, got {ir}")
            check((legacy[-1].artifacts or {}).get("n_r") == 73139, "aes mesh is the 73k-R candidate extract")
            check("aes" in str((legacy[-1].artifacts or {}).get("sdc") or ""), "aes F4 used the 0.82 ns SDC")
            dyn_mv = legacy[-1].qor.dynamic_ir_mv
            if dyn_mv is None:
                check(True, "aes 73k-R dynamic IR still GAP — not a gold restamp")
            else:
                check(abs(float(dyn_mv) - 45.298) > 1.0, f"aes dynamic IR is not gold 45.298, got {dyn_mv}")
                check(float(dyn_mv) > 0.0, f"aes dynamic IR is a paid droop, got {dyn_mv}")
            insts = (legacy[-1].artifacts or {}).get("insts")
            host = legacy[-1]
            if insts and Path(insts).is_file():
                attr = inspect_f4(host, design_id="aes")
                check(attr.get("join") == "odb-geom", f"aes F4 inspect is an ODB join, got {attr.get('join')}")
                check(attr.get("modules") == ["aes_cipher_top"], f"aes inspect block is the cipher top, got {attr.get('modules')}")
                check("dpath" not in (attr.get("modules") or []) and "ctrl" not in (attr.get("cones") or []),
                      "aes inspect never invents dpath/ctrl")
                check(bool(attr.get("cells")) and all(not str(x).startswith("dpath") for x in attr.get("cells") or []),
                      f"aes inspect cells are ODB instances, got {attr.get('cells')}")
                chosen = inspect_and_choose(am, design_id="aes", persist=False)
                nxt = chosen.get("next_stage")
                check(nxt is not None and nxt.get("stage") == "sizeup", f"aes inspect opens refine[0] size-up, got {nxt}")
                check(all("dpath" not in str(x) and "ctrl" not in str(x) for x in (nxt or {}).get("cells") or []),
                      "aes next size-up cells are not GCD names")
                steer = chosen.get("steer")
                if steer:
                    check(steer.get("modules") == ["aes_cipher_top"], f"aes size-up steer stays on the cipher top, got {steer.get('modules')}")
                    check(steer.get("host_source") == "f4_candidate_extract", f"aes join host is the candidate extract, got {steer.get('host_source')}")
        cloud = [
            c
            for c in f4s
            if int((c.artifacts or {}).get("n_r") or 0) == 66295 and c.qor.dynamic_ir_mv is not None
        ]
        if cloud:
            check(abs(float(cloud[-1].qor.static_ir_mv) - 12.953) < 0.05, f"cloud AES static ~12.953 mV, got {cloud[-1].qor.static_ir_mv}")
            check(abs(float(cloud[-1].qor.dynamic_ir_mv) - 17.745) < 0.05, f"cloud AES DirectLU droop ~17.745 mV, got {cloud[-1].qor.dynamic_ir_mv}")
            check(abs(float(cloud[-1].qor.dynamic_ir_mv) - 45.298) > 1.0, "cloud AES droop is not gold 45.298")
        f5s = [
            c
            for c in am.by_level("routing")
            if (c.knobs or {}).get("source") == "f5_openroad_drt_rcx" and c.status == "ok"
        ]
        if f5s:
            sdc = str((f5s[-1].knobs or {}).get("sdc") or (f5s[-1].artifacts or {}).get("sdc") or "")
            check("aes" in sdc and "gcd" not in sdc, f"live aes F5-lite used the 0.82 ns SDC, got {sdc}")
            check((f5s[-1].knobs or {}).get("clock") == "ideal", "live aes F5-lite clock stays ideal (no CTS)")
            check((f5s[-1].knobs or {}).get("top") == "aes_cipher_top", "live aes F5-lite top is the cipher")
    from dse.designs import resolve as resolve_design
    from dse.openroad_f2 import evaluate_f5_drt as raw_f5
    aes_spec = resolve_design("aes")
    gcd_spec = resolve_design("gcd")
    refuse = raw_f5(aes_spec.rtl, top=aes_spec.top, sdc=gcd_spec.constraint, timeout_s=1)
    check(
        refuse.get("status") == "fail" and "refusing gcd SDC" in str(refuse.get("reason")),
        f"aes F5 refuses the GCD SDC, got {refuse}",
    )


    missing = attach_activity_flags(["worker"], variant="aes", design_id="aes")
    check(missing == ["worker"], "missing aes waveform does not invent --saif/--vcd")
    cmd = build_worker_cmd(design_id="aes", period_ns=0.82, solver="krylov")
    check("--period-ns" in cmd and "0.82" in cmd, f"aes worker clock stays 0.82 ns, got {cmd}")
    check("--saif" not in cmd and "--vcd" not in cmd, "aes worker cmd stays waveform-free when no file exists")

    if FAILS:
        print(f"{len(FAILS)} FAILED")
        return 1
    print("ALL test_designs PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
