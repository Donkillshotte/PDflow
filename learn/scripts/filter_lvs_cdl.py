#!/usr/bin/env python3
"""Keep only instantiated cell masters in the LVS concat CDL.

ORFS concatenates 6_final.cdl + the full Nangate library CDL. Unused
library SUBCKTs (TBUF, TLAT, …) have no GDS and KLayout reports
"Flatten schematic circuit (no layout)" then "Netlists don't match".

This filter is honest: it does not invent connectivity. It drops library
cells that the design does not instantiate.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

INST_RE = re.compile(r"\bX\S+\s+.*\s+([A-Za-z][A-Za-z0-9_]*)\s*$")
SUBCKT_RE = re.compile(r"^\.SUBCKT\s+(\S+)", re.IGNORECASE)
ENDS_RE = re.compile(r"^\.ENDS\b", re.IGNORECASE)


def used_masters(design_cdl: str) -> set[str]:
    used: set[str] = set()
    buf = ""
    for raw in design_cdl.splitlines():
        line = raw.split("*", 1)[0].rstrip()
        if not line:
            continue
        if line.startswith("+"):
            buf += " " + line[1:].strip()
            continue
        if buf:
            m = INST_RE.search(buf)
            if m:
                used.add(m.group(1))
        buf = line
    if buf:
        m = INST_RE.search(buf)
        if m:
            used.add(m.group(1))
    return used


ALWAYS_KEEP = re.compile(r"^(FILLCELL|TAPCELL)_")


def filter_library(lib_cdl: str, keep: set[str]) -> str:
    out: list[str] = []
    keep_block = False
    in_sub = False
    for line in lib_cdl.splitlines():
        m = SUBCKT_RE.match(line.strip())
        if m:
            in_sub = True
            keep_block = m.group(1) in keep or bool(ALWAYS_KEEP.match(m.group(1)))
            if keep_block:
                out.append(line)
            continue
        if in_sub and ENDS_RE.match(line.strip()):
            if keep_block:
                out.append(line)
            in_sub = False
            keep_block = False
            continue
        if not in_sub:
            # keep header comments / models outside subckts
            out.append(line)
        elif keep_block:
            out.append(line)
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design-cdl", required=True)
    ap.add_argument("--library-cdl", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    design = Path(args.design_cdl).read_text(errors="replace")
    lib = Path(args.library_cdl).read_text(errors="replace")
    keep = used_masters(design)
    if not keep:
        raise SystemExit("no instantiated masters parsed from design CDL")
    filtered = filter_library(lib, keep)
    Path(args.out).write_text(design.rstrip() + "\n" + filtered)
    print("LVS_CDL_FILTER keep", sorted(keep))
    print("LVS_CDL_FILTER wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
