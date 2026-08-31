#!/usr/bin/env python3
"""Guards: AES / large-mesh analysis stays opt-in."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from heavy_analysis import (  # noqa: E402
    HEAVY_MESH_R,
    check_krylov,
    check_large_mesh,
    heavy_allowed,
    refusal_for_heavy,
)


def check(ok: bool, msg: str) -> None:
    print(("OK  " if ok else "FAIL ") + msg)
    if not ok:
        raise SystemExit(1)


def main() -> int:
    os.environ.pop("ALLOW_HEAVY_ANALYSIS", None)
    check(not heavy_allowed(), "default disallows heavy analysis")
    check(check_large_mesh(1000) is None, "GCD-sized mesh 1000 R allowed")
    check(check_large_mesh(HEAVY_MESH_R) is None, f"mesh == {HEAVY_MESH_R} allowed")
    msg = check_large_mesh(73_000)
    check(msg is not None and "73000" in msg, "AES 73k-R mesh refused without flag")
    check(check_krylov(73_000, "krylov") is not None, "Krylov on 73k refused")
    check(check_krylov(1000, "direct") is None, "DirectLU on small mesh allowed")
    os.environ["ALLOW_HEAVY_ANALYSIS"] = "1"
    check(heavy_allowed(), "flag enables heavy analysis")
    check(check_large_mesh(73_000) is None, "73k allowed when opted in")
    check("ALLOW_HEAVY_ANALYSIS=1" in refusal_for_heavy("x"), "refusal names the flag")
    print("HEAVY_GUARD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
