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
    include_dirs: tuple[Path, ...] = ()
    hdl: str = "verilog"
    f1_equiv: bool = True
    f1_timeout_s: float = 60.0
    f1_ready: bool = True

    @property
    def orfs_design(self) -> str:
        return self.orfs_name or self.id

    def has_cone(self, name: str) -> bool:
        return name in self.cones


def _aes_rtl_files() -> tuple[Path, ...]:
    """Cipher-top closure only — inv_* is a second top, not this design."""
    src = ORFS_SRC / "aes"
    names = ("aes_cipher_top.v", "aes_key_expand_128.v", "aes_sbox.v", "aes_rcon.v")
    return tuple(src / n for n in names)


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
        include_dirs=(ORFS_SRC / "aes",),
        f1_equiv=False,
        f1_timeout_s=240.0,
    ),
    "ibex": DesignSpec(
        id="ibex",
        top="ibex_core",
        rtl=ORFS_SRC / "ibex_sv" / "ibex_core.sv",
        rtl_files=(ORFS_SRC / "ibex_sv" / "ibex_core.sv",),
        orfs_name="ibex",
        cones=(),
        arch_extracts=False,
        include_dirs=(ORFS_SRC / "ibex_sv" / "vendor" / "lowrisc_ip" / "prim" / "rtl",),
        hdl="systemverilog",
        f1_equiv=False,
        f1_timeout_s=300.0,
        f1_ready=False,
    ),
}


def resolve(design_id: str) -> DesignSpec:
    if design_id not in DESIGNS:
        raise KeyError(f"unknown design {design_id} — registered: {sorted(DESIGNS)}")
    return DESIGNS[design_id]


def design_rtl(design_id: str = "gcd") -> Path:
    return resolve(design_id).rtl


def rtl_inputs(rtl: Path, design_id: str) -> tuple[list[Path], list[Path]]:
    """Files + include dirs for Yosys. Architecture extract copies stay single-file."""
    spec = resolve(design_id)
    src = Path(rtl)
    if src.resolve() == spec.rtl.resolve():
        return list(spec.rtl_files), list(spec.include_dirs)
    return [src], list(spec.include_dirs)
