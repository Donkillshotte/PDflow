#!/usr/bin/env python3
"""Dump instance geometry from a routed ODB for vectorless current mapping."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: export_odb_inst_power.py <odb> <out.json>", file=sys.stderr)
        return 2
    odb_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    if not odb_path.exists():
        print(f"FAIL missing {odb_path}", file=sys.stderr)
        return 1

    import odb  # type: ignore

    db = odb.dbDatabase.create()
    odb.read_db(db, str(odb_path))
    block = db.getChip().getBlock()
    rows = []
    seq = 0
    for inst in block.getInsts():
        master = inst.getMaster()
        name = master.getName() if master else ""
        is_seq = any(k in name.upper() for k in ("DFF", "LATCH", "DLATCH"))
        filler = any(
            k in (name + inst.getName()).upper()
            for k in ("FILLCELL", "FILLER", "TAPCELL", "ENDCAP", "WELLTAP")
        )
        if is_seq:
            seq += 1
        bbox = inst.getBBox()
        if bbox is None:
            continue
        area = max(1, (bbox.xMax() - bbox.xMin()) * (bbox.yMax() - bbox.yMin()))
        cx = 0.5 * (bbox.xMin() + bbox.xMax())
        cy = 0.5 * (bbox.yMin() + bbox.yMax())
        rows.append(
            {
                "name": inst.getName(),
                "cell": name,
                "area": area,
                "x": cx,
                "y": cy,
                "seq": is_seq,
                "filler": filler,
            }
        )
    die = block.getDieArea()
    out = {
        "n": len(rows),
        "sequential": seq,
        "die": {
            "x0": die.xMin(),
            "y0": die.yMin(),
            "x1": die.xMax(),
            "y1": die.yMax(),
        },
        "insts": rows,
        "odb": str(odb_path),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out) + "\n")
    print("WROTE", out_path, "n=", len(rows), "seq=", seq)
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
