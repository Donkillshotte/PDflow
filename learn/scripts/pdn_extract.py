#!/usr/bin/env python3
"""Replaceable PDN extraction layer.

Backends:
  write_pg_spice  — OpenROAD PDNSim R mesh + I_avg + bump V (GCD default)
  tech LEF        — metal WIDTH / THICKNESS / RPERSQ for EM J
  SPEF            — probed; signal OpenRCX on this GCD has no VDD PDN C

Not a DEF+LEF Rsq extractor and not a fork of OpenROAD PSM.
Never synthesizes PDN C from signal SPEF names.
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
SPEF_VDD = re.compile(r"\bVDD\b|\bVSS\b|\bVDDE\b", re.I)

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
        elif "RPERSQ" in up:
            nums = re.findall(r"[0-9.eE+-]+", s)
            if nums:
                layers[cur]["rpersq"] = float(nums[-1])
        elif up.startswith("TYPE"):
            layers[cur]["type"] = s.replace(";", "").split()[-1].upper()
    routing = {k: v for k, v in layers.items() if str(v.get("type", "")).startswith("ROUT")}
    out_layers = routing or layers
    return {
        "path": str(p),
        "dbu_per_um": dbu,
        "layers": out_layers,
        "n_routing_layers": len(out_layers),
        "status": "READY" if routing else "GAP",
        "via": "tech LEF WIDTH/THICKNESS/RPERSQ — strap width is inferred from R, not min WIDTH",
    }


def probe_spef(path: Path | None) -> dict:
    """Signal SPEF is not a PDN extract. Do not map pin C onto write_pg_spice nodes."""
    if path is None or not Path(path).is_file():
        return {
            "status": "GAP",
            "path": None,
            "has_pg_net": False,
            "note": "no SPEF — N2 C stays lumped c_decap, not OpenRCX PDN C",
        }
    p = Path(path)
    text = p.read_text(errors="replace")[:400_000]
    has_pg = bool(SPEF_VDD.search(text))
    n_dnet = text.upper().count("*D_NET")
    return {
        # GAP until a backend actually stamps PG C onto write_pg_spice nodes.
        # A VDD string in SPEF is not an extract.
        "status": "GAP",
        "path": str(p),
        "has_pg_net": has_pg,
        "n_d_net_head": n_dnet,
        "note": (
            "SPEF mentions VDD/VSS — still not stamped onto the PDN; lumped c_decap remains"
            if has_pg
            else "signal SPEF (no VDD net) — not PDN capacitance; lumped c_decap remains"
        ),
    }


def extract_pdn(
    spice: Path,
    *,
    lef: Path | None = None,
    spef: Path | None = None,
) -> dict:
    """One extract record. Callers should not parse SPICE themselves."""
    resistors, currents, voltages = parse_spice(spice)
    tech = parse_tech_lef(lef)
    spef_m = probe_spef(spef)
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
        "status": "READY",
        "note": "OpenROAD write_pg_spice R mesh; LEF for EM J; SPEF PDN C is GAP (never mapped from signal nets)",
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
        "spef": ext.get("spef"),
        "note": ext.get("note"),
    }
