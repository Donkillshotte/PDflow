"""LLM-as-proposer hook + symbolic fallback. Never the optimizer.

Attribution and stagnation produce *candidates*. F1 / F2 / F4 oracles still
measure. Physical and PDN knobs never appear in a logic proposal.

Set DSE_LLM_URL to POST a JSON brief; if unset, only the symbolic proposer
runs. Missing credentials must not block the controller.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .abc_space import BOILS_STD_OPS
from .arch_space import plan_dpath_extracts
from .memory import DesignMemory


def _best_logic_ops(mem: DesignMemory) -> list[str] | None:
    ok = [c for c in mem.by_level("logic") if c.status == "ok" and c.qor.area_um2 is not None]
    if not ok:
        return None
    best = min(ok, key=lambda c: float(c.qor.area_um2))
    return list(best.knobs.get("abc_ops") or [])


def _areas(mem: DesignMemory) -> list[float]:
    return sorted(
        float(c.qor.area_um2)
        for c in mem.by_level("logic")
        if c.status == "ok" and c.qor.area_um2 is not None
    )


def stagnating(mem: DesignMemory, *, n: int = 3, tol: float = 0.01) -> bool:
    xs = _areas(mem)
    if len(xs) < n:
        return False
    tail = xs[:n]
    return max(tail) <= min(tail) * (1.0 + tol)


def symbolic_propose(
    mem: DesignMemory, *, focus: str, attr: dict | None = None, design_id: str = "gcd"
) -> list[dict]:
    """Rule proposer: unused cone extracts, unused STD append, stagnation nudge."""
    from .designs import resolve

    spec = resolve(design_id)
    out: list[dict] = []
    attr = attr or {}
    combo = float(attr.get("combo_frac") or 0.0)
    extracts: list[str] = []
    if spec.arch_extracts:
        _eg, _r, extracts, _st = plan_dpath_extracts()
    seen_ex = {c.knobs.get("extract") for c in mem.by_level("architecture") if c.status == "ok"}
    default_mod = spec.cones[0] if spec.cones else spec.top
    for name in extracts:
        if name in seen_ex:
            continue
        out.append(
            {
                "level": "architecture",
                "name": name,
                "extract": name,
                "module": focus if focus != "chip" else default_mod,
                "scope": "logic_cone",
                "via": "symbolic_proposer",
                "why": f"unused e-graph extract on {focus} (combo={combo:.2f})",
            }
        )
    best = _best_logic_ops(mem)
    if best is not None and len(best) < 12:
        used_tail = {tuple(c.knobs.get("abc_ops") or []) for c in mem.by_level("logic")}
        prefer = list(BOILS_STD_OPS)
        if stagnating(mem):
            prefer = ["refactor -z", "resub -z", "rewrite -z", *prefer]
        for op in prefer:
            seq = [*best, op]
            if tuple(seq) in used_tail:
                continue
            out.append(
                {
                    "level": "logic",
                    "name": "propose_" + op.replace(" ", ""),
                    "abc_args": [],
                    "abc_ops": seq,
                    "abc_script": "file",
                    "via": "symbolic_proposer",
                    "why": "stagnation" if stagnating(mem) else "unused STD append",
                    "focus": focus,
                }
            )
            break
    return out


def llm_propose(
    mem: DesignMemory, *, focus: str, attr: dict | None = None, design_id: str = "gcd"
) -> list[dict] | None:
    """Optional HTTP proposer. Returns None if unconfigured or the call fails.

    `DSE_LLM=mock` is the CI path: one BOiLS-alphabet proposal, no network,
    never a physical/PDN knob.
    """
    if os.environ.get("DSE_LLM") == "mock":
        return [
            {
                "level": "logic",
                "name": "llm_mock_rewrite",
                "abc_args": [],
                "abc_ops": ["rewrite"],
                "abc_script": "file",
                "via": "llm_proposer_mock",
                "why": "CI mock — proposer only, not the optimizer",
                "focus": focus,
                "design_id": design_id,
            }
        ]
    url = os.environ.get("DSE_LLM_URL")
    if not url:
        return None
    brief = {
        "role": "proposer_only",
        "focus": focus,
        "attr": {
            "modules": (attr or {}).get("modules"),
            "combo_frac": (attr or {}).get("combo_frac"),
            "scope": (attr or {}).get("scope"),
            "region": (attr or {}).get("region"),
        },
        "seen_logic": [c.knobs.get("name") for c in mem.by_level("logic")[:12]],
        "instruction": (
            "Propose at most 3 logic ABC sequences from the BOiLS STD alphabet "
            "or unused dpath extracts. Do not mix coreUtilization or pkg_l. "
            "You are not the optimizer."
        ),
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(brief).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None
    rows = body.get("proposals") if isinstance(body, dict) else body
    if not isinstance(rows, list):
        return None
    clean: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if "coreUtilization" in row or "pkg_l" in row or "c_decap" in row:
            continue
        row = dict(row)
        row["via"] = "llm_proposer"
        clean.append(row)
    return clean or None


def propose(
    mem: DesignMemory, *, focus: str, attr: dict | None = None, design_id: str = "gcd"
) -> list[dict]:
    llm = llm_propose(mem, focus=focus, attr=attr, design_id=design_id)
    if llm:
        return llm
    return symbolic_propose(mem, focus=focus, attr=attr, design_id=design_id)
