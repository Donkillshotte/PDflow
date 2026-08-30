"""Registered designs. GCD cone names stay in GCD fixtures only.

aes (and later ibex) share the refine / F4 / PDN stack without inheriting
`dpath` / `ctrl` / e-graph extracts. Architecture extracts and FSM-cone ABC
are opt-in per DesignSpec.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ORFS_SRC = REPO / "tools" / "OpenROAD-flow-scripts" / "flow" / "designs" / "src"


@dataclass(frozen=True)
class DesignSpec:
    id: str
    top: str
    rtl: Path
    rtl_files: tuple[Path, ...]
    platform: str = "nangate45"
    orfs_name: str = ""
    cones: tuple[str, ...] = ()
    arch_extracts: bool = False

    @property
    def orfs_design(self) -> str:
        return self.orfs_name or self.id

    def has_cone(self, name: str) -> bool:
        return name in self.cones


def _aes_rtl_files() -> tuple[Path, ...]:
    src = ORFS_SRC / "aes"
    files = tuple(
        p
        for p in sorted(src.glob("*.v"))
        if p.name != "timescale.v"
    )
    return files


DESIGNS: dict[str, DesignSpec] = {
    "gcd": DesignSpec(
        id="gcd",
        top="gcd",
        rtl=REPO / "learn" / "flowlab" / "gcd.v",
        rtl_files=(REPO / "learn" / "flowlab" / "gcd.v",),
        orfs_name="gcd",
        cones=("dpath", "ctrl"),
        arch_extracts=True,
    ),
    "aes": DesignSpec(
        id="aes",
        top="aes_cipher_top",
        rtl=ORFS_SRC / "aes" / "aes_cipher_top.v",
        rtl_files=_aes_rtl_files(),
        orfs_name="aes",
        cones=(),
        arch_extracts=False,
    ),
}


def resolve(design_id: str) -> DesignSpec:
    if design_id not in DESIGNS:
        raise KeyError(f"unknown design {design_id} — registered: {sorted(DESIGNS)}")
    return DESIGNS[design_id]


def design_rtl(design_id: str = "gcd") -> Path:
    return resolve(design_id).rtl
