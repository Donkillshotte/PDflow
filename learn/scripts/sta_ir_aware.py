#!/usr/bin/env python3
"""IR-aware STA on the official GCD finish — NLDM path × per-cell V.

Joins OpenSTA worst-path gate delays to ITerm voltages from the Dynamic IR
map (current_run). Scales only gate delay: delay_ir = delay * (Vdd/V_inst)^α.
Nets stay nominal. This is not a second liberty at Vmin, not CCS, not
PrimeTime/Tempus voltage-aware STA, and it does not restamp gold 45.298 mV.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from pdn_activity import norm_inst
from pdn_dynamic import path_ir_timing
from pdn_extract import parse_pg_sinks

VDD_DEFAULT = 1.1
ALPHA_DEFAULT = 1.3
GOLD_IR_MV = 45.298
_REPO = Path(__file__).resolve().parents[2]


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_REPO))
    except ValueError:
        return str(path)


def load_sta_path(sta_json: Path) -> dict | None:
    if not sta_json.is_file():
        return None
    blob = json.loads(sta_json.read_text())
    return blob.get("worst_path")


def load_sta_instances(sta_json: Path) -> list[dict]:
    if not sta_json.is_file():
        return []
    blob = json.loads(sta_json.read_text())
    pins = blob.get("pins") or []
    seen: set[str] = set()
    out: list[dict] = []
    for p in pins:
        key = norm_inst(p.get("inst_key") or p.get("inst"))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "inst": key,
                "cell": p.get("cell"),
                "pin": p.get("pin"),
                "arrival_ns": p.get("rise_ns"),
            }
        )
    return out


def load_node_voltages(map_csv: Path) -> dict[str, float]:
    if not map_csv.is_file():
        return {}
    volts: dict[str, float] = {}
    with map_csv.open() as fh:
        for row in csv.DictReader(fh):
            node = (row.get("node") or "").strip()
            if not node:
                continue
            try:
                volts[node] = float(row["v"])
            except (KeyError, TypeError, ValueError):
                continue
    return volts


def inst_voltages(spice: Path, map_csv: Path, vdd: float) -> dict[str, float]:
    sinks = parse_pg_sinks(spice)
    nodes = load_node_voltages(map_csv)
    by_inst: dict[str, float] = {}
    for rec in sinks.values():
        key = norm_inst(rec.get("inst"))
        node = rec.get("node")
        if not key or node not in nodes:
            continue
        v = float(nodes[node])
        prev = by_inst.get(key)
        if prev is None or v < prev:
            by_inst[key] = v
    return by_inst


def voltages_to_events(v_by_inst: dict[str, float]) -> tuple[list[dict], list[float]]:
    events: list[dict] = []
    vmin: list[float] = []
    for i, (inst, v) in enumerate(v_by_inst.items()):
        events.append({"inst": inst, "idx": i})
        vmin.append(float(v))
    return events, vmin


def cell_rows(
    instances: list[dict],
    v_by_inst: dict[str, float],
    vdd: float,
    path_keys: set[str],
) -> list[dict]:
    rows: list[dict] = []
    for inst in instances:
        key = inst["inst"]
        v = v_by_inst.get(key)
        rows.append(
            {
                **inst,
                "v_inst": v if v is not None else vdd,
                "ir_mv": None if v is None else (vdd - v) * 1e3,
                "joined": v is not None,
                "on_worst_path": key in path_keys,
            }
        )
    rows.sort(key=lambda r: (-(r["ir_mv"] or -1.0), r["inst"]))
    return rows


def build_report(
    *,
    sta_json: Path,
    spice: Path,
    map_csv: Path,
    vdd: float = VDD_DEFAULT,
    alpha: float = ALPHA_DEFAULT,
    period_ns: float = 0.46,
    variant: str = "flowlab",
) -> dict:
    path = load_sta_path(sta_json)
    instances = load_sta_instances(sta_json)
    v_by_inst = inst_voltages(spice, map_csv, vdd)
    events, vmin = voltages_to_events(v_by_inst)
    timing = path_ir_timing(path, events, vmin, vdd, period_ns, alpha=alpha)
    path_keys = {
        norm_inst(st.get("inst_key") or st.get("inst"))
        for st in (path or {}).get("stages") or []
        if (st.get("kind") or "net") == "gate"
    }
    cells = cell_rows(instances, v_by_inst, vdd, path_keys)
    joined = [c for c in cells if c["joined"]]
    path_cells = [c for c in cells if c["on_worst_path"]]
    path_meta = timing.get("path") or {}
    return {
        "ok": timing.get("status") == "READY",
        "kind": "sta_ir_aware",
        "variant": variant,
        "vdd": vdd,
        "alpha": alpha,
        "period_ns": period_ns,
        "model": timing.get("model"),
        "not": [
            "second liberty at Vmin",
            "CCS / ECSM voltage-dependent delay",
            "PrimeTime / Tempus IR-aware STA",
            "foundry sign-off",
            "gold Dynamic IR 45.298 mV restamp",
        ],
        "via": "OpenSTA worst max path × ITerm V from Dynamic IR map.csv + write_pg_spice sinks",
        "gold_ir_mv": GOLD_IR_MV,
        "sta": {
            "arrivals": _rel(sta_json),
            "path_status": path_meta.get("status"),
            "startpoint": path_meta.get("startpoint"),
            "endpoint": path_meta.get("endpoint"),
            "slack_ns": path_meta.get("slack_ns"),
            "slack_ir_ns": path_meta.get("slack_ir_ns"),
            "n_gates": path_meta.get("n_gates"),
            "n_joined": path_meta.get("n_joined"),
            "gate_delay_ns": path_meta.get("gate_delay_ns"),
            "gate_delay_ir_ns": path_meta.get("gate_delay_ir_ns"),
            "degradation_ps": timing.get("degradation_ps"),
            "frac_of_period": timing.get("frac_of_period"),
        },
        "ir": {
            "n_inst_sta": len(instances),
            "n_inst_ir": len(v_by_inst),
            "n_joined_cells": len(joined),
            "worst_cell_ir_mv": max((c["ir_mv"] or 0.0) for c in joined) if joined else None,
            "mean_cell_ir_mv": (
                sum(c["ir_mv"] or 0.0 for c in joined) / len(joined) if joined else None
            ),
            "map": _rel(map_csv),
            "spice": _rel(spice),
        },
        "timing": timing,
        "path_gates": [
            {
                "inst": st.get("inst_key") or st.get("inst"),
                "cell": st.get("cell"),
                "pin": st.get("pin"),
                "delay_ns": st.get("delay_ns"),
                "delay_ir_ns": st.get("delay_ir_ns"),
                "v_inst": st.get("v_inst"),
                "ir_mv": None
                if st.get("v_inst") is None
                else (vdd - float(st["v_inst"])) * 1e3,
                "joined": st.get("joined"),
                "scale": st.get("scale"),
            }
            for st in path_meta.get("stages") or []
            if (st.get("kind") or "net") == "gate"
        ],
        "hottest_cells": joined[:12],
        "path_cells": path_cells,
        "note": (
            "Educational IR-aware STA: NLDM typical-V gate delay scaled by "
            f"(Vdd/V_inst)^{alpha} on ITerm-joined instances. "
            "Net delay stays unscaled. Do not mix with gold 45.298 mV."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sta", type=Path, required=True)
    ap.add_argument("--spice", type=Path, required=True)
    ap.add_argument("--map", type=Path, required=True, dest="map_csv")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--vdd", type=float, default=VDD_DEFAULT)
    ap.add_argument("--alpha", type=float, default=ALPHA_DEFAULT)
    ap.add_argument("--period-ns", type=float, default=0.46)
    ap.add_argument("--variant", default="flowlab")
    args = ap.parse_args()
    if not args.sta.is_file():
        print(f"FAIL missing STA arrivals {args.sta}", file=sys.stderr)
        return 2
    if not args.spice.is_file() or not args.map_csv.is_file():
        print(
            f"FAIL need spice+map for per-cell V ({args.spice} {args.map_csv})",
            file=sys.stderr,
        )
        return 2
    report = build_report(
        sta_json=args.sta,
        spice=args.spice,
        map_csv=args.map_csv,
        vdd=args.vdd,
        alpha=args.alpha,
        period_ns=args.period_ns,
        variant=args.variant,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    sta = report["sta"]
    print(
        f"STA_IR_AWARE_DONE slack={sta.get('slack_ns')} "
        f"slack_ir={sta.get('slack_ir_ns')} "
        f"joined={sta.get('n_joined')}/{sta.get('n_gates')} "
        f"cells={report['ir']['n_joined_cells']}"
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
