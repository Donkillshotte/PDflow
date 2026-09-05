"""Lab-only ASAP7 research kit.

Not the course. Not the product campaign. Does not decide wins.
Does not write nangate45/gcd/flowlab. Does not restamp gold 45.298 mV.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dse.flow_role import LOCKED_VARIANTS, is_locked_variant

REPO = Path(__file__).resolve().parents[2]
ORFS_FLOW = REPO / "tools" / "OpenROAD-flow-scripts" / "flow"
ASAP7_PLAT = ORFS_FLOW / "platforms" / "asap7"
SC6T_ROOT = REPO / "learn" / "lab" / "asap7" / "sc6t"
REPORT_PATH = REPO / "learn" / "sim" / "reports" / "lab_asap7.json"
VARIANT_PREFIX = "lab_asap7_"

CORNERS = {
    "BC": {"lib": "FF", "temperature": "25C", "voltage": 0.77},
    "TC": {"lib": "TT", "temperature": "0C", "voltage": 0.70},
    "WC": {"lib": "SS", "temperature": "100C", "voltage": 0.63},
}
VTS = ("RVT", "LVT", "SLVT", "SRAM")
LIB_MODELS = ("NLDM", "CCS")
TRACKS = ("7p5", "6")

STAGE_ORDER = ("synth", "floorplan", "place", "cts", "route", "finish")
STAGE_HINTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "synth": (("1_synth.v", "1_2_yosys.v", "1_synth.odb"), ("1_1_yosys.json", "1_synth.json")),
    "floorplan": (
        ("2_floorplan.odb", "2_1_floorplan.odb", "2_4_floorplan_pdn.odb"),
        ("2_1_floorplan.json",),
    ),
    "place": (("3_place.odb", "3_5_place_dp.odb"), ("3_5_place_dp.json",)),
    "cts": (("4_cts.odb", "4_1_cts.odb"), ("4_1_cts.json", "4_cts.json")),
    "route": (("5_route.odb", "5_2_route.odb"), ("5_1_grt.json",)),
    "finish": (("6_final.gds", "6_final.def", "6_final.odb"), ("6_report.json",)),
}
STAGE_PREFIX = {
    "synth": "1_",
    "floorplan": "2_",
    "place": "3_",
    "cts": "4_",
    "route": "5_",
    "finish": "6_",
}

GOLD_IR_REL = Path("learn/sim/reports/dynamic_ir_flowlab.json")
GOLD_GDS_REL = Path("tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.gds")
GOLD_RPT_REL = Path("tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab/6_report.json")
GOLD_IR_SHA = "938e122b1d25a3a4064134f0fa56a04357eb571d683ecedc67f089cf0dea850a"
GOLD_GDS_SHA = "439f5eba0de2abd61d6c14328c8ac4d966dee085e9c51687b8ee09182244bcb3"
GOLD_RPT_SHA = "5cba9a7a882a0420cfd6f3b121dc078244f86e79893963d3726ab53fb26bd543"

HEAVY_DESIGNS = frozenset(
    {"aes", "aes-block", "aes_lvt", "aes-mbff", "cva6", "swerv_wrapper", "ibex", "jpeg", "jpeg_lvt"}
)

DESIGNS = {
    "gcd": {
        "config": "designs/asap7/gcd/config.mk",
        "nickname": "gcd",
        "clk_ps": 310,
        "sram": False,
    },
    "gcd-ccs": {
        "config": "designs/asap7/gcd-ccs/config.mk",
        "nickname": "gcd-ccs",
        "clk_ps": 310,
        "sram": False,
        "force_lib": "CCS",
    },
    "uart": {
        "config": "designs/asap7/uart/config.mk",
        "nickname": "uart",
        "clk_ps": 270,
        "sram": False,
    },
    "minimal": {
        "config": "designs/asap7/minimal/config.mk",
        "nickname": "minimal",
        "clk_ps": None,
        "sram": False,
    },
    "riscv32i-mock-sram": {
        "config": "designs/asap7/riscv32i-mock-sram/config.mk",
        "nickname": "riscv32i-mock-sram",
        "clk_ps": None,
        "sram": True,
    },
}


class LabAsap7Refuse(ValueError):
    """Illegal lab ASAP7 combo or locked variant."""


@dataclass(frozen=True)
class LabAsap7Spec:
    design: str = "gcd"
    corner: str = "TC"
    vt: tuple[str, ...] = ("RVT",)
    lib_model: str = "NLDM"
    track: str = "7p5"
    cluster_flops: bool = False
    clk_ps: int | None = None
    extra: str = ""

    @property
    def primary_vt(self) -> str:
        return self.vt[0]

    @property
    def variant(self) -> str:
        """Human recipe title, not a camp_* hash.

        When LAB_CLK_PS differs from the ORFS smoke period, tag the variant
        so a relaxed-clock cook does not overwrite the 310 ps / 270 ps GDS.
        """
        vt_tag = "+".join(v.lower() for v in self.vt)
        bits = [
            "lab_asap7",
            self.design.replace("-", "_"),
            self.corner.lower(),
            vt_tag,
            self.lib_model.lower(),
            self.track,
        ]
        default_clk = DESIGNS.get(self.design, {}).get("clk_ps")
        if self.clk_ps is not None and (
            default_clk is None or int(self.clk_ps) != int(default_clk)
        ):
            bits.append(f"{int(self.clk_ps)}ps")
        if self.cluster_flops:
            bits.append("mbff")
        if self.extra:
            bits.append(re.sub(r"[^a-z0-9]+", "_", self.extra.lower()).strip("_"))
        return "_".join(bits)

    @property
    def config_rel(self) -> str:
        return str(DESIGNS[self.design]["config"])

    @property
    def nickname(self) -> str:
        return str(DESIGNS[self.design]["nickname"])


def parse_vt(raw: str | tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    if raw is None or raw == "":
        return ("RVT",)
    if isinstance(raw, (tuple, list)):
        parts = [str(x).strip().upper() for x in raw if str(x).strip()]
    else:
        parts = [p.strip().upper() for p in re.split(r"[,\s+]+", str(raw)) if p.strip()]
    if not parts:
        return ("RVT",)
    for p in parts:
        if p not in VTS:
            raise LabAsap7Refuse(f"REFUSED: unknown VT {p} (want {VTS})")
    return tuple(parts)


def spec_from_env(env: dict[str, str] | None = None) -> LabAsap7Spec:
    e = env if env is not None else os.environ
    design = e.get("LAB_ASAP7_DESIGN", e.get("DESIGN", "gcd"))
    corner = e.get("CORNER", "TC").upper()
    lib_model = e.get("LIB_MODEL", "").upper() or str(DESIGNS.get(design, {}).get("force_lib") or "NLDM")
    track = e.get("ASAP7_TRACK", "7p5")
    extra = e.get("LAB_ASAP7_EXTRA", "")
    clk = e.get("LAB_CLK_PS")
    cluster = e.get("CLUSTER_FLOPS", "0") in {"1", "true", "TRUE", "yes"}
    return LabAsap7Spec(
        design=design,
        corner=corner,
        vt=parse_vt(e.get("ASAP7_USE_VT", "RVT")),
        lib_model=lib_model,
        track=track,
        cluster_flops=cluster,
        clk_ps=int(clk) if clk else None,
        extra=extra,
    )


def sc6t_ready(root: Path | None = None) -> bool:
    base = (root or REPO) / "learn" / "lab" / "asap7" / "sc6t"
    lef = base / "lef" / "asap7sc6t_26_R_1x_210923b.lef"
    return lef.is_file()


CCS_FAMILIES = ("AO", "INVBUF", "OA", "SIMPLE", "SEQ")


def _ccs_search_roots(root: Path | None = None) -> tuple[Path, ...]:
    base = root or REPO
    return (
        base / "learn/lab/asap7/ccs",
        base / "tools/OpenROAD-flow-scripts/flow/platforms/asap7/lib/CCS",
    )


def _ccs_plain(name: str) -> bool:
    """ORFS uses *_ccs_*, not CCS-A / CCS-N."""
    return bool(re.search(r"_ccs_\d", name.lower()))


def ccs_lib_files(corner: str, vt: str, root: Path | None = None) -> list[Path]:
    """One CCS liberty per family for this corner × VT, extras first."""
    if corner not in CORNERS:
        return []
    lib_tag = str(CORNERS[corner]["lib"]).upper()
    vt_u = vt.upper()
    picked: list[Path] = []
    for fam in CCS_FAMILIES:
        hit: Path | None = None
        for base in _ccs_search_roots(root):
            if not base.is_dir():
                continue
            cands = [
                p
                for p in base.rglob("*")
                if p.is_file()
                and _ccs_plain(p.name)
                and f"_{fam}_" in p.name.upper()
                and f"_{vt_u}_" in p.name.upper()
                and f"_{lib_tag}_" in p.name.upper()
                and (p.suffix == ".lib" or p.name.endswith(".lib.gz"))
            ]
            if cands:
                hit = sorted(cands, key=lambda p: p.name)[0]
                break
        if hit is not None:
            picked.append(hit)
    return picked


def ccs_ready(corner: str, vt: str, root: Path | None = None) -> bool:
    """True when the five CCS families exist for this corner × VT."""
    return len(ccs_lib_files(corner, vt, root)) >= len(CCS_FAMILIES)


def ccs_make_assignment(corner: str, vt: str, root: Path | None = None) -> str:
    """CORNER_CCS_LIB_FILES=... for the wrapper. Empty if not cookable."""
    files = ccs_lib_files(corner, vt, root)
    if len(files) < len(CCS_FAMILIES):
        return ""
    joined = " ".join(str(p) for p in files)
    return f"{corner}_CCS_LIB_FILES={joined}"


def cdl_ready(root: Path | None = None) -> bool:
    dest = (root or REPO) / "learn" / "lab" / "asap7" / "cdl"
    return dest.is_dir() and any(dest.rglob("*.cdl"))


def validate(spec: LabAsap7Spec, *, root: Path | None = None, allow_heavy: bool | None = None) -> LabAsap7Spec:
    root = root or REPO
    if spec.design not in DESIGNS:
        raise LabAsap7Refuse(f"REFUSED: unknown lab design {spec.design}")
    if spec.corner not in CORNERS:
        raise LabAsap7Refuse(f"REFUSED: CORNER={spec.corner} (want BC/TC/WC)")
    if spec.lib_model not in LIB_MODELS:
        raise LabAsap7Refuse(f"REFUSED: LIB_MODEL={spec.lib_model}")
    if spec.track not in TRACKS:
        raise LabAsap7Refuse(f"REFUSED: ASAP7_TRACK={spec.track}")
    variant = spec.variant
    if is_locked_variant(variant) or variant in LOCKED_VARIANTS:
        raise LabAsap7Refuse(f"REFUSED: FLOW_VARIANT={variant} is locked")
    if not variant.startswith(VARIANT_PREFIX):
        raise LabAsap7Refuse(f"REFUSED: lab variant must start with {VARIANT_PREFIX}")
    if "krylov" in variant.lower():
        raise LabAsap7Refuse("REFUSED: Krylov is not a lab ASAP7 variant")
    if spec.lib_model == "CCS" and not ccs_ready(spec.corner, spec.primary_vt, root):
        raise LabAsap7Refuse(
            "REFUSED: CCS liberty missing for "
            f"CORNER={spec.corner} VT={spec.primary_vt}. "
            "Need AO/INVBUF/OA/SIMPLE/SEQ. Fetch extras with "
            "learn/scripts/fetch_asap7_libextras.sh"
        )
    if spec.track == "6":
        raise LabAsap7Refuse(
            "REFUSED: 6-track is fetch-gated leftover. RTL→GDS uses 7.5-track. "
            "Run learn/scripts/fetch_asap7_sc6t.sh to store views; do not claim a 6T finish."
        )
    heavy = allow_heavy
    if heavy is None:
        heavy = os.environ.get("ALLOW_HEAVY_ANALYSIS") == "1"
    if spec.design in HEAVY_DESIGNS and not heavy:
        raise LabAsap7Refuse(
            f"REFUSED: {spec.design} is heavy. Set ALLOW_HEAVY_ANALYSIS=1 or use gcd."
        )
    cfg = root / "tools/OpenROAD-flow-scripts/flow" / spec.config_rel
    if not cfg.is_file():
        raise LabAsap7Refuse(f"REFUSED: missing {cfg}")
    return spec


def result_dir(spec: LabAsap7Spec, root: Path | None = None) -> Path:
    root = root or REPO
    return (
        root
        / "tools/OpenROAD-flow-scripts/flow/results/asap7"
        / spec.nickname
        / spec.variant
    )


def logs_dir(spec: LabAsap7Spec, root: Path | None = None) -> Path:
    root = root or REPO
    return (
        root
        / "tools/OpenROAD-flow-scripts/flow/logs/asap7"
        / spec.nickname
        / spec.variant
    )


def result_dir_for_variant(variant: str, root: Path | None = None) -> Path | None:
    """Resolve results/asap7/<nick>/<variant> without reconstructing a spec."""
    root = root or REPO
    results = root / "tools/OpenROAD-flow-scripts/flow/results/asap7"
    if not results.is_dir():
        return None
    hits = sorted(p for p in results.glob(f"*/{variant}") if p.is_dir())
    return hits[0] if hits else None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def nangate_gold_status(root: Path | None = None) -> dict[str, Any]:
    """Read-only gold check. Missing ORFS artifacts are a lock-absent warning."""
    root = root or REPO
    ir = root / GOLD_IR_REL
    gds = root / GOLD_GDS_REL
    rpt = root / GOLD_RPT_REL
    ir_ok = ir.is_file() and _sha256(ir) == GOLD_IR_SHA and "45.298" in ir.read_text()
    gds_ok = (not gds.is_file()) or _sha256(gds) == GOLD_GDS_SHA
    rpt_ok = (not rpt.is_file()) or _sha256(rpt) == GOLD_RPT_SHA
    return {
        "ir_present": ir.is_file(),
        "gds_present": gds.is_file(),
        "rpt_present": rpt.is_file(),
        "ir_ok": ir_ok,
        "gds_ok": gds_ok,
        "rpt_ok": rpt_ok,
        "nangate_lock_absent": not gds.is_file(),
        "untouched": ir_ok and gds_ok and rpt_ok,
    }


def assert_nangate_gold_untouched(root: Path | None = None, *, require_orfs: bool = False) -> dict[str, Any]:
    st = nangate_gold_status(root)
    if not st["ir_ok"]:
        raise LabAsap7Refuse("REFUSED: Nangate gold IR missing or restamped")
    if require_orfs and st["nangate_lock_absent"]:
        raise LabAsap7Refuse("REFUSED: locked FlowLab GDS missing")
    if not st["gds_ok"]:
        raise LabAsap7Refuse("REFUSED: locked FlowLab GDS restamped")
    if not st["rpt_ok"]:
        raise LabAsap7Refuse("REFUSED: locked FlowLab 6_report restamped")
    return st


def _first_file(folder: Path, names: tuple[str, ...]) -> Path | None:
    if not folder.is_dir():
        return None
    for name in names:
        p = folder / name
        if p.is_file():
            return p
    return None


def _prefix_hit(folder: Path, prefix: str) -> Path | None:
    if not folder.is_dir():
        return None
    hits = sorted(p for p in folder.iterdir() if p.is_file() and p.name.startswith(prefix))
    return hits[0] if hits else None


def stage_ledger_at(nickname: str, variant: str, root: Path | None = None) -> dict[str, Any]:
    """Per-stage artifacts for one lab_asap7_* cook. No design-name branch."""
    root = root or REPO
    res = root / "tools/OpenROAD-flow-scripts/flow/results/asap7" / nickname / variant
    logs = root / "tools/OpenROAD-flow-scripts/flow/logs/asap7" / nickname / variant
    out: dict[str, Any] = {}
    for name in STAGE_ORDER:
        res_names, log_names = STAGE_HINTS[name]
        art = _first_file(res, res_names) or _first_file(logs, log_names)
        if art is None:
            art = _prefix_hit(res, STAGE_PREFIX[name]) or _prefix_hit(logs, STAGE_PREFIX[name])
        note: dict[str, Any] = {}
        if name == "place":
            dp = logs / "3_5_place_dp.json"
            if dp.is_file():
                from dse.f6_finish import parse_place_dp

                note = parse_place_dp(dp)
        elif name == "route":
            grt = logs / "5_1_grt.json"
            if grt.is_file():
                from dse.f6_finish import parse_grt

                note = parse_grt(grt)
        out[name] = {
            "done": art is not None,
            "artifact": str(art) if art is not None else None,
            "mtime": art.stat().st_mtime if art is not None else None,
            "note": note,
        }
    return out


def stage_ledger(spec: LabAsap7Spec, root: Path | None = None) -> dict[str, Any]:
    return stage_ledger_at(spec.nickname, spec.variant, root)


def stopped_at(ledger: dict[str, Any], *, gds_live: bool) -> str | None:
    if gds_live:
        return None
    for name in STAGE_ORDER:
        if not (ledger.get(name) or {}).get("done"):
            return name
    return None


def default_plan_specs() -> list[LabAsap7Spec]:
    """Cheap-first default cooks. uart relaxed is appended by the runner."""
    return [
        LabAsap7Spec(),
        LabAsap7Spec(corner="BC"),
        LabAsap7Spec(corner="WC"),
        LabAsap7Spec(design="gcd-ccs", corner="BC", lib_model="CCS"),
        LabAsap7Spec(lib_model="CCS", corner="TC"),
        LabAsap7Spec(lib_model="CCS", corner="WC"),
        LabAsap7Spec(vt=("RVT", "LVT")),
        LabAsap7Spec(cluster_flops=True),
        LabAsap7Spec(clk_ps=430),
        LabAsap7Spec(clk_ps=480),
        LabAsap7Spec(design="uart"),
    ]


def ceil_clk_10ps(period_min: float) -> int:
    return int(math.ceil(float(period_min) / 10.0) * 10)


def uart_relaxed_spec(root: Path | None = None) -> LabAsap7Spec:
    smoke = LabAsap7Spec(design="uart")
    qor = collect_report(smoke, root=root).get("qor") or {}
    pmin = qor.get("period_min_ps")
    clk = ceil_clk_10ps(float(pmin)) if pmin is not None else 290
    if clk <= int(DESIGNS["uart"]["clk_ps"] or 270):
        clk = 290
    return LabAsap7Spec(design="uart", clk_ps=clk)


def plan_refuse(spec: LabAsap7Spec, root: Path | None = None) -> str | None:
    """Named refuse for the default plan. Does not cook."""
    root = root or REPO
    try:
        validate(spec, root=root, allow_heavy=False)
    except LabAsap7Refuse as exc:
        return str(exc)
    return None


def closure_ladder(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        design = str(r.get("design") or "")
        by.setdefault(design, []).append(
            {
                "variant": r.get("variant"),
                "clk_ps": r.get("clk_ps"),
                "wns_ps": r.get("wns_ps"),
                "timing_closed": r.get("timing_closed"),
            }
        )
    for items in by.values():
        items.sort(key=lambda x: (x["clk_ps"] is None, float(x["clk_ps"] or 0)))
    return by


def flowlab_untouched(root: Path | None = None) -> bool:
    """Locked Nangate FlowLab tree still exists and is not our write target."""
    root = root or REPO
    locked = root / "tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.gds"
    return locked.is_file()


def _metrics(qor: dict) -> dict:
    def g(*keys: str):
        for k in keys:
            if k in qor and qor[k] is not None:
                return qor[k]
        return None

    return {
        "wns_ps": g("finish__timing__setup__ws"),
        "tns_ps": g("finish__timing__setup__tns"),
        "setup_violations": g("finish__timing__drv__setup_violation_count"),
        "area_um2": g("finish__design__instance__area__stdcell", "finish__design__instance__area"),
        "die_um2": g("finish__design__die__area"),
        "power_w": g("finish__power__total"),
        "leakage_w": g("finish__power__leakage__total"),
        "ir_vdd_worst_v": g("finish__design_powergrid__drop__worst__net:VDD__corner:default"),
        "util": g("finish__design__instance__utilization"),
    }


def collect_report(spec: LabAsap7Spec, *, root: Path | None = None, extra: dict | None = None) -> dict:
    root = root or REPO
    out = result_dir(spec, root)
    gds = out / "6_final.gds"
    log_rep = (
        root
        / "tools/OpenROAD-flow-scripts/flow/logs/asap7"
        / spec.nickname
        / spec.variant
        / "6_report.json"
    )
    rep = log_rep if log_rep.is_file() else out / "6_report.json"
    qor: dict = {}
    if rep.is_file():
        try:
            qor = json.loads(rep.read_text())
        except json.JSONDecodeError:
            qor = {}
    metrics = _metrics(qor)
    clk = spec.clk_ps if spec.clk_ps is not None else DESIGNS[spec.design].get("clk_ps")
    wns = metrics.get("wns_ps")
    if clk is not None and wns is not None:
        period_min = float(clk) + max(0.0, -float(wns))
        metrics["period_min_ps"] = period_min
        metrics["fmax_ghz"] = (1000.0 / period_min) if period_min > 0 else None
    pw = metrics.get("power_w")
    lk = metrics.get("leakage_w")
    ir = metrics.get("ir_vdd_worst_v")
    metrics["power_mw"] = (float(pw) * 1e3) if pw is not None else None
    metrics["leakage_nw"] = (float(lk) * 1e9) if lk is not None else None
    metrics["ir_drop_vdd_mv"] = (float(ir) * 1e3) if ir is not None else None
    metrics["timing_closed"] = wns is not None and float(wns) >= 0
    gds_live = gds.is_file()
    extra = extra or {}
    exit_code = extra.get("exit_code")
    if exit_code is None:
        ok = gds_live
    else:
        ok = bool(gds_live and int(exit_code) == 0)
    ledger = stage_ledger(spec, root)
    gold = nangate_gold_status(root)
    payload = {
        "ok": ok,
        "gds_live": gds_live,
        "stopped_at": stopped_at(ledger, gds_live=gds_live),
        "stages": ledger,
        "nangate_lock_absent": gold["nangate_lock_absent"],
        "surface": "lab",
        "platform": "asap7",
        "predictive": True,
        "manufacturable": False,
        "product_win": False,
        "comparable_to_gold_ir": False,
        "variant": spec.variant,
        "design": spec.design,
        "nickname": spec.nickname,
        "corner": spec.corner,
        "vt": list(spec.vt),
        "lib_model": spec.lib_model,
        "track": spec.track,
        "cluster_flops": spec.cluster_flops,
        "clk_ps": clk,
        "gds": str(gds) if gds.is_file() else None,
        "gds_bytes": gds.stat().st_size if gds.is_file() else None,
        "metrics_source": str(rep) if rep.is_file() else None,
        "leftover": {
            "sram": "FakeRAM2.0" if DESIGNS[spec.design].get("sram") else None,
            "ccs_partial": spec.lib_model == "CCS" and spec.corner != "BC",
            "lvs": (
                "leftover-named cell-vs-CDL; not Calibre"
                if cdl_ready(root)
                else "no LVS in ORFS slim pack"
            ),
            "fake_mbff": spec.cluster_flops,
            "timing_open": bool(wns is not None and float(wns) < 0),
            "six_track": "fetch-gated, not a finish",
            "drc": "community KLayout deck; not Calibre",
            "wc_die": (
                "310 ps + default 65% util can fail CTS legalization; "
                "wrapper defaults CORE_UTILIZATION=40 on WC"
            ),
            "uart_slang": (
                "ORFS uart wants slang.so; wrapper uses Yosys when slang.so is missing"
            ),
        },
        "qor": metrics,
        "note": (
            "ASAP7 lab cook. Predictive FinFET. Not a product win. "
            "Live metrics only — no gold stamp."
        ),
    }
    if extra:
        payload.update(extra)
    return payload


def write_report(payload: dict, root: Path | None = None) -> Path:
    root = root or REPO
    path = root / "learn" / "sim" / "reports" / "lab_asap7.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    write_folio(root)
    return path


def _folio_clk_ps(variant: str, nickname: str) -> int | None:
    tagged = re.search(r"_(\d+)ps(?:_|$)", variant)
    if tagged:
        return int(tagged.group(1))
    for info in DESIGNS.values():
        if info.get("nickname") == nickname:
            clk = info.get("clk_ps")
            return int(clk) if clk is not None else None
    return None


def scan_folio(root: Path | None = None) -> list[dict]:
    """Live cooks already on disk. Last cook only is lab_asap7.json."""
    root = root or REPO
    results = root / "tools/OpenROAD-flow-scripts/flow/results/asap7"
    rows: list[dict] = []
    if not results.is_dir():
        return rows
    for gds in sorted(results.glob("*/*/6_final.gds")):
        variant = gds.parent.name
        if not variant.startswith(VARIANT_PREFIX):
            continue
        nickname = gds.parent.parent.name
        log_rep = (
            root
            / "tools/OpenROAD-flow-scripts/flow/logs/asap7"
            / nickname
            / variant
            / "6_report.json"
        )
        qor: dict = {}
        if log_rep.is_file():
            try:
                qor = json.loads(log_rep.read_text())
            except json.JSONDecodeError:
                qor = {}
        metrics = _metrics(qor)
        clk = _folio_clk_ps(variant, nickname)
        wns = metrics.get("wns_ps")
        period_min = None
        fmax = None
        if clk is not None and wns is not None:
            period_min = float(clk) + max(0.0, -float(wns))
            fmax = (1000.0 / period_min) if period_min > 0 else None
        pw = metrics.get("power_w")
        lk = metrics.get("leakage_w")
        ir = metrics.get("ir_vdd_worst_v")
        ledger = stage_ledger_at(nickname, variant, root)
        gds_live = True
        rows.append(
            {
                "variant": variant,
                "design": nickname,
                "clk_ps": clk,
                "wns_ps": wns,
                "timing_closed": wns is not None and float(wns) >= 0,
                "area_um2": metrics.get("area_um2"),
                "power_mw": (float(pw) * 1e3) if pw is not None else None,
                "leakage_nw": (float(lk) * 1e9) if lk is not None else None,
                "ir_drop_vdd_mv": (float(ir) * 1e3) if ir is not None else None,
                "period_min_ps": period_min,
                "fmax_ghz": fmax,
                "gds_bytes": gds.stat().st_size,
                "gds_live": gds_live,
                "stopped_at": stopped_at(ledger, gds_live=gds_live),
                "stages": {k: {"done": v.get("done"), "artifact": v.get("artifact")} for k, v in ledger.items()},
            }
        )
    return rows


def write_folio(root: Path | None = None) -> Path:
    root = root or REPO
    dest = root / "learn" / "sim" / "reports" / "lab_asap7_folio.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    cooks = scan_folio(root)
    dest.write_text(
        json.dumps(
            {
                "note": "Live folio — last cook is lab_asap7.json. No gold stamp.",
                "cooks": cooks,
                "closure_ladder": closure_ladder(cooks),
                "track6": {
                    "status": "GAP",
                    "reason": "ASAP7_TRACK=6 refused until a second 6T platform exists",
                },
            },
            indent=2,
        )
        + "\n"
    )
    return dest


def write_constraint_sdc(path: Path, clk_ps: float, nickname: str) -> Path:
    """ORFS-style SDC. Liberty time_unit is 1ps. Not the course 0.46 ns file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"current_design {nickname}\n"
        "set clk_name core_clock\n"
        "set clk_port_name clk\n"
        f"set clk_period {float(clk_ps)}\n"
        "set clk_io_pct 0.2\n"
        "set clk_port [get_ports $clk_port_name]\n"
        "create_clock -name $clk_name -period $clk_period $clk_port\n"
        "set non_clock_inputs [all_inputs -no_clocks]\n"
        "set_input_delay  [expr $clk_period * $clk_io_pct] -clock $clk_name $non_clock_inputs\n"
        "set_output_delay [expr $clk_period * $clk_io_pct] -clock $clk_name [all_outputs]\n"
    )
    return path


def make_env(spec: LabAsap7Spec) -> dict[str, str]:
    env = os.environ.copy()
    env["DESIGN"] = spec.design
    env["LAB_ASAP7_DESIGN"] = spec.design
    env["FLOW_VARIANT"] = spec.variant
    env["PLATFORM"] = "asap7"
    env["CORNER"] = spec.corner
    env["LIB_MODEL"] = spec.lib_model
    env["ASAP7_USE_VT"] = " ".join(spec.vt)
    env["ASAP7_TRACK"] = spec.track
    env["CLUSTER_FLOPS"] = "1" if spec.cluster_flops else "0"
    if spec.clk_ps is not None:
        env["LAB_CLK_PS"] = str(spec.clk_ps)
    return env


def cook(
    spec: LabAsap7Spec | None = None,
    *,
    target: str = "finish",
    root: Path | None = None,
    timeout_s: int | None = None,
) -> dict:
    """Run scripts/run_lab_asap7.sh. One heavy cook at a time."""
    root = root or REPO
    spec = validate(spec or spec_from_env(), root=root)
    extra: dict = {}
    if not flowlab_untouched(root):
        extra["nangate_lock_absent"] = True
    script = root / "scripts" / "run_lab_asap7.sh"
    proc = subprocess.run(
        ["bash", str(script), target],
        cwd=str(root),
        env=make_env(spec),
        text=True,
        capture_output=True,
        timeout=timeout_s,
    )
    extra["exit_code"] = proc.returncode
    extra["stderr_tail"] = (proc.stderr or "")[-2000:]
    payload = collect_report(spec, root=root, extra=extra)
    payload["ok"] = bool(payload.get("gds") and proc.returncode == 0)
    write_report(payload, root)
    if proc.returncode != 0:
        raise LabAsap7Refuse(f"cook failed ({proc.returncode}): {proc.stderr[-800:]}")
    return payload
