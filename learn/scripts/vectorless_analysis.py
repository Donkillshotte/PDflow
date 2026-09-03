#!/usr/bin/env python3
"""Vectorless vs dynamic power/IR for GCD Nangate45.

References (methods, not copied code):
- F. Najm, "A survey of power estimation techniques in VLSI circuits",
  Proc. IEEE 1994. Switching probability P01 ≈ P0·P1 (here p=0.5 combo,
  p=0.1 sequential).
- D. Kouroussis & F. Najm, "A static pattern-independent technique for
  power grid voltage integrity verification", DAC 2003. Instance currents
  are constrained; a chip-level budget models mutual exclusion so not
  every gate draws I_max at once. Worst IR is estimated without a VCD.

When write_pg_spice exists, currents are re-scaled on the PDN mesh and
solved DC (same engine as pdn_transient.py).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

if "/usr/lib/python3/dist-packages" not in sys.path:
    sys.path.insert(0, "/usr/lib/python3/dist-packages")

TOTAL_RE = re.compile(
    r"^Total\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)",
    re.M,
)
IR_V_RE = re.compile(r"Worstcase IR drop:\s+([0-9.eE+-]+)\s*V", re.I)
VDD = 1.1
CREST_VECTORLESS = 3.0  # chip-level simultaneous-switch budget vs I_avg
P_COMBO = 0.5
P_SEQ = 0.1


def parse_power_log(path: Path) -> dict:
    text = path.read_text(errors="replace") if path.exists() else ""
    m = TOTAL_RE.search(text)
    watts = float(m.group(4)) if m else None
    src = "unknown"
    sm = re.search(r"ACTIVITY_SOURCE\s+(\S+)(.*)$", text, re.M)
    if sm:
        src = (sm.group(1) + (sm.group(2) or "")).strip()
    ir_mv = None
    im = IR_V_RE.search(text)
    if im:
        ir_mv = float(im.group(1)) * 1e3
    return {
        "exists": path.exists(),
        "source": src,
        "total_w": watts,
        "i_avg_a": (watts / VDD) if watts else None,
        "ir_straps_mv": ir_mv,
        "log": str(path),
    }


def switching_p01(p: float) -> float:
    """Najm 1994: P01 = p(1-p) for a node with signal probability p."""
    return p * (1.0 - p)


def worst_case_currents(insts: list[dict], i_avg: float, crest: float) -> dict:
    """Greedy vectorless envelope: spend the chip current budget on
    instances farthest from die origin (proxy for distance to straps).
    """
    budget = i_avg * crest
    logic = [i for i in insts if not i.get("filler")]
    work = logic or insts
    areas = [max(1.0, float(i["area"])) for i in work]
    weights = []
    for inst, a in zip(work, areas):
        p = P_SEQ if inst.get("seq") else P_COMBO
        p01 = switching_p01(p)
        dist = math.hypot(float(inst["x"]), float(inst["y"]))
        weights.append(a * p01 * (1.0 + dist))
    s = sum(weights) or 1.0
    i_nom = [budget * w / s for w in weights]
    # Cap per-instance at 8× its area share of I_avg (local I_max).
    i_area = [i_avg * a / (sum(areas) or 1.0) for a in areas]
    i_max = [8.0 * x for x in i_area]
    i_wc = [min(a, b) for a, b in zip(i_nom, i_max)]
    spent = sum(i_wc)
    ranked = sorted(
        (
            {
                "name": work[i]["name"],
                "cell": work[i].get("cell"),
                "seq": work[i].get("seq"),
                "i_a": i_wc[i],
            }
            for i in range(len(work))
        ),
        key=lambda r: r["i_a"],
        reverse=True,
    )
    return {
        "budget_a": budget,
        "spent_a": spent,
        "n": len(work),
        "n_skipped_fill": max(0, len(insts) - len(work)),
        "p_combo": P_COMBO,
        "p_seq": P_SEQ,
        "p01_combo": switching_p01(P_COMBO),
        "p01_seq": switching_p01(P_SEQ),
        "crest": crest,
        "hottest": ranked[:8],
    }


def spice_dc_drop_mv(spice: Path, scale: float) -> float | None:
    if not spice.exists() or scale <= 0:
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from pdn_transient import parse_spice, build_system, solve_static
    except Exception:
        return None
    try:
        resistors, currents, voltages = parse_spice(spice)
        currents = {k: v * scale for k, v in currents.items()}
        order, idx, G = build_system(resistors, currents, voltages)
        vdd = max(voltages.values()) if voltages else VDD
        result = solve_static(G, idx, order, currents, voltages, vdd)
        return max(0.0, float(result["worst_ir"]) * 1e3)
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--insts", required=True)
    ap.add_argument("--vectorless-log", required=True)
    ap.add_argument("--dynamic-log", required=True)
    ap.add_argument("--spice", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    insts_path = Path(args.insts)
    blob = json.loads(insts_path.read_text()) if insts_path.exists() else {"insts": []}
    insts = blob.get("insts") or []
    vl = parse_power_log(Path(args.vectorless_log))
    dy = parse_power_log(Path(args.dynamic_log))
    i_avg = vl.get("i_avg_a") or 0.0
    envelope = worst_case_currents(insts, i_avg, CREST_VECTORLESS) if insts and i_avg else {}
    spice = Path(args.spice)
    scale = 1.0
    mesh_i = dy.get("i_avg_a") or i_avg
    if envelope.get("spent_a") and mesh_i:
        scale = float(envelope["spent_a"]) / max(float(mesh_i), 1e-12)
    ir_mesh = spice_dc_drop_mv(spice, scale) if spice.exists() else None

    ok = bool(vl.get("total_w") and insts)
    out = {
        "ok": ok,
        "kind": "vectorless_vs_dynamic",
        "variant": args.variant,
        "vdd": VDD,
        "vectorless": vl,
        "dynamic": dy,
        "design": {
            "instances": blob.get("n"),
            "sequential": blob.get("sequential"),
        },
        "envelope": envelope,
        "ir_mesh_vectorless_mv": ir_mesh,
        "summary": (
            f"Vectorless P={vl.get('total_w')} W · I_avg={i_avg:.4e} A · "
            f"dynamic P={dy.get('total_w')} W · source {dy.get('source')}"
        ),
        "references": [
            "Najm, Proc. IEEE 1994, power estimation / switching probability",
            "Kouroussis & Najm, DAC 2003, vectorless IR current constraints",
        ],
        "notes": [
            "Gate VCD (tb_gcd_gate/dut) name-joins ODB instances. RTL VCD is ports-only (lesson 00).",
            "Icarus TB clock is 10 ns vs SDC 0.46 ns — OpenSTA warns STA-1452; dynamic watts are not 1:1 with vectorless.",
            "Fill/tap cells are excluded from the current envelope (Kouroussis instance currents).",
            "Raphael/StarRC are commercial; OpenRCX SPEF + this envelope are the OSS path.",
        ],
    }
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    print(out["summary"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
