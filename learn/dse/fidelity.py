"""Fidelity adapters. F4 is the existing Dynamic IR engine — ingest, don't fake.

F0  cheap analytical / SSK-GP / RUDY-class proxy
F1  Yosys + ABC liberty map + equiv (logic or architecture RTL)
F2  ingest OpenROAD place / GRT, plus F2-fast barycenter on a *candidate* netlist
F3  OpenSTA signoff ingest
F4  Dynamic IR / EM ingest (Solver A gold stays 45.298 mV on the GCD)
F5  GAP (signoff P&R not launched from the controller)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from .abc_space import write_abc_script
from .fingerprint import knobs_fp, sha256_file, sha256_text
from .memory import Candidate, DesignMemory
from .metrics import QoR, wns_cost_from_slack_ns
from .netgraph import estimate_physical, parse_mapped_verilog, features as net_features

REPO = Path(__file__).resolve().parents[1].parent
NANGATE_LIB = (
    REPO
    / "tools/OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib"
)
ORFS = REPO / "tools/OpenROAD-flow-scripts/flow"
COST_HINT = {"F0": 0.05, "F1": 2.0, "F2": 30.0, "F3": 20.0, "F4": 35.0, "F5": 600.0}


def reports_dir(variant: str) -> Path:
    return REPO / "learn" / "sim" / "reports"


def orfs_logs(variant: str) -> Path:
    return ORFS / "logs" / "nangate45" / "gcd" / variant


def orfs_results(variant: str) -> Path:
    return ORFS / "results" / "nangate45" / "gcd" / variant


def flowlab_params(root: Path | None = None) -> dict:
    p = (root or REPO) / "learn" / "flowlab" / "params.json"
    if not p.is_file():
        return {}
    return json.loads(p.read_text())


def ingest_physical(variant: str, mem: DesignMemory, design_id: str = "gcd") -> Candidate | None:
    """F3+F4 observation of the *current* layout. Separate level from ABC search."""
    rd = reports_dir(variant)
    sta = _read_json(rd / f"sta_signoff_{variant}.json")
    ir = _read_json(rd / f"dynamic_ir_{variant}.json")
    chip = _read_json(rd / f"pdn_chip_ir_{variant}.json")
    if not ir and not sta:
        return None
    params = flowlab_params()
    knobs = {
        "coreUtilization": params.get("coreUtilization"),
        "placeDensityAddon": params.get("placeDensityAddon"),
        "abcArea": params.get("abcArea"),
        "sdcPreset": params.get("sdcPreset"),
        "tnsEndPercent": params.get("tnsEndPercent"),
        "source": "ingest_layout",
    }
    fp = knobs_fp("physical", knobs)
    if fp in mem.seen_knobs("physical"):
        return next(c for c in mem.by_level("physical") if c.knobs_fp == fp)
    dyn = (ir or {}).get("dynamic") or {}
    static = (ir or {}).get("static") or (chip or {}).get("static") or {}
    em = (ir or {}).get("em") or {}
    slack = None
    timing = (ir or {}).get("timing_impact") or {}
    path = (timing.get("path") or {}) if isinstance(timing, dict) else {}
    if path.get("slack_ns") is not None:
        slack = float(path["slack_ns"])
    elif sta and (sta.get("timing") or {}).get("wns_ns") is not None:
        slack = float(sta["timing"]["wns_ns"])
    yosys_v = orfs_results(variant) / "1_2_yosys.v"
    q = QoR(
        wns_cost=wns_cost_from_slack_ns(slack),
        static_ir_mv=_mv(static.get("worst_ir"), static.get("worst_ir_mv")),
        dynamic_ir_mv=_mv(dyn.get("worst_droop"), dyn.get("worst_droop_mv")),
        em_j_a_m2=em.get("j_absmax_a_m2"),
        ttf_rel_inv=(1.0 / em["ttf_rel_min"]) if em.get("ttf_rel_min") else None,
        fidelity="F4" if ir else "F3",
        note="ingested layout oracles — not a new P&R",
    )
    rtl = REPO / "learn" / "flowlab" / "gcd.v"
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=None,
        level="physical",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=sha256_file(rtl),
        netlist_fp=sha256_file(yosys_v) if yosys_v.is_file() else None,
        fidelity=q.fidelity,
        qor=q,
        cost_s=0.0,
        note="F3/F4 ingest of existing FlowLab finish + Dynamic IR",
    )
    return mem.add(c)


def ingest_pdn(variant: str, mem: DesignMemory, design_id: str = "gcd") -> Candidate | None:
    ir = _read_json(reports_dir(variant) / f"dynamic_ir_{variant}.json")
    if not ir:
        return None
    dyn = ir.get("dynamic") or {}
    knobs = {
        "pkg_r": dyn.get("pkg_r"),
        "pkg_l": dyn.get("pkg_l"),
        "c_decap": dyn.get("c_decap"),
        "mode": ir.get("mode"),
        "source": "ingest_pdn",
    }
    fp = knobs_fp("pdn", knobs)
    if fp in mem.seen_knobs("pdn"):
        return next(c for c in mem.by_level("pdn") if c.knobs_fp == fp)
    em = ir.get("em") or {}
    static = ir.get("static") or {}
    q = QoR(
        static_ir_mv=_mv(static.get("worst_ir"), static.get("worst_ir_mv")),
        dynamic_ir_mv=_mv(dyn.get("worst_droop"), dyn.get("worst_droop_mv")),
        em_j_a_m2=em.get("j_absmax_a_m2"),
        ttf_rel_inv=(1.0 / em["ttf_rel_min"]) if em.get("ttf_rel_min") else None,
        fidelity="F4",
        note="PDN-level observation; gold droop is unrestamped Solver A",
    )
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=None,
        level="pdn",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=sha256_file(REPO / "learn" / "flowlab" / "gcd.v"),
        netlist_fp=None,
        fidelity="F4",
        qor=q,
        cost_s=0.0,
        note="F4 PDN ingest — does not re-run TRAN",
    )
    return mem.add(c)


def ingest_f2(variant: str, mem: DesignMemory, design_id: str = "gcd") -> Candidate | None:
    """Place / GRT / finish metrics from an existing ORFS run. No new P&R."""
    finish = _read_json(orfs_logs(variant) / "6_report.json")
    grt = orfs_logs(variant) / "5_1_grt.log"
    dp = orfs_logs(variant) / "3_5_place_dp.log"
    if not finish and not grt.is_file() and not dp.is_file():
        return None
    knobs = {"source": "ingest_f2_orfs", "variant": variant}
    fp = knobs_fp("physical", knobs)
    if fp in mem.seen_knobs("physical"):
        return next(c for c in mem.by_level("physical") if c.knobs_fp == fp)
    overflow = None
    usage = None
    wl = None
    if grt.is_file():
        text = grt.read_text(errors="replace")
        m = re.search(
            r"^Total\s+(\d+)\s+(\d+)\s+([0-9.]+)%\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)",
            text,
            re.M,
        )
        if m:
            usage = float(m.group(3)) / 100.0
            overflow = float(m.group(6))
        wm = re.search(r"Total wirelength:\s+([0-9.]+)", text)
        if wm:
            wl = float(wm.group(1))
    hpwl = None
    if dp.is_file():
        hm = re.search(r"Final HPWL\s+([0-9.]+)", dp.read_text(errors="replace"))
        if hm:
            hpwl = float(hm.group(1))
    area = None
    power = None
    slack = None
    util = None
    if finish:
        area = finish.get("finish__design__instance__area")
        power = finish.get("finish__power__total")
        slack = finish.get("finish__timing__setup__ws")
        util = finish.get("finish__design__instance__utilization")
    cong = overflow if overflow is not None else usage
    q = QoR(
        area_um2=float(area) if area is not None else None,
        power_w=float(power) if power is not None else None,
        wns_cost=wns_cost_from_slack_ns(float(slack)) if slack is not None else None,
        congestion=float(cong) if cong is not None else None,
        fidelity="F2",
        note=(
            f"ORFS ingest HPWL={hpwl} GRT_wl={wl} util={util} overflow={overflow} "
            "— not a new place"
        ),
    )
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=None,
        level="physical",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=sha256_file(REPO / "learn" / "flowlab" / "gcd.v"),
        netlist_fp=sha256_file(orfs_results(variant) / "1_2_yosys.v")
        if (orfs_results(variant) / "1_2_yosys.v").is_file()
        else None,
        fidelity="F2",
        qor=q,
        cost_s=0.0,
        note="F2 ingest of place/GRT/finish — controller did not launch P&R",
    )
    return mem.add(c)


def evaluate_f1_abc(
    *,
    rtl: Path,
    liberty: Path,
    knobs: dict,
    mem: DesignMemory,
    design_id: str = "gcd",
    parent_id: str | None = None,
    timeout_s: float = 60.0,
    level: str = "logic",
    top: str = "gcd",
) -> Candidate:
    """Yosys synth + liberty ABC + equiv vs RTL. ABC script is a *file* (not -p ';')."""
    ops = list(knobs.get("abc_ops") or [])
    args = list(knobs.get("abc_args") or [])
    fp = knobs_fp(level, knobs)
    t0 = time.time()
    lib = str(liberty)
    with tempfile.TemporaryDirectory(prefix="dse-f1-") as tmp:
        tmp_p = Path(tmp)
        log = tmp_p / "yosys.log"
        net = tmp_p / "mapped.v"
        ys = tmp_p / "f1.ys"
        abc_file = tmp_p / "aig.abc"
        aig_cmd = ""
        if ops:
            write_abc_script(ops, abc_file)
            aig_cmd = f"abc -script {abc_file}"
        map_cmd = "abc -liberty " + lib
        if args:
            map_cmd += " " + " ".join(args)
        ys.write_text(
            f"""
read_verilog {rtl}
hierarchy -check -top {top}
proc; flatten; opt_expr; opt_clean
design -save rtl
synth -top {top}
{aig_cmd}
design -save syn
design -copy-from rtl -as gold {top}
design -copy-from syn -as gate {top}
equiv_make gold gate equiv
hierarchy -top equiv
equiv_simple
equiv_induct
equiv_status
design -load syn
dfflibmap -liberty {lib}
{map_cmd}
stat -liberty {lib}
write_verilog -noattr {net}
"""
        )
        proc = subprocess.run(
            ["yosys", "-q", "-l", str(log), "-s", str(ys)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        text = log.read_text(errors="replace") if log.is_file() else (proc.stdout or "") + (proc.stderr or "")
        area, n_cells = _parse_stat(text, top)
        equiv = bool(
            re.search(r"Equivalence successfully proven", text, re.I)
            or re.search(r"are proven and 0 are unproven", text, re.I)
        )
        net_fp = sha256_file(net) if net.is_file() else sha256_text(text[-2000:])
        err = next((ln.strip() for ln in text.splitlines() if "ERROR" in ln), "")
        mapped_text = net.read_text() if net.is_file() else None
    cost = time.time() - t0
    ok = equiv and area is not None and proc.returncode == 0
    fail = None if ok else (err or "equiv_or_map_failed")
    cid = DesignMemory.new_id()
    artifacts: dict = {}
    if mapped_text and ok:
        dest = REPO / "learn" / "sim" / "dse" / "netlists" / f"{cid}.v"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(mapped_text)
        artifacts["mapped_v"] = str(dest)
        try:
            artifacts.update(net_features(parse_mapped_verilog(dest)))
        except Exception:
            pass
    q = QoR(
        area_um2=area,
        n_cells=n_cells,
        fidelity="F1",
        note="Yosys+ABC mapped area; delay/IR not claimed from F1",
    )
    c = Candidate(
        id=cid,
        design_id=design_id,
        parent_id=parent_id,
        level=level,
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=sha256_file(rtl),
        netlist_fp=net_fp,
        fidelity="F1",
        qor=q,
        cost_s=cost,
        artifacts=artifacts,
        status="ok" if ok else "fail",
        failure=fail,
        note=f"F1 {knobs.get('name')} equiv={'PASS' if equiv else 'FAIL'}"
        + (f" · {err}" if err and not ok else ""),
    )
    return mem.add(c)


def ensure_mapped_netlist(
    cand: Candidate,
    *,
    rtl: Path,
    liberty: Path,
    top: str = "gcd",
    timeout_s: float = 60.0,
) -> Candidate:
    """Resume-safe: re-map an F1 candidate that predates netlist persistence."""
    existing = (cand.artifacts or {}).get("mapped_v")
    if existing and Path(existing).is_file():
        return cand
    dest = REPO / "learn" / "sim" / "dse" / "netlists" / f"{cand.id}.v"
    dest.parent.mkdir(parents=True, exist_ok=True)
    knobs = cand.knobs or {}
    ops = list(knobs.get("abc_ops") or [])
    args = list(knobs.get("abc_args") or [])
    lib = str(liberty)
    with tempfile.TemporaryDirectory(prefix="dse-map-") as tmp:
        tmp_p = Path(tmp)
        net = tmp_p / "mapped.v"
        ys = tmp_p / "map.ys"
        abc_file = tmp_p / "aig.abc"
        aig_cmd = ""
        if ops:
            write_abc_script(ops, abc_file)
            aig_cmd = f"abc -script {abc_file}"
        map_cmd = "abc -liberty " + lib
        if args:
            map_cmd += " " + " ".join(args)
        ys.write_text(
            f"""
read_verilog {rtl}
hierarchy -check -top {top}
proc; flatten; opt_expr; opt_clean
synth -top {top}
{aig_cmd}
dfflibmap -liberty {lib}
{map_cmd}
write_verilog -noattr {net}
"""
        )
        proc = subprocess.run(
            ["yosys", "-q", "-s", str(ys)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if proc.returncode != 0 or not net.is_file():
            return cand
        dest.write_text(net.read_text())
    art = dict(cand.artifacts or {})
    art["mapped_v"] = str(dest)
    try:
        art.update(net_features(parse_mapped_verilog(dest)))
    except Exception:
        pass
    cand.artifacts = art
    return cand


def evaluate_f2_fast(
    parent: Candidate,
    mem: DesignMemory,
    *,
    design_id: str = "gcd",
    util: float = 0.35,
) -> Candidate | None:
    """F2-fast on a persisted F1 netlist. Separate physical observation, no P&R."""
    mapped = (parent.artifacts or {}).get("mapped_v")
    if not mapped or not Path(mapped).is_file():
        return None
    knobs = {
        "source": "f2_fast_barycenter",
        "parent_id": parent.id,
        "parent_name": parent.knobs.get("name"),
        "util": util,
    }
    fp = knobs_fp("physical", knobs)
    if fp in mem.seen_knobs("physical"):
        return next(c for c in mem.by_level("physical") if c.knobs_fp == fp)
    t0 = time.time()
    est = estimate_physical(Path(mapped), util=util)
    q = QoR(
        area_um2=parent.qor.area_um2,
        n_cells=est.get("n_cells"),
        congestion=est.get("congestion"),
        fidelity="F2",
        note=f"F2-fast HPWL={est['hpwl']:.3f} · {est['via']}",
    )
    c = Candidate(
        id=DesignMemory.new_id(),
        design_id=design_id,
        parent_id=parent.id,
        level="physical",
        knobs=knobs,
        knobs_fp=fp,
        rtl_fp=parent.rtl_fp,
        netlist_fp=parent.netlist_fp,
        fidelity="F2",
        qor=q,
        cost_s=time.time() - t0,
        artifacts=est,
        attr={
            "transform": parent.knobs.get("name"),
            "context": {"parent": parent.id, "level": parent.level},
            "note": "transform+netlist → ΔHPWL/RUDY; not Dynamic IR",
        },
        note=f"F2-fast child of {parent.knobs.get('name')} HPWL={est['hpwl']:.3f}",
    )
    return mem.add(c)


def _parse_stat(text: str, top: str = "gcd") -> tuple[float | None, float | None]:
    area = None
    cells = None
    for m in re.finditer(rf"Chip area for module '\\{top}':\s+([0-9.]+)", text):
        area = float(m.group(1))
    # Prefer the last cell count that sits near a gcd/top area line
    for m in re.finditer(r"Number of cells:\s+([0-9]+)", text):
        cells = float(m.group(1))
    return area, cells


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _mv(frac_or_none, mv_or_none) -> float | None:
    if mv_or_none is not None:
        return float(mv_or_none)
    if frac_or_none is None:
        return None
    v = float(frac_or_none)
    if v < 1.0:  # volts of droop
        return v * 1e3
    return v


def liberty_path() -> Path:
    env = os.environ.get("STA_LIB") or os.environ.get("DSE_LIB")
    if env and Path(env).is_file():
        return Path(env)
    return NANGATE_LIB
