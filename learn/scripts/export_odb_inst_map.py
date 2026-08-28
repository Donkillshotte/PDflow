#!/usr/bin/env python3
"""Export a coarse instance map SVG/PNG from an OpenROAD ODB (for synth/floorplan early die)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/OpenROAD-flow-scripts/flow/scripts"))


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: export_odb_inst_map.py <odb> <out.svg>", file=sys.stderr)
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
    insts = block.getInsts()
    if not insts:
        print("FAIL no instances", file=sys.stderr)
        return 1

    xs, ys, rects = [], [], []
    for inst in insts:
        bbox = inst.getBBox()
        if bbox is None:
            continue
        x1, y1 = bbox.xMin(), bbox.yMin()
        x2, y2 = bbox.xMax(), bbox.yMax()
        xs.extend([x1, x2])
        ys.extend([y1, y2])
        rects.append((x1, y1, x2 - x1, y2 - y1))

    if not rects:
        print("FAIL no bboxes", file=sys.stderr)
        return 1

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    pad = max((max_x - min_x), (max_y - min_y)) * 0.04 or 1000
    min_x -= pad
    min_y -= pad
    max_x += pad
    max_y += pad
    w = max_x - min_x
    h = max_y - min_y
    vw, vh = 800, max(400, int(800 * h / w)) if w else 600

    def sx(x: float) -> float:
        return (x - min_x) / w * vw if w else 0

    def sy(y: float) -> float:
        return vh - (y - min_y) / h * vh if h else 0

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{vw}" height="{vh}">',
        f'<rect width="{vw}" height="{vh}" fill="#0a0e14"/>',
        f'<rect x="1" y="1" width="{vw-2}" height="{vh-2}" fill="none" stroke="rgba(255,255,255,0.12)"/>',
    ]
    for x, y, rw, rh in rects:
        px, py = sx(x), sy(y + rh)
        pw, ph = sx(x + rw) - sx(x), sy(y) - sy(y + rh)
        if pw < 0.3 or ph < 0.3:
            continue
        lines.append(
            f'<rect x="{px:.2f}" y="{py:.2f}" width="{pw:.2f}" height="{ph:.2f}" '
            f'fill="rgba(88,166,255,0.55)" stroke="rgba(88,166,255,0.25)" stroke-width="0.3"/>'
        )
    lines.append(
        f'<text x="{vw/2:.0f}" y="{vh-8:.0f}" text-anchor="middle" fill="#8b949e" font-size="11">'
        f"{len(rects)} instances · {odb_path.name}</text>"
    )
    lines.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = {
        "instances": len(rects),
        "bbox": [min_x, min_y, max_x, max_y],
        "out": str(out_path),
    }
    print("INST_MAP_JSON", json.dumps(meta))
    print("WROTE", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
