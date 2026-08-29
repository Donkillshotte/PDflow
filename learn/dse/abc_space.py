"""Logic-level ABC alphabet — BOiLS standard ops, not mixed with P&R knobs.

Reference: Grosnit et al., BOiLS (DATE 2022); HEBO/BOiLS ActionSimple set
{rewrite, rewrite -z, refactor, refactor -z, resub, resub -z, balance}.
Sequences stay on the logic level. Physical/PDN knobs are a different level.
"""

from __future__ import annotations

# BOiLS STD_ACTION_SPACE act_id strings (HEBO/BOiLS ActionSimple).
BOILS_STD_OPS = (
    "rewrite",
    "rewrite -z",
    "refactor",
    "refactor -z",
    "resub",
    "resub -z",
    "balance",
)

# Named Yosys-abc liberty mapping modes that keep a real Nangate map
# (a raw +strash script without map under-counts area — do not use that).
CATALOG: list[dict] = [
    {
        "name": "liberty_default",
        "abc_args": [],
        "abc_ops": [],
        "note": "Yosys abc -liberty (ORFS-class default map)",
    },
    {
        "name": "liberty_fast",
        "abc_args": ["-fast"],
        "abc_ops": [],
        "note": "Yosys abc -fast (cheaper map, usually larger)",
    },
    {
        "name": "boils_rewrite_balance",
        "abc_args": [],
        "abc_ops": ["rewrite", "balance"],
        "note": "BOiLS ops appended to default liberty map (+rewrite;balance)",
    },
    {
        "name": "boils_resyn2ish",
        "abc_args": [],
        "abc_ops": ["balance", "rewrite", "rewrite -z", "balance", "rewrite -z", "balance"],
        "note": "resyn2-class sequence from the BOiLS/ABC cookbook, not a fork",
    },
]


def abc_script_plus(ops: list[str]) -> str | None:
    """Yosys `abc -script +…` form. Spaces in ops become commas (`rewrite,-z`).

    Yosys replaces commas with blanks and leaves `;` as ABC separators.
    Prefer write_abc_script() inside `-p`/`-s` so `;` never hits the Yosys lexer.
    """
    if not ops:
        return None
    body = list(ops)
    if body[0] != "strash":
        body = ["strash", *body]
    parts = [p.replace(" ", ",") for p in body]
    return f"+{';'.join(parts)}"


def write_abc_script(ops: list[str], path, *, map_liberty: bool = False) -> None:
    """ABC script *file* (one command per line). rewrite needs strash first.

    When map_liberty=True the script ends with ``map`` so Yosys `abc -liberty
    -script` actually emits standard cells instead of leftover $lut.
    """
    body = list(ops)
    if body and body[0] != "strash":
        body = ["strash", *body]
    elif not body:
        body = ["strash"]
    if map_liberty and body[-1] != "map":
        body.append("map")
    path.write_text("\n".join(body) + "\n")


def subsequence_kernel(a: list[str], b: list[str], ell: int = 2) -> float:
    """BOiLS-style substring kernel on op strings (order-ℓ contiguous).

    Used for *diversity*, not as QoR truth. Empty sequences are a unique token.
    """
    def grams(seq: list[str]) -> list[tuple[str, ...]]:
        s = seq or ["∅"]
        out = []
        for n in range(1, min(ell, len(s)) + 1):
            out.extend(tuple(s[i : i + n]) for i in range(len(s) - n + 1))
        return out

    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    from collections import Counter

    ca, cb = Counter(ga), Counter(gb)
    dot = sum(ca[k] * cb[k] for k in ca)
    na = sum(v * v for v in ca.values()) ** 0.5
    nb = sum(v * v for v in cb.values()) ** 0.5
    if na <= 0 or nb <= 0:
        return 0.0
    return float(dot / (na * nb))


def min_kernel_to_seen(ops: list[str], seen: list[list[str]]) -> float:
    if not seen:
        return 0.0
    return min(subsequence_kernel(ops, s) for s in seen)
