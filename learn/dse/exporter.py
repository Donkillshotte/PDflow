"""Full-chip export. Cone-local netlists are not finish_ready.

A finish handoff requires ``module gcd`` covering the whole design, not a
cone-scoped rewrite that changed only dpath operators while reporting
itself as a smaller chip.
"""

from __future__ import annotations

import re
from pathlib import Path

from .memory import Candidate

_MODULE_RE = re.compile(r"^module\s+(\w+)\s*\(", re.M)


def netlist_modules(text: str) -> list[str]:
    return _MODULE_RE.findall(text)


def is_full_chip_gcd(path: Path | str | None) -> tuple[bool, str]:
    if not path:
        return False, "no_netlist"
    p = Path(path)
    if not p.is_file():
        return False, "missing_file"
    text = p.read_text(errors="replace")
    mods = netlist_modules(text)
    if "gcd" not in mods:
        return False, "no_module_gcd"
    knobs_scope = ""
    # Hierarchical cone netlists still have gcd + many submodules; that is OK
    # if the top is gcd. Architecture extracts that flatten to a tiny gcd
    # still pass this syntactic check — finish_ready also needs semantic PASS
    # and funnel place-DP. This function only blocks missing tops.
    if not re.search(r"^module\s+gcd\s*\(", text, re.M):
        return False, "gcd_not_top"
    return True, "full_chip_top_gcd"


def mark_export(c: Candidate, netlist: Path | str | None = None) -> Candidate:
    path = netlist or (c.artifacts or {}).get("mapped_v") or c.netlist_fp
    ok, reason = is_full_chip_gcd(path)
    hist = list(c.promotion_history or [])
    hist.append({"stage": "export", "ok": ok, "reason": reason})
    c.promotion_history = hist
    kn = dict(c.knobs or {})
    if kn.get("scope") == "logic_cone" and kn.get("extract"):
        # Architecture rtl_rewrite of a cone, emitted as a whole-chip Yosys
        # flatten, is still a *different* netlist — not a stitch into baseline.
        c.attr = dict(c.attr or {})
        c.attr["export"] = "standalone_chip_not_stitched"
        c.finish_ready = False
        c.rejection_reason = c.rejection_reason or "not_stitched_into_baseline"
        hist.append({"stage": "export", "ok": False, "reason": "not_stitched_into_baseline"})
        c.promotion_history = hist
        return c
    c.finish_ready = bool(
        ok
        and (
            (c.semantic_contract or {}).get("status") == "pass"
            or (c.attr or {}).get("equiv") == "PASS"
        )
    )
    if not ok:
        c.finish_ready = False
        c.rejection_reason = reason
    return c
