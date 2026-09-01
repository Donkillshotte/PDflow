"""Pieces the Next Level loop does not consult.

GNN HPWL, the refine-stage bandit, and IR champ/leftover tours stay in
the tree for the legacy controller, but they cannot declare a finish
winner. Enable them only with DSE_ENABLE_FOLKLORE=1 (report-only GNN).
"""

from __future__ import annotations

import os
from typing import Any, Iterable

ISOLATED = (
    "gnn.predict_hpwl / surrogate.predict_f2_gnn — report-only, never a finish gate",
    "bandit.choose — unused by controller and by the Next Level scheduler",
    "ir_champ / leftover catalog extracts — same-extract PDN only after F6",
)


def folklore_enabled() -> bool:
    return os.environ.get("DSE_ENABLE_FOLKLORE") == "1"


def folklore_report() -> dict[str, Any]:
    return {
        "enabled": folklore_enabled(),
        "isolated": list(ISOLATED),
        "consulted_by_next_level": False,
    }


def gnn_report(all_cands: Iterable[Any] | None = None) -> dict[str, Any]:
    """Controller report hook. Default is skip so GNN is not a silent score."""
    if not folklore_enabled():
        return {
            "skipped": True,
            "via": "folklore_isolated",
            "not": "next-level scheduler / funnel / feasibility",
        }
    from .surrogate import predict_f2_gnn

    return predict_f2_gnn(list(all_cands or []))
