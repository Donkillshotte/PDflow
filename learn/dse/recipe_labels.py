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
        "ORFS default — sintesi area, util 35, place +0.20",
        "Ricetta ufficiale gcd: ABC area, floorplan util 35%, GPL density addon 0.20, TNS repair 100%.",
        "Reference. WNS −37 ps, area 940 µm², IR worst 6.67 mV / mean ~2.6 mV.",
    ),
    "camp_gcd_q1_d25u35": RecipeLabel(
        "Place più denso, stesso die — meno buffer di repair",
        "Stessa netlist e stesso util 35. Solo PLACE_DENSITY_LB_ADDON 0.20→0.25.",
        "§5 win: area −10.5%, power −13%, leak −14%, IR −8%, WL −8%.",
    ),
    "camp_ibex_base": RecipeLabel(
        "ORFS default — sintesi area, util 50, place +0.20",
        "Ricetta ufficiale ibex: ABC area, util 50%, density addon 0.20.",
        "Reference. WNS +22 ps, power 108 mW, IR worst 124 mV.",
    ),
    "camp_ibex_q1_d20u60": RecipeLabel(
        "Core più stretto — die più piccolo, fili più corti",
        "Stessa netlist e stesso density addon 0.20. CORE_UTILIZATION 50→60.",
        "§5 win: WNS +42 vs +22 ps; IR −30%; WL −4%; power ~iso.",
    ),
    "camp_ibex_q1_d25u50": RecipeLabel(
        "Place più denso, stesso die",
        "Stessa netlist e util 50. PLACE_DENSITY_LB_ADDON 0.20→0.25.",
        "§5 win slack (+40 vs +22 ps). Area/power ~iso.",
    ),
    "camp_ibex_q1_d15u50": RecipeLabel(
        "Place più sparso, stesso die",
        "Stessa netlist e util 50. PLACE_DENSITY_LB_ADDON 0.20→0.15.",
        "§5 win slack (+36 vs +22 ps). Area/power ~iso.",
    ),
    "camp_ibex_q1_d20u40": RecipeLabel(
        "Core più largo — die più grande, fili più lunghi",
        "Stessa netlist. CORE_UTILIZATION 50→40.",
        "Lose: WNS −6 ps, WL +5%. Controesempio del core stretto.",
    ),
    "camp_gcd_q4_d25u35_c055": RecipeLabel(
        "Place più denso al clock dove il default chiude (0.55 ns)",
        "Stessi knob del win gcd, SDC 0.55 ns (regime area).",
        "I4 falsa: chiude come il default, area 698 vs 697. Il win non transferisce di clock.",
    ),
    "camp_gcd_dse_small": RecipeLabel(
        "Netlist DSE rewrite (sub_twos_complement) — place/route uguale al default",
        "Cambia solo il Verilog mappato. Floorplan/place/CTS = default.",
        "Lose: WNS −338 vs −37 ps. Il rewrite di sintesi non è un win di prodotto.",
    ),
    "camp_gcd_dse_fast": RecipeLabel(
        "Sintesi ABC delay sulla stessa ricetta fisica",
        "ABC speed, util/density del default.",
        "Lose: WNS −187 ps, power +41%. ABC delay non batte ABC area + knob fisici.",
    ),
    "camp_gcd_dse_fixedb": RecipeLabel(
        "Netlist DSE rewrite sul die del default (controllo geometria)",
        "Stesso Verilog DSE di B, DIE_AREA bloccata su A.",
        "Lose: ancora ~−350 ps. Non è un problema di die.",
    ),
    "camp_spi_place_denser": RecipeLabel(
        "Place più denso",
        "Stessa netlist ufficiale. PLACE_DENSITY_LB_ADDON 0.20→0.25. Util resta il default di config (8).",
        "Transfer miss su spi: WNS −1.5 ps (tie), area +0.2%, stessi 22 buffer. Il lever gcd non transferisce su un die già chiuso e sparso.",
    ),
    "camp_spi_repair_half_tns": RecipeLabel(
        "Repair TNS a metà",
        "Stessa netlist ufficiale. TNS_END_PERCENT 100→50. Util resta 8.",
        "Su spi non cambia nulla: era già in orario.",
    ),
    "camp_spi_place_sparser": RecipeLabel(
        "Place più sparso",
        "Celle un po’ più larghe (density addon 0.20→0.15).",
        "Su spi quasi uguale al default. Fili un po’ più lunghi.",
    ),
    "camp_spi_cell_pad_plus": RecipeLabel(
        "Padding celle +1 site",
        "Un site di spazio extra tra le celle.",
        "Su spi quasi uguale. Fili un po’ più lunghi.",
    ),
    "camp_spi_repair_setup_margin": RecipeLabel(
        "Margine di setup sul repair",
        "Chiede 50 ps in più al repair di timing.",
        "Su spi non cambia nulla: era già in orario.",
    ),
    "camp_spi_cts_closer_bufs": RecipeLabel(
        "Buffer di clock più fitti",
        "Buffer di clock ogni 80 µm.",
        "Su spi non cambia nulla (albero di clock già piccolo).",
    ),
    "camp_spi_aspect_wide": RecipeLabel(
        "Floorplan più largo che alto",
        "Rettangolo 2:1 invece di un quadrato.",
        "Su spi un po’ peggio: più celle, area +3%, IR peggiore.",
    ),
    "camp_spi_core_tighter": RecipeLabel(
        "Core più stretto",
        "Util 8→18: die più piccolo.",
        "Su spi: area −2.6%, fili −18%, slack +3 ps. IR peggiore. Non basta per un win.",
    ),
    "camp_spi_core_looser": RecipeLabel(
        "Core più largo",
        "Util 8→5: die più grande (minimo 5).",
        "Su spi: die più grande, area +2%, slack quasi uguale.",
    ),
    "camp_spi_synth_hier": RecipeLabel(
        "Sintesi gerarchica",
        "Yosys senza flatten prima di ABC.",
        "Su spi identico al default (il Verilog è già piatto).",
    ),
    "camp_aes_place_denser": RecipeLabel(
        "Place più denso",
        "Stessa netlist ufficiale. Density addon +0.05. Die bloccato dal config.",
        "Su aes quasi uguale al default (slack −8.6 vs −8.9 ps).",
    ),
    "camp_aes_repair_setup_margin": RecipeLabel(
        "Margine di setup sul repair",
        "Chiede 50 ps in più al repair di timing. Stessa netlist, die bloccato.",
        "Su aes: primo a chiudere (+17 vs −9 ps). IR −12%. Area/potenza +3%. Win.",
    ),
    "camp_gcd_repair_setup_margin": RecipeLabel(
        "Margine di setup sul repair",
        "Chiede 50 ps in più al repair di timing.",
        "Su gcd: slack un filo peggio, IR molto peggio. Perde.",
    ),
    "camp_gcd_aspect_wide": RecipeLabel(
        "Floorplan più largo che alto",
        "Rettangolo 2:1 invece di un quadrato.",
        "Su gcd: slack uguale, IR −61%. Win su IR.",
    ),
}


def _knob_label(lb: float | None, util: float | None, *, lb0: float = 0.20, util0: float | None = None) -> RecipeLabel | None:
    if lb is None and util is None:
        return None
    parts_title = []
    parts_does = []
    if lb is not None and abs(lb - lb0) > 1e-9:
        if lb > lb0:
            parts_title.append("place più denso")
            parts_does.append(f"PLACE_DENSITY_LB_ADDON {lb0:g}→{lb:g}")
        else:
            parts_title.append("place più sparso")
            parts_does.append(f"PLACE_DENSITY_LB_ADDON {lb0:g}→{lb:g}")
    if util is not None:
        if util0 is not None and abs(util - util0) > 1e-9:
            if util > util0:
                parts_title.append("core più stretto")
                parts_does.append(f"CORE_UTILIZATION {util0:g}→{util:g}")
            else:
                parts_title.append("core più largo")
                parts_does.append(f"CORE_UTILIZATION {util0:g}→{util:g}")
        else:
            parts_title.append(f"util {int(util) if float(util).is_integer() else util}")
            parts_does.append(f"CORE_UTILIZATION={util:g}")
    if not parts_title:
        return RecipeLabel(
            "Stessi knob del default, altro punto di misura",
            "Offset knob = 0 rispetto ai default di config.",
            "Controllo / centro griglia.",
        )
    title = ", ".join(p.capitalize() if i == 0 else p for i, p in enumerate(parts_title))
    return RecipeLabel(
        title[0].upper() + title[1:],
        "Stessa netlist ORFS. " + "; ".join(parts_does) + ".",
        "Knob fisici, non un nuovo Verilog.",
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
            "Ricetta ufficiale del design: sintesi e knob fisici di config.",
            "Reference dello slot. I delta si leggono contro questa riga.",
        )
    if role == "ainj":
        return RecipeLabel(
            f"Stessa netlist del default, ricotta (forno){clk}",
            "Re-iniezione del 1_2_yosys.v ufficiale. Non è un challenger di prodotto.",
            "Controllo H6: deve essere bit-identical al default.",
        )
    if role == "abc_speed":
        return RecipeLabel(
            f"Sintesi ABC delay{clk}",
            "Script ABC speed, stesso floorplan/place del default.",
            "In campagna: nessun win §5. Non è il metodo di sintesi da usare di default.",
        )
    if role in ("dse_small", "dse_fast", "dse_other") or "dse" in variant:
        return RecipeLabel(
            f"Netlist DSE / rewrite{clk}",
            "Cambia la netlist. I knob fisici restano quelli del default.",
            "In campagna: proxy invertito (H1), nessun win §5.",
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
    return RecipeLabel(variant, "Variant di campagna.", "")


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
            "Q1–Q4: 4 win §5 sulla netlist ufficiale (ABC area) + knob fisici. "
            "ABC delay e i rewrite DSE non hanno mai vinto §5 (H1: il proxy inverte)."
        ),
        "next_synth_axes": ["SYNTH_HIERARCHICAL", "TNS_END_PERCENT after map"],
    }
