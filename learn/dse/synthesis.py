"""Replaceable synthesis adapter.

Logic F1 is Yosys ``abc -liberty`` / BOiLS ``abc_ops`` (teacher 409.108).
Synthesis F1 is the ORFS delay recipe (``ABC_AREA=0`` → ``abc_speed.script``
plus ``-D`` clock). Area-script (``ABC_AREA=1``) stays F0-only — same teacher
family as liberty_default on this GCD.

Do not put ``abc_ops`` on synthesis knobs (that flattens into the logic e-graph).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORFS_SCRIPTS = ROOT / "tools" / "OpenROAD-flow-scripts" / "flow" / "scripts"
ABC_SPEED = ORFS_SCRIPTS / "abc_speed.script"
ABC_AREA = ORFS_SCRIPTS / "abc_area.script"
# Nangate45 gcd constraint.sdc: create_clock -period 0.46 → ABC -D is picoseconds.
CLK_PERIOD_PS = 460


def orfs_abc_script(*, abc_area: bool) -> Path:
    return ABC_AREA if abc_area else ABC_SPEED


def synth_f1_knobs() -> dict:
    return {
        "name": "orfs_abc_speed",
        "abcArea": 0,
        "source": "orfs_abc_script",
        "abc_args": synth_abc_args(),
        "abc_script": "file",
    }


def synth_abc_args() -> list[str]:
    """Extra Yosys-abc args. Caller already prepends ``-liberty``."""
    return ["-script", str(ABC_SPEED), "-D", str(CLK_PERIOD_PS)]


def available() -> bool:
    return ABC_SPEED.is_file()
