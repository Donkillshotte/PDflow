"""Attribution → next level. Does not flatten knobs across levels.

Physical feedback chooses *where* to search (chip→block→region→cone):
  combo IR on a module  → architecture extracts on that cone
  F3 WNS on an extract  → deprioritize extracts that lost slack
  spatial IR region     → physical density, not more ABC
  high GRT congestion   → physical F0 / GPL, not more ABC
  ctrl hops on the path → cone-local ABC on the FSM (not leftover of dpath)
  otherwise             → logic BOiLS/DRiLLS (EHVI area+WNS), then F2 / GPL
"""

from __future__ import annotations

from .arch_space import plan_dpath_extracts
from .memory import DesignMemory
from .mo import baseline_wns, extract_wns, timing_bound


def plan_search(attr: dict, mem: DesignMemory, *, f2_cong: float | None) -> dict:
    modules = list(attr.get("modules") or [])
    region = attr.get("region")
    focus = modules[0] if modules else (region or "chip")
    combo = float(attr.get("combo_frac") or 0.0)
    seq = float(attr.get("seq_frac") or 0.0)
    scope = attr.get("scope") or ("logic_cone" if modules else "chip")
    slack = None
    hot = (attr.get("hotspot") or {}) if isinstance(attr.get("hotspot"), dict) else {}
    timing = hot.get("timing") if isinstance(hot, dict) else None
    if isinstance(timing, dict) and timing.get("path_slack_ns") is not None:
        slack = float(timing["path_slack_ns"])
    bound = timing_bound(mem, slack_ns=slack)
    steps: list[dict] = []
    _eg, _r, extracts, _st = plan_dpath_extracts()
    unseen_arch = rank_extracts(extracts, mem, combo=combo)
    if scope == "logic_cone" and focus != "chip" and combo >= 0.5 and unseen_arch:
        why = f"combo IR {combo:.2f} on {focus} — cone extracts, no chip restart"
        if bound:
            why += "; F3 WNS reorders remaining extracts"
        steps.append(
            {
                "level": "architecture",
                "reason": why,
                "extracts": unseen_arch,
                "scope": "logic_cone",
            }
        )
    if (f2_cong is not None and f2_cong > 0.25) or (scope == "region" and region):
        why = (
            f"F2 congestion {f2_cong:.3f} — prefer physical knobs over more ABC"
            if f2_cong is not None and f2_cong > 0.25
            else f"IR region {region} — physical density, not a chip restart"
        )
        steps.append({"level": "physical", "reason": why, "scope": "region" if region else "block"})
    else:
        logic_why = "BOiLS SSK-GP + DRiLLS UCB on ABC sequences"
        if bound or extract_wns(mem):
            logic_why = "BOiLS EHVI(area, WNS) + DRiLLS UCB — F3 steers ABC, not area-only"
        if focus == "dpath" or "dpath" in modules:
            logic_why += "; cone-local ABC on dpath (chip flatten-first teacher already measured)"
        steps.append(
            {
                "level": "logic",
                "reason": logic_why,
                "scope": "logic_cone" if (focus == "dpath" or "dpath" in modules) else ("block" if focus != "chip" else "chip"),
            }
        )
        if focus == "ctrl" or "ctrl" in modules:
            steps.append(
                {
                    "level": "logic_ctrl",
                    "reason": (
                        "STA/IR attributes ctrl hops — cone-local ABC on the FSM "
                        "(not leftover of dpath, not a chip restart)"
                    ),
                    "scope": "logic_cone",
                    "cone": "ctrl",
                }
            )
    steps.append(
        {
            "level": "f2_fast",
            "reason": "anchored barycenter HPWL/RUDY on the best F1 netlist (not make finish)",
            "scope": "chip",
        }
    )
    steps.append(
        {
            "level": "f2_gpl",
            "reason": "budgeted OpenROAD GPL -skip_io on the F1 winner — not route/F5/IR",
            "scope": "chip",
        }
    )
    steps.append(
        {
            "level": "f3_sta",
            "reason": "OpenSTA ideal WNS/power interleaved after each F1 — not SPEF, not IR",
            "scope": "block" if focus != "chip" else "chip",
        }
    )
    steps.append(
        {
            "level": "routing",
            "reason": "budgeted OpenROAD GRT after place_pins — not detailed route/F5",
            "scope": "chip",
        }
    )
    steps.append(
        {
            "level": "f3_sdf",
            "reason": "OpenSTA + GRT SDF after estimate_parasitics — not SPEF/OpenRCX, not F5",
            "scope": "chip",
        }
    )
    steps.append(
        {
            "level": "f5_drt",
            "reason": "budgeted detailed_route + OpenRCX SPEF — F5-lite, not make finish",
            "scope": "chip",
        }
    )
    steps.append(
        {
            "level": "f3_spef",
            "reason": "OpenSTA + OpenRCX SPEF on the F5 netlist — not GRT SDF, not finish launch",
            "scope": "chip",
        }
    )
    steps.append(
        {
            "level": "f5_cts",
            "reason": "budgeted CTS + DRT + OpenRCX SPEF — propagated clock, not make finish",
            "scope": "chip",
        }
    )
    steps.append(
        {
            "level": "f5_local",
            "reason": (
                "OpenRCX SPEF on the cell/net netlist — F3→F5 residual vs F1 F5-lite, "
                "not a reused SPEF, not make finish"
            ),
            "scope": "net",
        }
    )
    steps.append(
        {
            "level": "residual_steer",
            "reason": (
                "F3→F5 residual + uncertainty pick the next local level "
                "(other host SPEF, or SPEF-path cell/net) — not a mixed knob vector"
            ),
            "scope": "net",
        }
    )
    steps.append(
        {
            "level": "f5_port",
            "reason": (
                "OpenRCX SPEF on the port-net BUF netlist — F3→F5 residual, "
                "not the intra-module net host, not make finish"
            ),
            "scope": "port",
        }
    )
    steps.append(
        {
            "level": "synthesis",
            "reason": "ORFS abc_speed.script (ABC_AREA=0) — measured synthesis F1, not logic -fast",
            "scope": "chip",
        }
    )
    cell_n = len(attr.get("cells") or [])
    steps.append(
        {
            "level": "cell",
            "reason": (
                f"upsize {cell_n} attributed worst-path cells — not more ABC, not a chip restart"
                if cell_n
                else "upsize OpenSTA worst-path cells after F3 — cell-local, not ABC"
            ),
            "scope": "cell",
        }
    )
    net_n = len(attr.get("nets") or [])
    steps.append(
        {
            "level": "net",
            "reason": (
                f"insert BUF on {net_n} attributed worst-path hops — net-local, not ABC"
                if net_n
                else "insert BUF on OpenSTA worst-path hops after F3 — net-local, not ABC"
            ),
            "scope": "net",
        }
    )
    steps.append(
        {
            "level": "net_port",
            "reason": (
                "insert BUF on attributed ctrl↔dpath port nets at the parent "
                "— not intra-module hops, not ABC"
            ),
            "scope": "port",
        }
    )
    steps.append(
        {
            "level": "f4_amg",
            "reason": "SA-AMG restamp on the named extract — MF solver residual vs DirectLU, not gold",
            "scope": "chip",
        }
    )
    steps.append(
        {
            "level": "f4_ras",
            "reason": "RAS restamp after AMG — domain-decomp MF residual vs DirectLU, not gold",
            "scope": "chip",
        }
    )
    steps.append(
        {
            "level": "f4_krylov",
            "reason": "rational Krylov/MOR restamp after RAS — reduced-order residual vs DirectLU, not gold",
            "scope": "chip",
        }
    )
    steps.append(
        {
            "level": "physical_catalog",
            "reason": "measure one AutoDMP util/density point with GPL (not F0-only RUDY)",
            "scope": "region" if region else "chip",
        }
    )
    if region or (isinstance(attr.get("x_dbu"), (int, float)) and isinstance(attr.get("y_dbu"), (int, float))):
        steps.append(
            {
                "level": "f2_region",
                "reason": (
                    f"IR hotspot region {region or 'xy'} — OpenROAD density cap on that bin, "
                    "not more ABC, not a chip restart"
                ),
                "scope": "region",
                "region": region,
            }
        )
        steps.append(
            {
                "level": "f4_region_extract",
                "reason": (
                    f"write_pg_spice under the {region or 'IR'} density cap — new R-graph, "
                    "not the unconstrained extract, not gold"
                ),
                "scope": "region",
                "region": region,
            }
        )
    ir_up = _ir_rose(mem)
    steps.append(
        {
            "level": "f4_extract",
            "reason": (
                "write_pg_spice after place_pins+GPL+DP+pdngen on the F1 incumbent "
                "— new R-graph, not the finish mesh, not gold"
            ),
            "scope": "chip",
        }
    )
    pdn_why = "Solver A restamp on the named extract (c_decap/pkg L) — not gold, not finish"
    if ir_up:
        pdn_why += "; scaled I(t) IR rose — keep PDN knobs off the ABC vector"
    steps.append({"level": "pdn", "reason": pdn_why, "scope": "chip"})
    steps.append(
        {
            "level": "f4_scale",
            "reason": (
                "I(t)×P_F3/P_base on the WNS/power incumbent — candidate mesh if extracted, "
                "not a VCD remap"
                + ("; IR feedback to the cone, no chip restart" if focus != "chip" else "")
            ),
            "scope": "logic_cone" if focus != "chip" else "chip",
        }
    )
    steps.append(
        {
            "level": "ir_steer",
            "reason": (
                "F4 mesh/knob/region residual picks the next PDN action "
                "(winning decap on the region mesh, or unused pkg L) — not ABC, not a mixed vector"
            ),
            "scope": "region" if region else "chip",
        }
    )
    return {
        "focus": focus,
        "combo_frac": combo,
        "seq_frac": seq,
        "f2_cong": f2_cong,
        "region": region,
        "scope": scope,
        "timing_bound": bound,
        "ir_rose": ir_up,
        "restart_chip": False,
        "hierarchy": ["chip", "block", "region", "logic_cone", "cell", "net"],
        "steps": steps,
    }


def rank_extracts(extracts: list[str], mem: DesignMemory, *, combo: float) -> list[str]:
    """IR order, then F3 WNS: measured-worse extracts go last; unseen stay first."""
    prefer = _ir_prefer(extracts, combo=combo)
    seen = {c.knobs.get("extract") or c.knobs.get("name") for c in mem.by_level("architecture")}
    unseen = [e for e in prefer if e not in seen]
    timed = extract_wns(mem)
    base = baseline_wns(mem)

    def key(e: str) -> tuple:
        w = timed.get(e)
        ir_i = prefer.index(e) if e in prefer else 99
        if w is None:
            return (0, ir_i, 0.0)
        worse = base is not None and w > base + 1e-6
        return (1 if worse else 0, ir_i if not worse else 0, w)

    unseen.sort(key=key)
    return unseen


def _ir_prefer(extracts: list[str], *, combo: float) -> list[str]:
    """Combo-heavy IR → compare/sub first (datapath), then zero-test."""
    prefer = ["lt_borrow", "sub_twos_complement", "eqz_or_reduce"] if combo >= 0.5 else list(extracts)
    out = [e for e in prefer if e in extracts]
    for e in extracts:
        if e not in out:
            out.append(e)
    return out


def _ir_rose(mem: DesignMemory) -> bool:
    """True when a candidate F4 droop exceeds the ingested gold observation."""
    ingest = None
    cand = None
    for c in mem.by_level("pdn"):
        if c.status != "ok" or c.qor.dynamic_ir_mv is None:
            continue
        src = (c.knobs or {}).get("source")
        if src == "ingest_pdn":
            ingest = float(c.qor.dynamic_ir_mv)
        elif src in ("f4_iscale", "f4_solver_a", "f4_candidate_extract", "f4_region_extract"):
            v = float(c.qor.dynamic_ir_mv)
            cand = v if cand is None else max(cand, v)
    return ingest is not None and cand is not None and cand > ingest + 0.05


def _prefer_extracts(extracts: list[str], *, combo: float) -> list[str]:
    """Back-compat wrapper used by tests — IR order with no WNS memory."""
    return _ir_prefer(extracts, combo=combo)
