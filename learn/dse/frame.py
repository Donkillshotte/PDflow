"""Refinement chain as data — depth is an index, not a new function per layer.

Legacy memory records name the chain with suffixes ("", "_leftover",
"_leftover2"). This adapter rebuilds the same chain from the persisted
lineage so deeper layers need zero new code. It never invents records:
everything is read back from DesignMemory.

Conventions (0-indexed):
  depth 0 — leftover-combo size-up on the winning-IR-region PDN join
  depth 1 — leftover of depth 0 (legacy "leftover leftover")
  depth 2 — leftover of depth 1 (legacy "leftover leftover leftover")
  depth n — legacy source suffix "" / "_leftover" / f"_leftover{n}"

Base lineage (outside the refine chain, always subtracted from joins):
  cell_size_ir, cell_size_ir_champ, cell_size_ir_champ_cone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .memory import DesignMemory

BASE_SIZED_SOURCES = (
    "cell_size_ir",
    "cell_size_ir_champ",
    "cell_size_ir_champ_cone",
)


def _suffix(depth: int) -> str:
    if depth <= 0:
        return ""
    if depth == 1:
        return "_leftover"
    return f"_leftover{depth}"


def refine_cell_source(depth: int) -> str:
    """knobs.source of the size-up candidate at this depth."""
    return f"cell_size_ir_winning_region{_suffix(depth)}"


def refine_extract_source(depth: int) -> str:
    """knobs.source of the write_pg_spice candidate at this depth."""
    return f"f4_winning_ir_region_cell{_suffix(depth)}_extract"


def refine_pdn_via(depth: int) -> str:
    """attr.via of the winning-family PDN restamp at this depth."""
    return f"active_f4_winning_ir_region_cell{_suffix(depth)}_pdn"


def refine_catalog_via(depth: int) -> str:
    """attr.via of the unused Dynamic IR catalog restamp at this depth."""
    return f"active_f4_winning_ir_region_cell{_suffix(depth)}_catalog"


def _newest(mem: DesignMemory, *, level: str, source: str = "", via: str = ""):
    for c in reversed(list(mem.by_level(level))):
        if c.status != "ok":
            continue
        if source and (c.knobs or {}).get("source") != source:
            continue
        if via and (c.attr or {}).get("via") != via:
            continue
        return c
    return None


@dataclass
class RefinementFrame:
    """One depth of the refine chain, fully resolved from memory."""

    depth: int
    cell: object | None = None  # size-up Candidate
    extract: object | None = None  # write_pg_spice Candidate
    pdn: object | None = None  # winning-family restamp Candidate
    catalog: list = field(default_factory=list)  # unused-catalog Candidates
    cells: list[str] = field(default_factory=list)  # cells sized at this depth

    @property
    def extract_id(self) -> str:
        if self.extract is None:
            return ""
        return str((self.extract.knobs or {}).get("extract_id") or self.extract.id)


def base_sized_cells(mem: DesignMemory) -> set[str]:
    """Union of IR-cell / champ / leftover-cone size-up sets (newest each)."""
    out: set[str] = set()
    for src in BASE_SIZED_SOURCES:
        c = _newest(mem, level="cell", source=src)
        if c is not None:
            out.update(str(x) for x in (c.knobs or {}).get("cells") or [])
    return out


def refine_chain(mem: DesignMemory, *, max_depth: int = 32) -> list[RefinementFrame]:
    """Frames depth 0..N while a size-up exists at that depth."""
    frames: list[RefinementFrame] = []
    for depth in range(max_depth):
        cell = _newest(mem, level="cell", source=refine_cell_source(depth))
        if cell is None:
            break
        extract = _newest(mem, level="pdn", source=refine_extract_source(depth))
        pdn = _newest(mem, level="pdn", via=refine_pdn_via(depth))
        catalog = [
            c
            for c in mem.by_level("pdn")
            if c.status == "ok" and (c.attr or {}).get("via") == refine_catalog_via(depth)
        ]
        frames.append(
            RefinementFrame(
                depth=depth,
                cell=cell,
                extract=extract,
                pdn=pdn,
                catalog=catalog,
                cells=[str(x) for x in (cell.knobs or {}).get("cells") or []],
            )
        )
    return frames


def sized_through(mem: DesignMemory, depth: int) -> set[str]:
    """Base lineage ∪ refine cells at depths 0..depth inclusive."""
    out = base_sized_cells(mem)
    for f in refine_chain(mem):
        if f.depth <= depth:
            out.update(f.cells)
    return out


def leftover_cells(mem: DesignMemory, depth: int) -> list[str]:
    """Join cells on the depth-N restamp minus everything already sized.

    The join lives on the PDN restamp when present (its hotspot is the
    steer for depth N+1), else on the extract.
    """
    chain = refine_chain(mem)
    frame = next((f for f in chain if f.depth == depth), None)
    if frame is None:
        return []
    host = frame.pdn or frame.extract
    if host is None:
        return []
    sized = sized_through(mem, depth)
    cells = [str(x) for x in ((host.attr or {}).get("cells") or [])]
    return [c for c in cells if c not in sized]


def next_stage(mem: DesignMemory) -> dict | None:
    """First missing stage of the chain: the next generic action to consider.

    Order per depth: sizeup → extract → pdn → catalog → (leftover ≠ ∅ →
    sizeup at depth+1). Returns None when the chain is closed (leftover
    empty and catalog exhausted at the deepest frame).
    """
    from .pdn_space import next_winning_ir_pdn_spec

    chain = refine_chain(mem)
    if not chain:
        return None
    tail = chain[-1]
    if tail.extract is None:
        return {"depth": tail.depth, "stage": "extract"}
    if tail.pdn is None:
        return {"depth": tail.depth, "stage": "pdn"}
    if next_winning_ir_pdn_spec(mem, tail.pdn) is not None:
        return {"depth": tail.depth, "stage": "catalog"}
    left = leftover_cells(mem, tail.depth)
    if left:
        return {"depth": tail.depth + 1, "stage": "sizeup", "cells": left}
    return None
