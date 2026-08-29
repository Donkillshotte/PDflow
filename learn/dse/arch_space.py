"""Architecture-level equivalence-preserving RTL extracts and cone stamps.

Hierarchical: an attributed cone is rewritten or remapped; the inverse
modules stay default-mapped. Full-chip F1 equiv still runs on `gcd`.

Architecture extracts stay on the dpath operators (e-graph). Cone ABC is
a separate first-class transform: `dpath` or `ctrl`, never a leftover
placeholder and never a silent flatten of the whole chip.

Extracts are emitted only when the e-graph discovered the equality
(see egraph.available_extracts). This is ROVER/ASPEN-shaped:
saturate → extract → measure with a real EDA oracle — not an LLM rewrite.
"""

from __future__ import annotations

from pathlib import Path

from .egraph import EGraph, available_extracts, egraph_stats, gcd_dpath_egraph

# Exact PyMTL-emitted bodies in learn/flowlab/gcd.v
_SUB_ORIG = "    out = (in0-in1);"
_SUB_TWOS = "    out = in0 + ((~in1) + 16'd1);"
_EQZ_ORIG = "    out = (in_ == 0);"
_EQZ_ORRED = "    out = ~(|in_);"
_LT_ORIG = "    out = (in0 < in1);"
_LT_BORROW_BLOCK = """  wire [16:0] _dse_lt_ext;
  assign _dse_lt_ext = {1'b0, in0} - {1'b0, in1};
  always @ (*) begin
    out = _dse_lt_ext[16];
  end"""


# Yosys modules after hierarchical `synth -top gcd` (no flatten).
# Cone ABC remaps the paid cone; leftover = known modules minus that cone.
DPATH_MODULE = "GcdUnitDpathRTL_0x4d0fc71ead8d3d9e"
CTRL_MODULE = "GcdUnitCtrlRTL_0x4d0fc71ead8d3d9e"
DPATH_CONE_MODULES = (
    DPATH_MODULE,
    "RegEn_0x68db79c4ec1d6e5b",
    "LtComparator_0x422b1f52edd46a85",
    "ZeroComparator_0x422b1f52edd46a85",
    "Mux_0x683fa1a418b072c9",
    "Mux_0xdd6473406d1a99a",
    "Subtractor_0x422b1f52edd46a85",
)
# Inverse of the dpath cone: FSM + reset regs. First-class when STA
# attributes `ctrl/` hops — not a leftover placeholder of dpath ABC.
LEFTOVER_MODULES = (
    CTRL_MODULE,
    "RegRst_0x9f365fdf6c8998a",
)
CTRL_CONE_MODULES = list(LEFTOVER_MODULES)
KNOWN_SUB_MODULES = list(dict.fromkeys(list(DPATH_CONE_MODULES) + list(CTRL_CONE_MODULES)))


def is_cone_abc(knobs: dict | None) -> bool:
    """Explicit cone ABC — not architecture `scope=logic_cone` (flatten-first)."""
    k = knobs or {}
    cone = k.get("cone")
    return bool(k.get("cone_module") or cone in ("dpath", "ctrl"))


def leftover_modules(cone_mods: list[str] | tuple[str, ...], top: str = "gcd") -> list[str]:
    """Submodules that stay default-mapped, plus the top. Inverse of the paid cone."""
    paid = set(cone_mods)
    leftover = [m for m in KNOWN_SUB_MODULES if m not in paid]
    leftover.append(top)
    return leftover


def cone_modules_for(knobs: dict | None) -> list[str]:
    """Paid Yosys modules for a cone-ABC proposal."""
    k = knobs or {}
    if k.get("cone_modules"):
        return [str(m) for m in k["cone_modules"]]
    if k.get("cone") == "ctrl" or k.get("cone_module") == CTRL_MODULE:
        return list(CTRL_CONE_MODULES)
    return list(DPATH_CONE_MODULES)


def stamp_cone_knobs(knobs: dict, focus: str) -> dict:
    """Same ABC sequence, scoped to one named cone. Chip flatten-first stays unstamped.

    `ctrl` is its own cone (FSM + RegRst), not a leftover of the dpath cone
    and not a chip restart. `scope=logic_cone` without `cone`/`cone_module`
    is not enough — that used to silently flatten the whole chip.
    """
    out = dict(knobs)
    if focus == "dpath":
        out["scope"] = "logic_cone"
        out["cone"] = "dpath"
        out["cone_module"] = DPATH_MODULE
        out["cone_modules"] = list(DPATH_CONE_MODULES)
        return out
    if focus == "ctrl":
        out["scope"] = "logic_cone"
        out["cone"] = "ctrl"
        out["cone_module"] = CTRL_MODULE
        out["cone_modules"] = list(CTRL_CONE_MODULES)
        return out
    return knobs

EXTRACTS: dict[str, dict] = {
    "sub_twos_complement": {
        "module": "Subtractor_0x422b1f52edd46a85",
        "cone": "dpath",
        "operator": "sub",
        "note": "a-b ≡ a+(~b+1)  (two's complement, 16-bit)",
    },
    "eqz_or_reduce": {
        "module": "ZeroComparator_0x422b1f52edd46a85",
        "cone": "dpath",
        "operator": "eqz",
        "note": "(x==0) ≡ ~(|x)",
    },
    "lt_borrow": {
        "module": "LtComparator_0x422b1f52edd46a85",
        "cone": "dpath",
        "operator": "lt",
        "note": "unsigned a<b ≡ borrow of {0,a}-{0,b}",
    },
}


def plan_dpath_extracts() -> tuple[EGraph, dict, list[str], dict]:
    eg, roots = gcd_dpath_egraph()
    names = available_extracts(eg, roots)
    return eg, roots, names, egraph_stats(eg, roots)


def emit_gcd_variant(src: Path, extract: str, dest: Path) -> dict:
    """Rewrite one dpath operator in a copy of gcd.v. Fails loud if the body moved."""
    if extract not in EXTRACTS:
        raise ValueError(f"unknown extract {extract}")
    text = Path(src).read_text()
    if extract == "sub_twos_complement":
        if _SUB_ORIG not in text:
            raise ValueError("Subtractor body not found — refuse to guess")
        text = text.replace(_SUB_ORIG, _SUB_TWOS, 1)
    elif extract == "eqz_or_reduce":
        if _EQZ_ORIG not in text:
            raise ValueError("ZeroComparator body not found — refuse to guess")
        text = text.replace(_EQZ_ORIG, _EQZ_ORRED, 1)
    elif extract == "lt_borrow":
        old = "  always @ (*) begin\n    out = (in0 < in1);\n  end"
        # LtComparator is the first `in0 < in1` always block
        if old not in text:
            raise ValueError("LtComparator body not found — refuse to guess")
        text = text.replace(old, _LT_BORROW_BLOCK, 1)
    dest = Path(dest)
    dest.write_text(text)
    meta = dict(EXTRACTS[extract])
    meta["extract"] = extract
    meta["rtl"] = str(dest)
    return meta
