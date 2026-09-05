#!/usr/bin/env python3
"""ASAP7 inverter on patched Xyce BSIM-CMG cards.

HSpice ships level=72. Xyce 7.4 maps BSIM-CMG v107 to level=107.
Tiny inverter only. Not AES. Does not change the Nangate IR
reference 45.298 mV. Never writes .lvs.ok.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDK = ROOT / "learn/lab/asap7/pdk"
XYCE_DIR = PDK / "xyce"
REPORT = ROOT / "learn/sim/reports/lab_asap7_spice.json"
HSPICE_LEVEL = 72
XYCE_LEVEL = 107


def xyce_bin(root: Path = ROOT) -> Path | None:
    cand = root / "learn/tools/xyce/bin/Xyce"
    if cand.is_file() and os.access(cand, os.X_OK):
        return cand
    return None


def patch_hspice_cmg(text: str) -> str:
    """Join HSpice + continuations and retarget level 72 → Xyce 107."""
    lines: list[str] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("*"):
            continue
        lines.append(s)
    cards: list[list[str]] = []
    cur: list[str] = []
    for s in lines:
        if s.lower().startswith(".model"):
            if cur:
                cards.append(cur)
            cur = [
                s.replace("level = 72", f"level={XYCE_LEVEL}").replace(
                    "level=72", f"level={XYCE_LEVEL}"
                )
            ]
        elif s.startswith("+"):
            cur.append(s[1:].strip())
        else:
            cur.append(s)
    if cur:
        cards.append(cur)
    out: list[str] = []
    for card in cards:
        head = card[0]
        params = re.sub(r"\s+", " ", " ".join(card[1:]))
        toks = params.split()
        chunks = [" ".join(toks[i : i + 8]) for i in range(0, len(toks), 8)]
        block = head
        if chunks:
            block += "\n+" + "\n+".join(chunks)
        out.append(block)
    return "\n".join(out) + "\n"


def parse_models(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        s = line.strip().lower()
        if s.startswith(".model "):
            parts = s.split()
            if len(parts) >= 2:
                names.append(parts[1])
    return names


def parse_prn(prn: Path) -> dict:
    rows: list[tuple[float, float, float]] = []
    if not prn.is_file():
        return {"n": 0, "inverted": False}
    for line in prn.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            rows.append((float(parts[1]), float(parts[2]), float(parts[3])))
        except ValueError:
            continue
    if not rows:
        return {"n": 0, "inverted": False}
    vins = [r[1] for r in rows]
    vouts = [r[2] for r in rows]
    hi = [r[2] for r in rows if r[1] > 0.55]
    lo = [r[2] for r in rows if r[1] < 0.15]
    mean_hi = sum(hi) / len(hi) if hi else None
    mean_lo = sum(lo) / len(lo) if lo else None
    inverted = mean_lo is not None and mean_hi is not None and mean_lo > 0.5 and mean_hi < 0.3
    return {
        "n": len(rows),
        "vin_min": min(vins),
        "vin_max": max(vins),
        "vout_min": min(vouts),
        "vout_max": max(vouts),
        "vout_when_vin_high": mean_hi,
        "vout_when_vin_low": mean_lo,
        "inverted": inverted,
    }


def run_spice(root: Path = ROOT) -> dict:
    pdk = root / "learn/lab/asap7/pdk"
    src = pdk / "models/hspice/7nm_TT_160803.pm"
    if not src.is_file():
        src = pdk / "models/hspice/7nm_TT.pm"
    xyce = xyce_bin(root)
    work = pdk / "xyce"
    work.mkdir(parents=True, exist_ok=True)
    pm = work / "7nm_TT_xyce107.pm"
    net = work / "inv_tt.sp"
    prn_prefix = work / "inv_tt"
    payload: dict = {
        "ok": False,
        "surface": "lab",
        "platform": "asap7",
        "kind": "leftover_xyce_inverter",
        "product_win": False,
        "comparable_to_gold_ir": False,
        "calibre": False,
        "hspice_level": HSPICE_LEVEL,
        "xyce_level": XYCE_LEVEL,
        "patch": "level 72→107",
        "xyce": str(xyce) if xyce else None,
        "source_pm": str(src) if src.is_file() else None,
        "netlist": str(net),
        "leftover": {
            "spice": "HSpice BSIM-CMG cards patched for Xyce; not HSpice; not ngspice",
            "calibre": "ASU encrypted tarball + Calibre 2017.3/2017.4 not in this image",
            "stamp": "never write .lvs.ok for ASAP7",
        },
        "note": "ASAP7 Xyce inverter. Not a product win. "
        "Live metrics only — no gold stamp.",
    }
    if not src.is_file():
        payload["error"] = "HSpice .pm missing; run fetch_asap7_pdk.sh"
        return payload
    if xyce is None:
        payload["error"] = "Xyce not installed; learn/scripts/install_xyce.sh"
        return payload
    raw = src.read_text(errors="replace")
    patched = patch_hspice_cmg(raw)
    pm.write_text(patched)
    models = parse_models(raw)
    net.write_text(
        f"""* ASAP7 inverter on patched Xyce cards. Not the Nangate 45.298 mV IR. Not AES.
.include {pm}
Vdd vdd 0 0.7
Vin in 0 PULSE(0 0.7 50p 10p 10p 200p 500p)
Mn out in 0 0 nmos_rvt L=21n NFIN=2
Mp out in vdd vdd pmos_rvt L=21n NFIN=4
Cl out 0 0.2f
.tran 2p 500p
.print tran format=std v(in) v(out)
.end
"""
    )
    env = os.environ.copy()
    lib = root / "learn/tools/xyce/lib"
    if lib.is_dir():
        env["LD_LIBRARY_PATH"] = f"{lib}{os.pathsep}{env.get('LD_LIBRARY_PATH', '')}"
    env["PATH"] = f"{xyce.parent}{os.pathsep}{env.get('PATH', '')}"
    proc = subprocess.run(
        [str(xyce), str(net), "-o", str(prn_prefix)],
        cwd=str(work),
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )
    prn = Path(str(prn_prefix) + ".prn")
    wave = parse_prn(prn)
    payload.update(
        {
            "ok": proc.returncode == 0 and wave.get("inverted") is True,
            "exit_code": proc.returncode,
            "models": models,
            "n_model": len(models),
            "prn": str(prn) if prn.is_file() else None,
            "wave": wave,
            "stdout_tail": (proc.stdout or "")[-400:],
            "stderr_tail": (proc.stderr or "")[-400:],
        }
    )
    return payload


def main() -> int:
    payload = run_spice(ROOT)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {REPORT}")
    wave = payload.get("wave") or {}
    print(
        f"ok={payload['ok']} inverted={wave.get('inverted')} "
        f"patch={payload.get('patch')} exit={payload.get('exit_code')}"
    )
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
