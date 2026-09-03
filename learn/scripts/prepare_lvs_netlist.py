#!/usr/bin/env python3
"""Build an LVS CDL that matches what is actually in the GDS.

ORFS concatenates the full Nangate library (135 SUBCKTs). GCD instantiates
~40 masters. Unused library cells have no GDS and KLayout flattens them.

OpenROAD write_cdl emits TAPCELL instances but drops FILLCELL. The GDS/DEF
still contain fillers. This script:

1. Keeps only instantiated library SUBCKTs (plus FILL/TAP).
2. Injects FILLCELL instances from the DEF into the top SUBCKT.

It does not invent nets or add well ports. Pin counts stay as in the CDL.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from filter_lvs_cdl import ALWAYS_KEEP, filter_library, used_masters

FILL_RE = re.compile(
    r"^\s*-\s+(\S+)\s+(FILLCELL_[A-Za-z0-9_]+)\b",
    re.IGNORECASE,
)
ENDS_RE = re.compile(r"^\.ENDS\b", re.IGNORECASE)
SUBCKT_RE = re.compile(r"^\.SUBCKT\s+(\S+)", re.IGNORECASE)


def fillers_from_def(def_text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in def_text.splitlines():
        m = FILL_RE.match(line)
        if not m:
            continue
        inst, master = m.group(1), m.group(2)
        if inst in seen:
            continue
        seen.add(inst)
        found.append((inst, master))
    return found


def inject_fillers(design_cdl: str, fillers: list[tuple[str, str]], top: str) -> str:
    if not fillers:
        return design_cdl
    lines = design_cdl.splitlines()
    out: list[str] = []
    in_top = False
    injected = False
    for line in lines:
        m = SUBCKT_RE.match(line.strip())
        if m:
            in_top = m.group(1) == top
        if in_top and ENDS_RE.match(line.strip()) and not injected:
            out.append("* FILLCELL instances from DEF (present in GDS, omitted by write_cdl)")
            for inst, master in fillers:
                out.append(f"X{inst} VDD VSS {master}")
            injected = True
            in_top = False
        out.append(line)
    if not injected:
        raise RuntimeError(f"top SUBCKT {top!r} .ENDS not found — cannot inject fillers")
    return "\n".join(out) + "\n"


def prepare(*, design_cdl: Path, library_cdl: Path, def_path: Path | None, top: str, out: Path) -> dict:
    design = design_cdl.read_text(errors="replace")
    lib = library_cdl.read_text(errors="replace")
    fillers: list[tuple[str, str]] = []
    if def_path and def_path.is_file():
        fillers = fillers_from_def(def_path.read_text(errors="replace"))
    design = inject_fillers(design, fillers, top)
    keep = used_masters(design)
    keep |= {master for _, master in fillers}
    filtered = filter_library(lib, keep)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(design.rstrip() + "\n" + filtered)
    return {
        "top": top,
        "n_fillers": len(fillers),
        "n_masters": len(keep),
        "masters": sorted(keep),
        "out": str(out),
        "always_keep_fill_tap": bool(ALWAYS_KEEP.pattern),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design-cdl", required=True)
    ap.add_argument("--library-cdl", required=True)
    ap.add_argument("--def", dest="def_path", default="")
    ap.add_argument("--top", default="gcd")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    info = prepare(
        design_cdl=Path(args.design_cdl),
        library_cdl=Path(args.library_cdl),
        def_path=Path(args.def_path) if args.def_path else None,
        top=args.top,
        out=Path(args.out),
    )
    print("LVS_NETLIST fillers", info["n_fillers"], "masters", info["n_masters"])
    print("LVS_NETLIST wrote", info["out"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
