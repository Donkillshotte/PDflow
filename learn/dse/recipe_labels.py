"""Human-readable recipe names for campaign experiments.

`variant` stays the ORFS FLOW_VARIANT id (filesystem). Tables show `title`
(what it does) and `payoff` (what we learned). Labels are derived from role
and knobs — not from a per-design if/else on the design name.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RecipeLabel:
    title: str
    does: str
    payoff: str


# Explicit overrides for the runs people actually read. Ids stay camp_*.
_EXPLICIT: dict[str, RecipeLabel] = {
    "camp_gcd_base": RecipeLabel(
        "ORFS default — area synthesis, util 35, place +0.20",
        "Official gcd recipe: ABC area, floorplan util 35%, GPL density addon 0.20, TNS repair 100%.",
        "Reference. WNS −37 ps, area 940 µm², IR worst 6.67 mV / mean ~2.6 mV.",
    ),
    "camp_gcd_q1_d25u35": RecipeLabel(
        "Denser placement, same die — fewer repair buffers",
        "Same netlist and same util 35. Only PLACE_DENSITY_LB_ADDON 0.20→0.25.",
        "§5 win: area −10.5%, power −13%, leak −14%, IR −8%, WL −8%.",
    ),
    "camp_ibex_base": RecipeLabel(
        "ORFS default — area synthesis, util 50, place +0.20",
        "Official ibex recipe: ABC area, util 50%, density addon 0.20.",
        "Reference. WNS +22 ps, power 108 mW, IR worst 124 mV.",
    ),
    "camp_ibex_q1_d20u60": RecipeLabel(
        "Tighter core — smaller die, shorter wires",
        "Same netlist and same density addon 0.20. CORE_UTILIZATION 50→60.",
        "Lab (smaller die, util 50→60). Better slack/IR, but moved the floorplan. Not a product win.",
    ),
    "camp_ibex_q1_d25u50": RecipeLabel(
        "Denser placement, same die",
        "Same netlist and util 50. PLACE_DENSITY_LB_ADDON 0.20→0.25.",
        "§5 win slack (+40 vs +22 ps). Area/power ~same.",
    ),
    "camp_ibex_q1_d15u50": RecipeLabel(
        "Sparser placement, same die",
        "Same netlist and util 50. PLACE_DENSITY_LB_ADDON 0.20→0.15.",
        "§5 win slack (+36 vs +22 ps). Area/power ~same.",
    ),
    "camp_ibex_q1_d20u40": RecipeLabel(
        "Looser core — larger die, longer wires",
        "Same netlist. CORE_UTILIZATION 50→40.",
        "Lose: WNS −6 ps, WL +5%. Counterexample to tighter core.",
    ),
    "camp_gcd_q4_d25u35_c055": RecipeLabel(
        "Denser placement at the clock where the default closes (0.55 ns)",
        "Same knobs as gcd win, SDC 0.55 ns (area regime).",
        "False I4: closes like default, area 698 vs 697. Win does not transfer across clock.",
    ),
    "camp_gcd_dse_small": RecipeLabel(
        "Netlist DSE rewrite (sub_twos_complement) — place/route same as default",
        "Only changes mapped Verilog. Floorplan/place/CTS = default.",
        "Lose: WNS −338 vs −37 ps. Synthesis rewrite is not a product win.",
    ),
    "camp_gcd_dse_fast": RecipeLabel(
        "ABC delay synthesis on the same physical recipe",
        "ABC speed, default util/density.",
        "Lose: WNS −187 ps, power +41%. ABC delay does not beat ABC area + physical knobs.",
    ),
    "camp_gcd_dse_fixedb": RecipeLabel(
        "Netlist DSE rewrite on default die (geometry control)",
        "Same DSE Verilog as B, DIE_AREA locked to A.",
        "Lose: still ~−350 ps. Not a die-size problem.",
    ),
    "camp_spi_place_denser": RecipeLabel(
        "Denser placement",
        "Same official netlist. PLACE_DENSITY_LB_ADDON 0.20→0.25. Util stays config default (8).",
        "Transfer miss on spi: WNS −1.5 ps (tie), area +0.2%, same 22 buffers. The gcd lever does not transfer on an already closed, sparse die.",
    ),
    "camp_spi_repair_half_tns": RecipeLabel(
        "Half TNS repair",
        "Same official netlist. TNS_END_PERCENT 100→50. Util stays 8.",
        "On spi changes nothing: already met timing.",
    ),
    "camp_spi_place_sparser": RecipeLabel(
        "Sparser placement",
        "Slightly wider cells (density addon 0.20→0.15).",
        "On spi almost same as default. Slightly longer wires.",
    ),
    "camp_spi_cell_pad_plus": RecipeLabel(
        "Cell padding +1 site",
        "One site of extra space between cells.",
        "On spi almost same. Slightly longer wires.",
    ),
    "camp_spi_repair_setup_margin": RecipeLabel(
        "Setup margin on repair",
        "Asks for 50 ps more on timing repair.",
        "On spi changes nothing: already met timing.",
    ),
    "camp_spi_cts_closer_bufs": RecipeLabel(
        "Denser clock buffers",
        "Clock buffers every 80 µm.",
        "On spi changes nothing (clock tree already small).",
    ),
    "camp_spi_aspect_wide": RecipeLabel(
        "Floorplan wider than tall",
        "2:1 rectangle instead of a square.",
        "On spi slightly worse: more cells, area +3%, worse IR.",
    ),
    "camp_spi_core_tighter": RecipeLabel(
        "Tighter core",
        "Util 8→18: smaller die.",
        "On spi: area −2.6%, wires −18%, slack +3 ps. Worse IR. Not enough for a win.",
    ),
    "camp_spi_core_looser": RecipeLabel(
        "Looser core",
        "Util 8→5: larger die (minimum 5).",
        "On spi: larger die, area +2%, slack almost same.",
    ),
    "camp_spi_synth_hier": RecipeLabel(
        "Hierarchical synthesis",
        "Yosys without flatten before ABC.",
        "On spi identical to default (Verilog is already flat).",
    ),
    "camp_aes_place_denser": RecipeLabel(
        "Denser placement",
        "Same official netlist. Density addon +0.05. Die locked by config.",
        "On aes almost same as default (slack −8.6 vs −8.9 ps).",
    ),
    "camp_aes_repair_setup_margin": RecipeLabel(
        "Setup margin on repair",
        "Asks for 50 ps more on timing repair. Same netlist, die locked.",
        "On aes: first to close (+17 vs −9 ps). IR −12%. Area/power +3%. Win.",
    ),
    "camp_gcd_repair_setup_margin": RecipeLabel(
        "Setup margin on repair",
        "Asks for 50 ps more on timing repair.",
        "On gcd: slack slightly worse, IR much worse. Loses.",
    ),
    "camp_gcd_aspect_wide": RecipeLabel(
        "Floorplan wider than tall",
        "2:1 rectangle instead of a square.",
        "Lab (shape 2:1). IR −61% but moved the floorplan. Not a product win.",
    ),
    "camp_gcd_synth_hier": RecipeLabel(
        "Hierarchical synthesis",
        "Yosys without flatten before ABC.",
        "On gcd: loses. Slack −5 ps, power +150%, IR +155%. Do not use here.",
    ),
    "camp_gcd_cell_pad_plus": RecipeLabel(
        "Cell padding +1 site",
        "One site of extra space between cells. Same netlist, same die.",
        "On gcd: win. IR −19%, area −7%, power −8%. Slack −3.6 ps (within 5 ps).",
    ),
    "camp_gcd_repair_half_tns": RecipeLabel(
        "Half TNS repair",
        "TNS_END_PERCENT 100→50: repairs fewer violated paths.",
        "On gcd: loses. IR +19%. Slack and area almost same.",
    ),
    "camp_gcd_cts_closer_bufs": RecipeLabel(
        "Denser clock buffers",
        "Clock buffers every 80 µm.",
        "On gcd: identical to default. No-op.",
    ),
    "camp_ibex_synth_hier": RecipeLabel(
        "Hierarchical synthesis",
        "Yosys without flatten before ABC.",
        "On ibex: loses. Slack +8 ps, but IR +18%.",
    ),
    "camp_ibex_aspect_wide": RecipeLabel(
        "Floorplan wider than tall",
        "2:1 rectangle instead of a square.",
        "Lab (shape 2:1). IR −31% but moved the floorplan. Not a product win.",
    ),
    "camp_ibex_cell_pad_plus": RecipeLabel(
        "Cell padding +1 site",
        "One site of extra space between cells. Same netlist, same die.",
        "On ibex: win. IR −36%. Slack and area ~same.",
    ),
    "camp_ibex_repair_half_tns": RecipeLabel(
        "Half TNS repair",
        "TNS_END_PERCENT 100→50: repairs fewer violated paths.",
        "On ibex: identical to default (already met timing). No-op.",
    ),
    "camp_ibex_repair_setup_margin": RecipeLabel(
        "Setup margin on repair",
        "Asks for 50 ps more on timing repair.",
        "On ibex: win. Slack +41 ps. Area/power/IR ~same.",
    ),
    "camp_ibex_cts_closer_bufs": RecipeLabel(
        "Denser clock buffers",
        "Clock buffers every 80 µm.",
        "On ibex: slack +4 ps. Not enough for a win. Tie.",
    ),
    "camp_aes_synth_delay": RecipeLabel(
        "ABC delay synthesis",
        "Yosys + ABC speed script. Same RTL, different mapping.",
        "On aes: identical to default (official config is already ABC speed). No-op.",
    ),
    "camp_aes_synth_hier": RecipeLabel(
        "Hierarchical synthesis",
        "Yosys without flatten before ABC.",
        "On aes: loses. IR +16%. Slack ~same.",
    ),
    "camp_aes_place_sparser": RecipeLabel(
        "Sparser placement",
        "Density addon −0.05. Die locked by config.",
        "On aes: win. IR −13%. Slack −0.9 ps (within 5 ps).",
    ),
    "camp_aes_cell_pad_plus": RecipeLabel(
        "Cell padding +1 site",
        "One site of extra space between cells. Die locked.",
        "On aes: loses. Slack −21 ps. Better IR not enough.",
    ),
    "camp_aes_repair_half_tns": RecipeLabel(
        "Half TNS repair",
        "TNS_END_PERCENT 100→50. Die locked.",
        "On aes: loses. Slack −16 ps.",
    ),
    "camp_aes_cts_closer_bufs": RecipeLabel(
        "Denser clock buffers",
        "Clock buffers every 80 µm. Die locked.",
        "On aes: win. Slack +8 ps. Area/power/IR ~same.",
    ),
    "camp_dynamic_node_synth_delay": RecipeLabel(
        "ABC delay synthesis",
        "Yosys + ABC speed script. Same RTL, different mapping.",
        "On dynamic_node: identical to default. No-op.",
    ),
    "camp_dynamic_node_synth_hier": RecipeLabel(
        "Hierarchical synthesis",
        "Yosys without flatten before ABC.",
        "On dynamic_node: place +3.48 ns, policy STOP (pred finish −123 ps vs base). Not finished.",
    ),
    "camp_dynamic_node_core_tighter": RecipeLabel(
        "Tighter core",
        "CORE_UTILIZATION +10 vs default.",
        "Lab (smaller die). Slack +66 ps but moved the floorplan. Not a product win.",
    ),
    "camp_dynamic_node_core_looser": RecipeLabel(
        "Looser core",
        "CORE_UTILIZATION −10 vs default.",
        "Lab (larger die). Slack +101 ps, IR −14% but moved the floorplan. Not a product win.",
    ),
    "camp_dynamic_node_aspect_wide": RecipeLabel(
        "Floorplan wider than tall",
        "2:1 rectangle instead of a square.",
        "Lab (shape 2:1). Slack +56 ps but moved the floorplan. Not a product win.",
    ),
    "camp_dynamic_node_place_denser": RecipeLabel(
        "Denser placement",
        "Density addon +0.05. Same netlist.",
        "On dynamic_node: loses. IR +32%. Slack −30 ps.",
    ),
    "camp_dynamic_node_place_sparser": RecipeLabel(
        "Sparser placement",
        "Density addon −0.05. Same netlist.",
        "On dynamic_node: loses. IR +15%.",
    ),
    "camp_dynamic_node_cell_pad_plus": RecipeLabel(
        "Cell padding +1 site",
        "One site of extra space between cells.",
        "On dynamic_node: loses. Slack −49 ps, IR +18%.",
    ),
    "camp_dynamic_node_repair_half_tns": RecipeLabel(
        "Half TNS repair",
        "TNS_END_PERCENT 100→50.",
        "On dynamic_node: identical to default (already closed by 3.3 ns). No-op.",
    ),
    "camp_dynamic_node_repair_setup_margin": RecipeLabel(
        "Setup margin on repair",
        "Asks for 50 ps more on timing repair.",
        "On dynamic_node: identical to default. No-op.",
    ),
    "camp_dynamic_node_cts_closer_bufs": RecipeLabel(
        "Denser clock buffers",
        "Clock buffers every 80 µm.",
        "On dynamic_node: win. Slack +23 ps. Area/power/IR ~same.",
    ),
    "camp_spi_place_notiming": RecipeLabel(
        "Placement without timing-driven",
        "GPL_TIMING_DRIVEN=0. Same official netlist.",
        "On spi: loses. IR +48%. Area +2%. Slack −1 ps.",
    ),
    "camp_spi_hold_margin": RecipeLabel(
        "Hold margin on repair",
        "HOLD_SLACK_MARGIN=0.05 ns.",
        "On spi: identical to default. No-op.",
    ),
    "camp_spi_cts_sparser": RecipeLabel(
        "Sparser clock buffers",
        "CTS_BUF_DISTANCE=200.",
        "On spi: identical to default (tree already small). No-op.",
    ),
    "camp_spi_repair_skip": RecipeLabel(
        "No TNS repair",
        "TNS_END_PERCENT=0.",
        "On spi: identical to default (already met timing). No-op.",
    ),
    "camp_gcd_core_looser_aspect_wide": RecipeLabel(
        "Looser core + wider floorplan",
        "Util −10 and 2:1 rectangle. Same official netlist.",
        "On gcd: loses. Area +12%, power +12%. Better IR not enough.",
    ),
    "camp_gcd_core_looser_cell_pad_plus": RecipeLabel(
        "Looser core + cell padding",
        "Util −10 and one extra site between cells. Same netlist.",
        "Lab (larger die + pad). IR −48% but moved the floorplan. Not a product win.",
    ),
}


def _knob_label(lb: float | None, util: float | None, *, lb0: float = 0.20, util0: float | None = None) -> RecipeLabel | None:
    if lb is None and util is None:
        return None
    parts_title = []
    parts_does = []
    if lb is not None and abs(lb - lb0) > 1e-9:
        if lb > lb0:
            parts_title.append("denser placement")
            parts_does.append(f"PLACE_DENSITY_LB_ADDON {lb0:g}→{lb:g}")
        else:
            parts_title.append("sparser placement")
            parts_does.append(f"PLACE_DENSITY_LB_ADDON {lb0:g}→{lb:g}")
    if util is not None:
        if util0 is not None and abs(util - util0) > 1e-9:
            if util > util0:
                parts_title.append("tighter core")
                parts_does.append(f"CORE_UTILIZATION {util0:g}→{util:g}")
            else:
                parts_title.append("looser core")
                parts_does.append(f"CORE_UTILIZATION {util0:g}→{util:g}")
        else:
            parts_title.append(f"util {int(util) if float(util).is_integer() else util}")
            parts_does.append(f"CORE_UTILIZATION={util:g}")
    if not parts_title:
        return RecipeLabel(
            "Same knobs as default, different measurement point",
            "Knob offset = 0 vs config defaults.",
            "Control / grid center.",
        )
    title = ", ".join(p.capitalize() if i == 0 else p for i, p in enumerate(parts_title))
    return RecipeLabel(
        title[0].upper() + title[1:],
        "Same ORFS netlist. " + "; ".join(parts_does) + ".",
        "Physical knobs, not a new Verilog.",
    )


def label_for(exp: Any) -> RecipeLabel:
    """Best title/does/payoff for an Experiment or a variant name."""
    variant = getattr(exp, "variant", None) or (exp if isinstance(exp, str) else "")
    if variant in _EXPLICIT:
        return _EXPLICIT[variant]
    role = getattr(exp, "role", "") or ""
    clock = getattr(exp, "clock_ns", None)
    extra = getattr(exp, "extra", None) or {}
    clk = f" @ {clock:g} ns" if clock is not None else ""

    if role == "base":
        return RecipeLabel(
            f"ORFS default{clk}",
            "Official design recipe: synthesis and config physical knobs.",
            "Slot reference. Deltas read against this row.",
        )
    if role == "ainj":
        return RecipeLabel(
            f"Same netlist as default, recooked (oven){clk}",
            "Re-injection of official 1_2_yosys.v. Not a product challenger.",
            "Control H6: must be bit-identical to default.",
        )
    if role == "abc_speed":
        return RecipeLabel(
            f"ABC delay synthesis{clk}",
            "ABC speed script, same floorplan/place as default.",
            "In campaign: no §5 win. Not the synthesis method to use by default.",
        )
    if role in ("dse_small", "dse_fast", "dse_other") or "dse" in variant:
        return RecipeLabel(
            f"Netlist DSE / rewrite{clk}",
            "Changes the netlist. Physical knobs stay those of default.",
            "In campaign: inverted proxy (H1), no §5 win.",
        )
    rid = extra.get("recipe_id")
    rids = extra.get("recipe_ids") or ([rid] if rid else None)
    if rids:
        try:
            from dse.knob_catalog import by_id, titles_of

            recs = [by_id(r) for r in rids]
            return RecipeLabel(
                titles_of(list(rids)),
                " ".join(r["does"] for r in recs),
                " ".join(r["payoff"] for r in recs),
            )
        except Exception:
            pass
    lb = extra.get("place_density_lb_addon")
    util = extra.get("core_utilization")
    derived = _knob_label(
        float(lb) if lb is not None else None,
        float(util) if util is not None else None,
        util0=extra.get("util_default"),
    )
    if derived:
        return derived
    notes = (getattr(exp, "notes", None) or "").strip()
    if notes:
        return RecipeLabel(notes.split(".")[0][:80], notes, "")
    return RecipeLabel(variant, "Campaign variant.", "")


def synth_method_from_exploration() -> dict[str, Any]:
    """How to run Yosys/ABC on *new* challengers. Does not rewrite Verilog.

    Physical exploration: 4 §5 wins, all on the official (ABC area) netlist
    plus physical knobs. ABC delay / DSE rewrites: 0 wins.
    """
    return {
        "abc": "area",
        "ABC_AREA": 1,
        "ABC_SPEED": 0,
        "apply_to": "new challenger variants only",
        "never_apply_to": ["role=base", "FLOW_VARIANT=flowlab", "FLOW_VARIANT=learn"],
        "avoid_as_default": ["abc_speed", "dse_rtl_rewrite"],
        "why": (
            "Q1–Q4: 4 §5 wins on official netlist (ABC area) + physical knobs. "
            "ABC delay and DSE rewrites never won §5 (H1: proxy inverts)."
        ),
        "next_synth_axes": ["SYNTH_HIERARCHICAL", "TNS_END_PERCENT after map"],
    }
