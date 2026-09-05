#!/usr/bin/env python3
"""Inventory the fetched ASAP7 layer-1 PDK. Not Calibre. Not a product win.

Does not restamp 45.298. Never writes .lvs.ok.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDK = ROOT / "learn/lab/asap7/pdk"
REPORT = ROOT / "learn/sim/reports/lab_asap7_pdk.json"

REQUIRED_RUL = (
    "ruledirs/drc/drcRules_calibre_asap7.rul",
    "ruledirs/lvs/lvsRules_calibre_asap7.rul",
    "ruledirs/rcx/rcxControl_calibre_asap7.rul",
)


def _pm_files(pdk: Path) -> list[str]:
    models = pdk / "models"
    if not models.is_dir():
        return []
    return sorted(str(p.relative_to(pdk)) for p in models.rglob("*.pm"))


def _rul_files(calibre: Path) -> list[str]:
    if not calibre.is_dir():
        return []
    return sorted(str(p.relative_to(calibre)) for p in calibre.rglob("*.rul"))


def inventory(root: Path = ROOT) -> dict:
    pdk = root / "learn/lab/asap7/pdk"
    calibre = pdk / "calibre"
    pms = _pm_files(pdk)
    ruls = _rul_files(calibre)
    placeholder = False
    readme = calibre / "ruledirs/lvs/README.txt"
    if readme.is_file():
        placeholder = "not provided as part of the ASAP7 PDK" in readme.read_text()
    calibre_ready = all((calibre / rel).is_file() for rel in REQUIRED_RUL)
    payload = {
        "ok": pdk.is_dir() and len(pms) >= 3,
        "surface": "lab",
        "platform": "asap7",
        "kind": "layer1_pdk_inventory",
        "product_win": False,
        "comparable_to_gold_ir": False,
        "calibre": False,
        "calibre_ready": calibre_ready,
        "calibre_ran": False,
        "calibre_placeholder": placeholder,
        "pdk": str(pdk) if pdk.is_dir() else None,
        "n_pm": len(pms),
        "pm_files": pms,
        "n_calibre_rul": len(ruls),
        "calibre_rul": ruls,
        "cdslib": (pdk / "cdslib/asap7_TechLib_10").is_dir(),
        "drm": (pdk / "docs/asap7_drm_201207a.pdf").is_file(),
        "leftover": {
            "calibre": "ASU encrypted tarball + Calibre 2017.3/2017.4 not in this image"
            if not calibre_ready
            else "decks present; Calibre binary still required to run",
            "virtuoso": "cdslib is OA techlib; no Virtuoso in this image",
            "spice": "HSpice BSIM-CMG cards; ngspice is the wrong first tool",
            "stamp": "never write .lvs.ok for ASAP7",
        },
        "note": "Layer-1 public PDK inventory. Not Calibre unless calibre_ready. "
        "Not a product win. Live metrics only — no gold stamp.",
    }
    return payload


def main() -> int:
    payload = inventory(ROOT)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {REPORT}")
    print(
        f"ok={payload['ok']} n_pm={payload['n_pm']} "
        f"calibre_ready={payload['calibre_ready']} placeholder={payload['calibre_placeholder']}"
    )
    if not payload["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
