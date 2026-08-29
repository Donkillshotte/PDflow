#!/usr/bin/env python3
"""Replaceable PDN extraction layer.

Backends:
  write_pg_spice  — OpenROAD PDNSim R mesh + I_avg + bump V (GCD default)
  tech LEF        — metal WIDTH / THICKNESS / RPERSQ for EM J
  SPEF            — PG *D_NET *CAP name-joined onto write_pg_spice nodes (GCD OpenRCX has no VDD)

Not a DEF+LEF Rsq extractor and not a fork of OpenROAD PSM.
Never synthesizes PDN C from signal SPEF names.
On-die L is Grover partial self plus cutoff partial mutual on same-layer straps;
not stamped into the SPD companion unless the caller asks for the descriptor.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

R_RE = re.compile(r"^\S+\s+(\S+)\s+(\S+)\s+R=([0-9eE.+-]+)")
I_RE = re.compile(r"^\S+\s+(\S+)\s+\S+\s+DC\s+([0-9eE.+-]+)", re.I)
V_RE = re.compile(r"^\S+\s+(\S+)\s+\S+\s+DC\s+([0-9eE.+-]+)", re.I)
COORD_RE = re.compile(r"(ITermNode|Node)_metal(\d+)_(-?\d+)_(-?\d+)")
LAYER_HDR = re.compile(r"^LAYER\s+(\S+)\s*$", re.I)
PG_BARE = re.compile(r"^(?:VDD|VSS|VDDE|VCC|GND|VPWR|VGND)(?:\[\d+\])?$", re.I)
SINK_RE = re.compile(r"^\*\s*Sink for\s+(\S+)/(\S+)\s*$", re.I)
_VSS_PINS = {"VSS", "VGND", "GND", "VSSWE", "VEE"}
_VDD_PINS = {"VDD", "VPWR", "VCC", "VDDE", "VDDWE"}
NAME_MAP_RE = re.compile(r"^\*(\d+)\s+(\S+)\s*$")
D_NET_RE = re.compile(r"^\*D_NET\s+(\S+)\s+", re.I)
C_UNIT_RE = re.compile(r"^\*C_UNIT\s+([0-9.eE+-]+)\s+(\S+)", re.I)
MAPPED_NODE_RE = re.compile(r"^(\*\d+)(.*)$")

_C_UNIT_F = {
    "F": 1.0,
    "UF": 1e-6,
    "NF": 1e-9,
    "PF": 1e-12,
    "FF": 1e-15,
}

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_LEF = (
    _ROOT
    / "tools"
    / "OpenROAD-flow-scripts"
    / "flow"
    / "platforms"
    / "nangate45"
    / "lef"
    / "NangateOpenCellLibrary.tech.lef"
)


def parse_spice(path: Path):
    """OpenROAD write_pg_spice: R= / I DC / V DC. Same contract as the old pdn_transient parser."""
    resistors = []
    currents = defaultdict(float)
    voltages = {}
    for raw in Path(path).read_text().splitlines():
        s = raw.strip()
        if not s or s.startswith("*") or s.startswith("."):
            continue
        k = s[0].upper()
        if k == "R":
            m = R_RE.match(s)
            if not m:
                continue
            a, b, r = m.group(1), m.group(2), float(m.group(3))
            resistors.append((a, b, max(r, 1e-12)))
        elif k == "I":
            m = I_RE.match(s)
            if m:
                currents[m.group(1)] += abs(float(m.group(2)))
        elif k == "V":
            m = V_RE.match(s)
            if m:
                voltages[m.group(1)] = float(m.group(2))
    if not resistors or not voltages:
        raise SystemExit(f"SPICE incompleto: R={len(resistors)} V={len(voltages)}")
    return resistors, dict(currents), voltages


def parse_pg_sinks(path: Path) -> dict:
    """OpenROAD write_pg_spice '* Sink for inst/pin' joined to the next I element.

    This is the PDNSim comment contract, not an RTL VCD → ITerm invention.
    """
    pending = None
    sinks: dict[str, dict] = {}
    if not Path(path).is_file():
        return sinks
    for raw in Path(path).read_text().splitlines():
        s = raw.strip()
        sm = SINK_RE.match(s)
        if sm:
            pending = (sm.group(1), sm.group(2))
            continue
        if not s or s.startswith("*") or s.startswith("."):
            continue
        if s[0].upper() != "I" or pending is None:
            continue
        m = I_RE.match(s)
        if not m:
            pending = None
            continue
        node = m.group(1)
        inst, pin = pending
        sinks[node] = {"inst": inst, "pin": pin, "node": node, "i_avg": abs(float(m.group(2)))}
        pending = None
    return sinks


def pair_pg_rails(vdd_sinks: dict, vss_sinks: dict) -> dict:
    """Pair VDD/VSS ITerms by spice sink instance. CMOS I_vdd returns as I_vss.

    Block-diagonal dual-rail MNA: no rail-to-rail C. Not a second physics model.
    """
    by_inst_vdd: dict[str, dict] = {}
    for rec in vdd_sinks.values():
        pin = str(rec.get("pin") or "").upper()
        if pin in _VSS_PINS:
            continue
        by_inst_vdd[str(rec["inst"])] = rec
    by_inst_vss: dict[str, dict] = {}
    for rec in vss_sinks.values():
        pin = str(rec.get("pin") or "").upper()
        if pin in _VDD_PINS:
            continue
        by_inst_vss[str(rec["inst"])] = rec
    pairs = []
    for inst, vd in by_inst_vdd.items():
        vs = by_inst_vss.get(inst)
        if vs is None:
            continue
        pairs.append(
            {
                "inst": inst,
                "vdd_node": vd["node"],
                "vss_node": vs["node"],
                "vdd_pin": vd["pin"],
                "vss_pin": vs["pin"],
            }
        )
    return {
        "status": "READY" if pairs else "GAP",
        "n_pairs": len(pairs),
        "n_vdd_sinks": len(vdd_sinks),
        "n_vss_sinks": len(vss_sinks),
        "pairs": pairs,
        "via": "write_pg_spice '* Sink for inst/pin' on VDD and VSS (not RTL name-join)",
        "note": (
            "I_cell leaves VDD and enters VSS; G is block-diagonal (no rail-to-rail C). "
            "VDD gold TRAN is unchanged."
        ),
    }


def remap_events_to_rail(events: list, vdd_idx: dict, vss_idx: dict, pairs: list) -> list:
    """Copy VDD I(t) events onto paired VSS nodes. Unpaired events are dropped."""
    inv_vdd = {int(i): n for n, i in vdd_idx.items()}
    vss_of_vdd = {p["vdd_node"]: p["vss_node"] for p in pairs}
    out = []
    for ev in events:
        node = inv_vdd.get(int(ev["idx"]))
        if node is None:
            continue
        vss_node = vss_of_vdd.get(node)
        if vss_node is None or vss_node not in vss_idx:
            continue
        rec = dict(ev)
        rec["idx"] = int(vss_idx[vss_node])
        rec["rail"] = "VSS"
        rec["vdd_node"] = node
        rec["vss_node"] = vss_node
        out.append(rec)
    return out


def node_xy_dbu(name: str) -> tuple[float, float] | None:
    m = COORD_RE.search(name)
    if not m:
        return None
    return float(m.group(3)), float(m.group(4))


def layer_of(name: str) -> str | None:
    m = COORD_RE.search(name)
    return f"metal{m.group(2)}" if m else None


def parse_tech_lef(path: Path | None) -> dict:
    """Routing-layer WIDTH (µm), THICKNESS (µm), RPERSQ (ohm/sq). First WIDTH after LAYER."""
    p = Path(path) if path else _DEFAULT_LEF
    if not p.is_file():
        return {"path": None, "dbu_per_um": 2000.0, "layers": {}, "status": "GAP"}
    layers: dict[str, dict] = {}
    dbu = 2000.0
    cur = None
    saw_width = False
    for raw in p.read_text(errors="replace").splitlines():
        s = raw.strip()
        if s.upper().startswith("DATABASE MICRONS"):
            parts = s.replace(";", "").split()
            try:
                dbu = float(parts[-1])
            except (ValueError, IndexError):
                pass
            continue
        hm = LAYER_HDR.match(s.rstrip(" ;"))
        if hm:
            cur = hm.group(1)
            saw_width = False
            layers.setdefault(cur, {})
            continue
        if cur is None:
            continue
        if s.upper().startswith("END ") and s.split()[-1] == cur:
            cur = None
            continue
        up = s.upper()
        wm = re.match(r"WIDTH\s+([0-9.]+)\s*;", s, re.I)
        if wm and not saw_width:
            layers[cur]["width_um"] = float(wm.group(1))
            saw_width = True
        elif up.startswith("THICKNESS"):
            nums = re.findall(r"[0-9.]+", s)
            if nums:
                layers[cur]["thickness_um"] = float(nums[0])
        elif up.startswith("HEIGHT"):
            nums = re.findall(r"[0-9.]+", s)
            if nums:
                layers[cur]["height_um"] = float(nums[0])
        elif "RPERSQ" in up:
            nums = re.findall(r"[0-9.eE+-]+", s)
            if nums:
                layers[cur]["rpersq"] = float(nums[-1])
        elif up.startswith("RESISTANCE"):
            nums = re.findall(r"[0-9.eE+-]+", s)
            if nums:
                layers[cur]["r_ohm"] = float(nums[-1])
        elif up.startswith("TYPE"):
            layers[cur]["type"] = s.replace(";", "").split()[-1].upper()
    routing = {k: v for k, v in layers.items() if str(v.get("type", "")).startswith("ROUT")}
    cuts = {k: v for k, v in layers.items() if str(v.get("type", "")).upper() == "CUT"}
    out_layers = routing or layers
    return {
        "path": str(p),
        "dbu_per_um": dbu,
        "layers": out_layers,
        "cuts": cuts,
        "n_routing_layers": len(out_layers),
        "n_cut_layers": len(cuts),
        "status": "READY" if routing else "GAP",
        "via": "tech LEF WIDTH/THICKNESS/HEIGHT/RPERSQ + CUT WIDTH/R — strap w from R, via G_th from HEIGHT/CUT",
    }


def spice_node_set(resistors, currents, voltages) -> set[str]:
    nodes: set[str] = set()
    for a, b, _ in resistors:
        if a != "0":
            nodes.add(a)
        if b != "0":
            nodes.add(b)
    nodes.update(n for n in currents if n != "0")
    nodes.update(n for n in voltages if n != "0")
    return nodes


def _c_unit_to_f(scale: float, unit: str) -> float:
    u = unit.upper().rstrip(";")
    return float(scale) * _C_UNIT_F.get(u, 1e-12)


def _is_pg_net(name: str) -> bool:
    if not name:
        return False
    bare = name.replace("\\", "").split("/")[-1].split(":")[0]
    return bool(PG_BARE.fullmatch(bare))


def _resolve_spef_token(tok: str, namemap: dict[str, str]) -> str:
    m = MAPPED_NODE_RE.match(tok)
    if m and m.group(1) in namemap:
        return namemap[m.group(1)] + m.group(2)
    return namemap.get(tok, tok)


def _join_spice(name: str, spice: set[str]) -> str | None:
    """Name-join only. Never coordinate-map a signal pin onto a PDN node."""
    if not name or not spice:
        return None
    for cand in (name, name.replace("\\", "")):
        if cand in spice:
            return cand
    return None


def stamp_spef_pg_c(path: Path | None, spice_nodes: set[str] | None = None) -> dict:
    """Stamp *CAP from PG *D_NET onto matching write_pg_spice nodes.

    READY only when at least one Farad is added to a spice node. Signal *D_NET
    is ignored (no silent OpenRCX pin-C → PDN map). Two-node CAP on two PDN
    nodes is lumped C/2 on each (the BE operator is diagonal C). Coupling to an
    unmapped node is treated as grounded C on the mapped end.
    """
    spice = set(spice_nodes or ())
    empty = {
        "status": "GAP",
        "path": None if path is None else str(path),
        "has_pg_net": False,
        "n_pg_net": 0,
        "n_stamped": 0,
        "c_sum_f": 0.0,
        "c_unit_f": 1e-12,
        "node_c": {},
        "via": "SPEF PG *D_NET *CAP name-joined onto write_pg_spice nodes",
        "note": "no SPEF — N2 C stays lumped c_decap, not OpenRCX PDN C",
    }
    if path is None or not Path(path).is_file():
        return empty

    namemap: dict[str, str] = {}
    in_name_map = False
    in_cap = False
    net_is_pg = False
    n_pg_net = 0
    c_scale = 1e-12
    node_c: dict[str, float] = {}

    def add_c(spice_name: str, farad: float) -> None:
        if farad == 0.0:
            return
        node_c[spice_name] = node_c.get(spice_name, 0.0) + farad

    with Path(path).open(errors="replace") as fh:
        for raw in fh:
            s = raw.strip()
            if not s:
                continue
            if s.startswith("*C_UNIT"):
                um = C_UNIT_RE.match(s)
                if um:
                    c_scale = _c_unit_to_f(float(um.group(1)), um.group(2))
                continue
            if s.startswith("*NAME_MAP"):
                in_name_map = True
                in_cap = False
                continue
            if in_name_map:
                mm = NAME_MAP_RE.match(s)
                if mm:
                    namemap[f"*{mm.group(1)}"] = mm.group(2)
                    continue
                in_name_map = False
            dm = D_NET_RE.match(s)
            if dm:
                net = _resolve_spef_token(dm.group(1), namemap)
                net_is_pg = _is_pg_net(net)
                if net_is_pg:
                    n_pg_net += 1
                in_cap = False
                continue
            up = s.upper()
            if up.startswith("*CAP"):
                in_cap = True
                continue
            if up.startswith("*RES") or up.startswith("*END") or up.startswith("*CONN") or up.startswith("*D_NET"):
                in_cap = False
                if up.startswith("*END"):
                    net_is_pg = False
                continue
            if not in_cap or not net_is_pg:
                continue
            parts = s.split()
            if len(parts) < 3:
                continue
            try:
                val = float(parts[-1]) * c_scale
            except ValueError:
                continue
            if val == 0.0:
                continue
            toks = parts[1:-1]
            mapped = []
            for tok in toks:
                joined = _join_spice(_resolve_spef_token(tok, namemap), spice)
                if joined:
                    mapped.append(joined)
            if len(toks) == 1 and len(mapped) == 1:
                add_c(mapped[0], val)
            elif len(toks) == 2 and len(mapped) == 2:
                add_c(mapped[0], 0.5 * val)
                add_c(mapped[1], 0.5 * val)
            elif len(toks) == 2 and len(mapped) == 1:
                add_c(mapped[0], val)

    n_stamped = len(node_c)
    c_sum = float(sum(node_c.values()))
    has_pg = n_pg_net > 0
    if n_stamped > 0:
        status = "READY"
        note = (
            f"stamped {n_stamped} PG nodes, C_sum={c_sum:.4e} F "
            f"({n_pg_net} PG *D_NET); added to lumped c_decap, not a replacement"
        )
    elif has_pg:
        status = "GAP"
        note = (
            f"{n_pg_net} PG *D_NET in SPEF but 0 name-joins to write_pg_spice nodes "
            "— lumped c_decap remains; no coordinate map"
        )
    else:
        status = "GAP"
        note = "signal SPEF (no VDD/VSS *D_NET) — not PDN capacitance; lumped c_decap remains"

    return {
        "status": status,
        "path": str(path),
        "has_pg_net": has_pg,
        "n_pg_net": n_pg_net,
        "n_stamped": n_stamped,
        "c_sum_f": c_sum,
        "c_unit_f": c_scale,
        "node_c": node_c,
        "via": "SPEF PG *D_NET *CAP name-joined onto write_pg_spice nodes",
        "note": note,
    }


def probe_spef(path: Path | None, spice_nodes: set[str] | None = None) -> dict:
    """SPEF PDN C. GAP until *CAP from a PG *D_NET is stamped onto spice nodes."""
    return stamp_spef_pg_c(path, spice_nodes)


def extract_pdn(
    spice: Path,
    *,
    lef: Path | None = None,
    spef: Path | None = None,
) -> dict:
    """One extract record. Callers should not parse SPICE themselves."""
    resistors, currents, voltages = parse_spice(spice)
    tech = parse_tech_lef(lef)
    nodes = spice_node_set(resistors, currents, voltages)
    spef_m = stamp_spef_pg_c(spef, nodes)
    spef_ready = spef_m.get("status") == "READY"
    from pdn_em import estimate_on_die_L

    on_die = estimate_on_die_L(resistors, tech)
    return {
        "backend": "write_pg_spice",
        "spice": str(spice),
        "resistors": resistors,
        "currents": currents,
        "voltages": voltages,
        "n_r": len(resistors),
        "n_i": len(currents),
        "n_v": len(voltages),
        "n_layers": int(tech.get("n_routing_layers") or len(tech.get("layers") or {})),
        "tech": tech,
        "spef": spef_m,
        "on_die_l": on_die,
        "status": "READY",
        "note": (
            "OpenROAD write_pg_spice R mesh; LEF for EM J; "
            + (
                f"SPEF PG C stamped on {spef_m.get('n_stamped')} nodes"
                if spef_ready
                else "SPEF PG C is GAP (never mapped from signal nets)"
            )
            + (
                f"; Grover on-die L on {on_die.get('n_stamped')} straps"
                if on_die.get("status") == "READY"
                else "; on-die L GAP"
            )
        ),
    }


def summarize_extract(ext: dict) -> dict:
    """JSON-safe extract record. Never includes the resistor list."""
    tech = ext.get("tech") or {}
    layers = tech.get("layers") or {}
    return {
        "status": ext.get("status"),
        "backend": ext.get("backend"),
        "spice": ext.get("spice"),
        "n_r": ext.get("n_r"),
        "n_i": ext.get("n_i"),
        "n_v": ext.get("n_v"),
        "n_layers": ext.get("n_layers") or len(layers),
        "tech": {
            "status": tech.get("status"),
            "path": tech.get("path"),
            "dbu_per_um": tech.get("dbu_per_um"),
            "via": tech.get("via"),
            "n_routing_layers": tech.get("n_routing_layers") or len(layers),
            "rpersq": {k: v.get("rpersq") for k, v in layers.items() if v.get("rpersq") is not None},
            "thickness_um": {
                k: v.get("thickness_um") for k, v in layers.items() if v.get("thickness_um") is not None
            },
        },
        "spef": {k: v for k, v in (ext.get("spef") or {}).items() if k != "node_c"},
        "on_die_l": {k: v for k, v in (ext.get("on_die_l") or {}).items() if k not in ("branches", "mutual")},
        "note": ext.get("note"),
    }
