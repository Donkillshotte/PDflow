#!/usr/bin/env python3
"""Convert OpenROAD write_pg_spice netlists to a vyges-em-ir .pdn mesh.

The engine (https://github.com/vyges-tools/em-ir) solves G·V = I on a
whitespace-keyword resistor network. This adapter is the GCD Nangate45 seam:
same R/I/V as PDNSim BUMPS, so static IR is comparable to pdn_transient.py.

Dynamic extras (optional):
  cap   — C_DECAP on each load node, in pF
  switch — simultaneous-switch triangle pulses (engine limit: one t50)

Node names stay SPICE identifiers (alnum + _). Layer tags come from
Node_metalN / ITermNode_metalN. Differing layers become `via`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from pdn_transient import parse_spice  # noqa: E402

LAYER_RE = re.compile(r"metal(\d+)", re.I)
SAFE_NODE = re.compile(r"[^A-Za-z0-9_]")


def sanitize(name: str) -> str:
    if name in ("0", "gnd", "GND"):
        return "0"
    out = SAFE_NODE.sub("_", name)
    if out and out[0].isdigit():
        out = "n_" + out
    return out or "node"


def layer_of(name: str) -> str | None:
    m = LAYER_RE.search(name)
    return f"metal{m.group(1)}" if m else None


def convert(
    spice: Path,
    *,
    dynamic: bool,
    c_decap_f: float,
    peak_factor: float,
    switch_t_ns: float,
    switch_dur_ns: float,
    vdd_override: float = 0.0,
) -> tuple[str, dict]:
    resistors, currents, voltages = parse_spice(spice)
    if not voltages:
        raise SystemExit("SPICE senza sorgenti V (pad)")
    vdd = vdd_override or next(iter(voltages.values()))
    pads = sorted({sanitize(n) for n in voltages if n != "0"})
    if not pads:
        raise SystemExit("nessun pad (nodo V)")

    lines: list[str] = [
        f"# vyges-em-ir PDN from {spice}",
        f"# adapter: spice_to_pdn.py · OpenROAD write_pg_spice",
        f"vdd {vdd:.6g}",
        "",
    ]
    for p in pads:
        lines.append(f"pad {p}")
    lines.append("")

    n_res = 0
    n_via = 0
    skipped_gnd = 0
    for a, b, r in resistors:
        if a == "0" or b == "0":
            skipped_gnd += 1
            continue
        na, nb = sanitize(a), sanitize(b)
        if na == nb:
            continue
        rr = max(float(r), 1e-12)
        la, lb = layer_of(a), layer_of(b)
        if la and lb and la != lb:
            lines.append(f"via {na} {nb} {rr:.8g}")
            n_via += 1
        else:
            layer = la or lb or "metal1"
            lines.append(f"res {na} {nb} {rr:.8g} {layer}")
            n_res += 1

    lines.append("")
    n_load = 0
    total_i = 0.0
    load_nodes: list[tuple[str, float]] = []
    for node, cur in sorted(currents.items()):
        if node == "0":
            continue
        i = abs(float(cur))
        if i <= 0.0:
            continue
        nn = sanitize(node)
        lines.append(f"load {nn} {i:.8g}")
        load_nodes.append((nn, i))
        n_load += 1
        total_i += i

    n_cap = 0
    n_sw = 0
    cap_pf = c_decap_f * 1e12
    if dynamic and load_nodes:
        lines.append("")
        lines.append("# dynamic IR: uniform decap on load taps + simultaneous switch")
        for nn, i_avg in load_nodes:
            if cap_pf > 0:
                lines.append(f"cap {nn} {cap_pf:.8g}")
                n_cap += 1
            # Triangle: Q = I_peak * dur / 2, energy = Q * vdd
            # I_peak = peak_factor * I_avg  (same envelope as pdn_transient)
            energy_pj = peak_factor * i_avg * vdd * switch_dur_ns * 500.0
            if energy_pj > 0:
                lines.append(
                    f"switch {nn} {energy_pj:.8g} {switch_t_ns:.6g} {switch_dur_ns:.6g}"
                )
                n_sw += 1

    stats = {
        "spice": str(spice),
        "vdd": vdd,
        "pads": len(pads),
        "resistors": n_res,
        "vias": n_via,
        "loads": n_load,
        "caps": n_cap,
        "switches": n_sw,
        "total_current_a": total_i,
        "skipped_gnd_res": skipped_gnd,
        "dynamic": bool(dynamic and n_sw > 0),
        "c_decap_f": c_decap_f,
        "peak_factor": peak_factor,
        "switch_t_ns": switch_t_ns,
        "switch_dur_ns": switch_dur_ns,
    }
    return "\n".join(lines) + "\n", stats


def write_job(path: Path, design: str, pdn_name: str, ir_limit_pct: float) -> None:
    path.write_text(
        "\n".join(
            [
                f"design: {design}",
                f"pdn: {pdn_name}",
                f"ir_limit_pct: {ir_limit_pct}",
                "",
            ]
        )
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spice", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--design", default="gcd")
    ap.add_argument("--ir-limit-pct", type=float, default=5.0)
    ap.add_argument("--dynamic", action="store_true")
    ap.add_argument("--c-decap", type=float, default=50e-15)
    ap.add_argument("--peak-factor", type=float, default=8.0)
    ap.add_argument("--switch-t-ns", type=float, default=1.0)
    ap.add_argument("--switch-dur-ns", type=float, default=0.08)
    ap.add_argument("--vdd", type=float, default=0.0)
    args = ap.parse_args()

    if not args.spice.is_file():
        print(f"FAIL manca spice {args.spice}", file=sys.stderr)
        return 1

    text, stats = convert(
        args.spice,
        dynamic=args.dynamic,
        c_decap_f=args.c_decap,
        peak_factor=args.peak_factor,
        switch_t_ns=args.switch_t_ns,
        switch_dur_ns=args.switch_dur_ns,
        vdd_override=args.vdd,
    )
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    pdn_name = f"{args.design}.pdn"
    emir_name = f"{args.design}.emir"
    (out / pdn_name).write_text(text)
    write_job(out / emir_name, args.design, pdn_name, args.ir_limit_pct)
    (out / f"{args.design}.adapter.json").write_text(json.dumps(stats, indent=2) + "\n")
    print("SPICE_TO_PDN_DONE")
    print(json.dumps(stats, indent=2))
    print(f"pdn → {out / pdn_name}")
    print(f"job → {out / emir_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
