"""DSE is a proposer. Signoff owns the close.

Product DSE (`run_recipe_loop.py`) and lab DSE (`run_dse.py`) may suggest
knobs, ECO steps, or extracts. They must not:

- call `run_signoff_all.sh`
- stamp `.lvs.ok`
- treat a lab IR number as a product win
- skip `signoff_all` after an applied ECO

The loop is: finish → (optional ECO propose/apply) → `signoff_all`.
Wins stay in `win_rule.py`. Lab gold Dynamic IR stays 45.298 mV.
"""

from __future__ import annotations

from pathlib import Path

LOCKED_VARIANTS = frozenset({"flowlab", "learn", "base"})
SIGNOFF_ORCHESTRATOR = "learn/scripts/run_signoff_all.sh"
DSE_ENTRIES = (
    "learn/scripts/run_dse.py",
    "learn/scripts/run_dse.sh",
    "learn/scripts/run_recipe_loop.py",
    "learn/dse/controller.py",
    "learn/dse/cook.py",
)


def is_locked_variant(variant: str) -> bool:
    return variant in LOCKED_VARIANTS


def dse_mentions_signoff_all(root: Path) -> list[str]:
    """Return DSE files that invoke the signoff orchestrator (should be empty)."""
    hits: list[str] = []
    for rel in DSE_ENTRIES:
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(errors="replace")
        if "run_signoff_all" in text or "signoff_all.sh" in text:
            hits.append(rel)
    return hits
