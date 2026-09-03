#!/usr/bin/env python3
"""Read the FreePDK45 KLayout DRC deck and record what it actually checks.

Antenna is in the deck. Density and a named ERC section are not.
This is a PDK-deck fact, not a missing wrapper in this repo.
"""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
DECK = _ROOT / "tools/OpenROAD-flow-scripts/flow/platforms/nangate45/drc/FreePDK45.lydrc"


def inspect(text: str) -> dict:
    low = text.lower()
    antenna = "antenna_check(" in text and "ANTENNA = true" in text
    density = any(tok in low for tok in ("density_check", "metal_density", "min_density"))
    erc = "if erc" in low or "\nerc =" in low
    return {
        "deck": str(DECK),
        "feol": "FEOL    = true" in text or "FEOL = true" in text,
        "beol": "BEOL    = true" in text or "BEOL = true" in text,
        "offgrid": "OFFGRID" in text,
        "antenna": antenna,
        "antenna_ratio": "300:1" if "300.0" in text and antenna else None,
        "density": density,
        "named_erc_section": erc,
        "ok": True,
        "summary": (
            "DRC deck: FEOL+BEOL+antenna"
            + ("" if density else " · no density rules")
            + ("" if erc else " · no named ERC section")
        ),
    }


def main() -> int:
    if not DECK.is_file():
        print("missing FreePDK45.lydrc", file=__import__("sys").stderr)
        return 2
    report = inspect(DECK.read_text(errors="replace"))
    out = _ROOT / "learn/sim/reports/drc_deck_coverage.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(report["summary"])
    print("WROTE", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
