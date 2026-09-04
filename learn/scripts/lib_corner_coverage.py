#!/usr/bin/env python3
"""List Nangate STD-cell liberty files and record which corners exist.

ORFS Nangate45 ships one typical.lib. That is a PDK fact, not a missing
wrapper. Do not invent slow/fast corners.
"""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = _ROOT / "tools/OpenROAD-flow-scripts/flow/platforms/nangate45/lib"


def inspect(lib_dir: Path = LIB_DIR) -> dict:
    libs = sorted(lib_dir.glob("NangateOpenCellLibrary_*.lib")) if lib_dir.is_dir() else []
    corners: list[str] = []
    for path in libs:
        name = path.name
        if name.startswith("NangateOpenCellLibrary_") and name.endswith(".lib"):
            corners.append(name[len("NangateOpenCellLibrary_") : -len(".lib")])
    mcmm = len(corners) >= 2
    named = ", ".join(corners) if corners else "none"
    return {
        "lib_dir": str(lib_dir),
        "liberty": [path.name for path in libs],
        "corners": corners,
        "mcmm": mcmm,
        "ok": True,
        "summary": (
            f"Liberty corners: {named}"
            + ("" if mcmm else " · leftover no MCMM")
        ),
    }


def write_report(lib_dir: Path = LIB_DIR) -> dict:
    report = inspect(lib_dir)
    out = _ROOT / "learn/sim/reports/lib_corner_coverage.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> int:
    if not LIB_DIR.is_dir():
        print("missing nangate45/lib", file=__import__("sys").stderr)
        return 2
    report = write_report()
    print(report["summary"])
    print("WROTE", _ROOT / "learn/sim/reports/lib_corner_coverage.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
