#!/usr/bin/env python3
"""Append a lab DSE launch snapshot and compare it to the previous cook.

Called after every ``run_dse.sh`` success. Does not restamp gold. Does not
treat ΔIR across different extracts as a product win.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "learn/sim/reports"
DSE = ROOT / "learn/sim/dse"
HISTORY = DSE / "launch_compare.jsonl"
GOLD_MV = 45.298

KEYS = (
    "n_candidates",
    "n_f1",
    "n_f4",
    "n_f4_solve",
    "winning_static_mv",
    "winning_ir_pdn_mv",
    "ir_champ_amg_mv",
    "ir_champ_ras_mv",
    "ir_champ_krylov_mv",
    "ir_cell_champ_extract_mv",
    "ir_cell_champ_wns_ns",
    "spent_s",
)


def _f(v):
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None  # NaN guard


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text().splitlines():
        t = line.strip()
        if not t:
            continue
        try:
            rows.append(json.loads(t))
        except json.JSONDecodeError:
            continue
    return rows


def snapshot_from_report(report: dict, *, role: str = "cook") -> dict:
    shot = {
        "kind": "dse_launch",
        "role": role,
        "ok": bool(report.get("ok")),
        "variant": report.get("variant") or "flowlab",
        "design_id": report.get("design_id") or "gcd",
        "created_at": time.time(),
        "summary": str(report.get("summary") or "")[:240],
    }
    for k in KEYS:
        shot[k] = _f(report.get(k)) if k != "n_candidates" else report.get(k)
        if k.startswith("n_"):
            v = report.get(k)
            shot[k] = int(v) if v is not None else None
    return shot


def snapshot_from_ingest(mem_path: Path, variant: str) -> dict | None:
    if not mem_path.is_file():
        return None
    for line in mem_path.read_text().splitlines():
        t = line.strip()
        if not t:
            continue
        try:
            row = json.loads(t)
        except json.JSONDecodeError:
            continue
        qor = row.get("qor") or {}
        ir = qor.get("dynamic_ir_mv")
        if row.get("fidelity") != "F4" or ir is None:
            continue
        return {
            "kind": "dse_launch",
            "role": "ingest",
            "ok": row.get("status") == "ok",
            "variant": variant,
            "design_id": row.get("design_id") or "gcd",
            "created_at": float(row.get("created_at") or time.time()),
            "n_candidates": 1,
            "n_f1": 0,
            "n_f4": 1,
            "n_f4_solve": 0,
            "winning_static_mv": _f(qor.get("static_ir_mv")),
            "winning_ir_pdn_mv": _f(ir),
            "ir_champ_amg_mv": None,
            "ir_champ_ras_mv": None,
            "ir_champ_krylov_mv": None,
            "ir_cell_champ_extract_mv": None,
            "ir_cell_champ_wns_ns": _f((row.get("attr") or {}).get("path_slack_ns")),
            "spent_s": _f(row.get("cost_s")) or 0.0,
            "summary": "First F4 ingest in memory. Gold-adjacent extract. Not a controller cook.",
            "note": "Do not subtract this IR from a later candidate mesh.",
        }
    return None


def compare(curr: dict, prev: dict | None) -> dict:
    if not prev:
        return {
            "versus": None,
            "note": "First recorded launch for this variant.",
            "same_mesh": None,
        }
    same_mesh = (
        curr.get("role") == prev.get("role") == "cook"
        and curr.get("variant") == prev.get("variant")
    )
    delta = {}
    for k in (
        "n_candidates",
        "winning_static_mv",
        "winning_ir_pdn_mv",
        "ir_champ_amg_mv",
        "ir_cell_champ_extract_mv",
        "ir_cell_champ_wns_ns",
        "spent_s",
    ):
        a, b = _f(curr.get(k)), _f(prev.get(k))
        delta[k] = None if a is None or b is None else a - b
    note = (
        "Same report keys. ΔIR is only a product story if both cooks share an extract."
        if same_mesh
        else "Different roles or extracts. Do not read ΔIR as a win."
    )
    prev_ir = _f(prev.get("winning_ir_pdn_mv"))
    if prev_ir is not None and abs(prev_ir - GOLD_MV) < 0.05:
        note = "Previous shot is the gold ingest (45.298 mV). Not the same mesh as a later F4 cook."
    return {"versus": prev.get("created_at"), "same_mesh": same_mesh, "delta": delta, "note": note}


def record(*, variant: str, seed_ingest: bool = False) -> dict:
    DSE.mkdir(parents=True, exist_ok=True)
    history = _jsonl(HISTORY)
    same = [r for r in history if r.get("variant") == variant]
    if seed_ingest and not any(r.get("role") == "ingest" for r in same):
        ingest = snapshot_from_ingest(DSE / f"memory_{variant}.jsonl", variant)
        if ingest:
            ingest["compare"] = compare(ingest, None)
            with HISTORY.open("a") as fh:
                fh.write(json.dumps(ingest, separators=(",", ":")) + "\n")
            same.append(ingest)
            history.append(ingest)
    report = _read_json(REPORTS / f"dse_{variant}.json")
    if not report:
        latest = same[-1] if same else None
        return {"ok": False, "reason": "no dse report", "n": len(history), "latest": latest}
    shot = snapshot_from_report(report)
    prev = same[-1] if same else None
    shot["compare"] = compare(shot, prev)
    with HISTORY.open("a") as fh:
        fh.write(json.dumps(shot, separators=(",", ":")) + "\n")
    history.append(shot)
    latest_path = DSE / "launch_compare_latest.json"
    latest_path.write_text(json.dumps({"ok": True, "n": len(history), "latest": shot}, indent=2) + "\n")
    return {"ok": True, "n": len(history), "latest": shot}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--variant", default="flowlab")
    ap.add_argument(
        "--seed-ingest",
        action="store_true",
        help="record the first F4 memory ingest if no ingest row exists yet",
    )
    args = ap.parse_args()
    out = record(variant=args.variant, seed_ingest=args.seed_ingest)
    latest = out.get("latest") or {}
    print(
        f"DSE_LAUNCH_COMPARE ok={out.get('ok')} n={out.get('n')} "
        f"role={latest.get('role')} ir={latest.get('winning_ir_pdn_mv')} "
        f"n_cand={latest.get('n_candidates')}"
    )
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
