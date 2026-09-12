#!/usr/bin/env python3
"""Describe live IR/EM meshes without importing an external result.

Reports from different physical meshes are intentionally kept separate.
Only solver results that point at the same live extract may be compared.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "learn/sim/reports"


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _mv(value, scale: float = 1.0) -> float | None:
    if value is None:
        return None
    try:
        return float(value) * scale
    except (TypeError, ValueError):
        return None


def _report_name(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("learn/", "", 1)
    except ValueError:
        return str(path)


def _live_entry(*, ident: str, mesh: str, path: Path, static_mv: float | None,
                dynamic_mv: float | None, comparison_scope: str, note: str,
                **extra) -> dict:
    return {
        "id": ident,
        "mesh": mesh,
        "report": _report_name(path),
        "static_mv": static_mv,
        "dynamic_mv": dynamic_mv,
        "comparison_scope": comparison_scope,
        "em_checked": None,
        "comparable_to": [],
        "note": note,
        **extra,
    }


def build_ledger(variant: str = "flowlab") -> dict:
    dynamic_path = REPORTS / f"dynamic_ir_{variant}_direct.json"
    chip_path = REPORTS / f"pdn_chip_ir_{variant}.json"
    system_path = REPORTS / f"system_pdn_{variant}.json"
    vyges_path = REPORTS / f"vyges_em_ir_{variant}.json"
    dynamic = _load(dynamic_path)
    chip = _load(chip_path)
    system = _load(system_path)
    vyges = _load(vyges_path)
    meshes: list[dict] = []

    if dynamic:
        win = dynamic.get("windowed") or {}
        dyn_mv = _mv(win.get("worst_droop_mv"))
        if dyn_mv is None:
            dyn_mv = _mv((dynamic.get("dynamic") or {}).get("worst_droop"), 1e3)
        static = dynamic.get("static") or {}
        static_mv = _mv(static.get("worst_ir_mv"))
        if static_mv is None:
            static_mv = _mv(static.get("worst_ir"), 1e3)
        meshes.append(_live_entry(
            ident="dynamic_ir", mesh="live Dynamic IR I(t)", path=dynamic_path,
            static_mv=static_mv, dynamic_mv=dyn_mv,
            comparison_scope="same-live-extract",
            note="Direct, AMG, RAS and Krylov results may be compared only within this extract.",
        ))

    if chip:
        meshes.append(_live_entry(
            ident="chip_pdn", mesh="live write_pg_spice chip PDN", path=chip_path,
            static_mv=_mv((chip.get("static") or {}).get("worst_ir"), 1e3),
            dynamic_mv=_mv((chip.get("transient") or {}).get("worst_droop"), 1e3),
            comparison_scope="distinct-live-mesh",
            note="Chip mesh is a separate live artifact; do not combine it with Dynamic IR values.",
        ))

    if vyges:
        value = vyges.get("vyges") or {}
        meshes.append(_live_entry(
            ident="vyges_em_ir", mesh="live vyges-em-ir mesh", path=vyges_path,
            static_mv=_mv((value.get("worst_ir") or {}).get("drop"), 1e3),
            dynamic_mv=_mv((value.get("dynamic") or {}).get("drop"), 1e3),
            comparison_scope="distinct-live-mesh",
            em_checked=int(value.get("em_checked") or 0),
            note="EM remains ungraded when the active process has no EM limit.",
        ))

    if system:
        meshes.append(_live_entry(
            ident="system_pdn", mesh="live VRM-to-board-to-package-to-die ladder", path=system_path,
            static_mv=None,
            dynamic_mv=_mv((system.get("transient") or {}).get("droop_mv")),
            comparison_scope="distinct-live-mesh",
            zmax_mohm=_mv((system.get("impedance") or {}).get("z_max_mohm")),
            note="Package/board ladder is not the on-die mesh.",
        ))

    return {
        "ok": bool(meshes),
        "variant": variant,
        "comparison_scope": "same-live-extract only; distinct-live-mesh otherwise",
        "meshes": meshes,
        "note": "Values are from this invocation's reports; no external reference is loaded.",
    }


def stamp(variant: str = "flowlab") -> dict:
    ledger = build_ledger(variant)
    out = REPORTS / f"power_signoff_{variant}.json"
    blob = _load(out) or {
        "kind": "power_signoff", "variant": variant, "ok": None,
        "summary": "power_signoff report missing — ledger only",
    }
    blob["ir_mesh_ledger"] = ledger
    out.write_text(json.dumps(blob, indent=2) + "\n")
    return ledger


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variant", default="flowlab")
    ap.add_argument("--stamp", action="store_true", help="write the live mesh ledger into power_signoff JSON")
    args = ap.parse_args()
    ledger = stamp(args.variant) if args.stamp else build_ledger(args.variant)
    print(json.dumps(ledger, indent=2))
    return 0 if ledger["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
