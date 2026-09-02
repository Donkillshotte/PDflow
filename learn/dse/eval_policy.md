# Next-iteration eval vs frozen I1–I5

Plan sha: `9e4c452080e0239bff3b906072b886e808cd63fb72cfac7bdaa2c7fdaf5d7880`
Experiments: 129 (112 done)

I1–I5 bars stay frozen (historical). Product win is `dse.win_rule` (slack + area/power/leak/IR on a pinned floorplan).
Readable reference+challenger sheets: `learn/dse/qor_compare.md`.

## I1_physical_knobs

**Verdict:** I1 supported (wins ['camp_gcd_q1_d25u35', 'camp_ibex_q1_d15u50', 'camp_ibex_q1_d25u50', 'camp_ibex_q1_d20u60']) gcd_range=8.4ps ibex_range=26.2ps

```json
{
  "wins": [
    "camp_gcd_q1_d25u35",
    "camp_ibex_q1_d15u50",
    "camp_ibex_q1_d25u50",
    "camp_ibex_q1_d20u60"
  ],
  "ranges": {
    "gcd": {
      "n_q1": 8,
      "range_ps": 8.424999999999995,
      "n_wns": 9
    },
    "ibex": {
      "n_q1": 4,
      "range_ps": 26.2391,
      "n_wns": 5
    }
  },
  "gcd_bar_ps": 25.0,
  "ibex_bar_ps": 50.0,
  "supported": true,
  "verdict": "I1 supported (wins ['camp_gcd_q1_d25u35', 'camp_ibex_q1_d15u50', 'camp_ibex_q1_d25u50', 'camp_ibex_q1_d20u60']) gcd_range=8.4ps ibex_range=26.2ps"
}
```

## I2_per_design_residual

**Verdict:** I2 supported (13/13 holdout inside per-design ±2σ)

```json
{
  "calibration": {
    "aes": {
      "n": 15,
      "mean_ns": 0.031173409066666668,
      "std_ns": 0.029643684456396615
    },
    "dynamic_node": {
      "n": 11,
      "mean_ns": -0.24053909090909095,
      "std_ns": 0.011800051232554417
    },
    "gcd": {
      "n": 38,
      "mean_ns": -0.051514804473684214,
      "std_ns": 0.015306218331966255
    },
    "ibex": {
      "n": 24,
      "mean_ns": -0.19765361250000002,
      "std_ns": 0.07972644079853315
    },
    "spi": {
      "n": 16,
      "mean_ns": 0.026529312499999964,
      "std_ns": 0.010790672081130994
    }
  },
  "n_holdout": 13,
  "n_inside": 13,
  "coverage": 1.0,
  "bar": 0.8,
  "holdout": [
    {
      "variant": "camp_gcd_q1_d15u25",
      "design": "gcd",
      "pred_ns": -0.04087719137931035,
      "actual_ns": -0.0444042,
      "err_ns": -0.0035270086206896506,
      "band_ns": 0.034846697766391294,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d15u35",
      "design": "gcd",
      "pred_ns": -0.038896691379310344,
      "actual_ns": -0.0436955,
      "err_ns": -0.004798808620689654,
      "band_ns": 0.034846697766391294,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d15u45",
      "design": "gcd",
      "pred_ns": -0.035874891379310346,
      "actual_ns": -0.0359792,
      "err_ns": -0.0001043086206896568,
      "band_ns": 0.034846697766391294,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d20u25",
      "design": "gcd",
      "pred_ns": -0.04108587137931034,
      "actual_ns": -0.0362789,
      "err_ns": 0.00480697137931034,
      "band_ns": 0.034846697766391294,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d20u45",
      "design": "gcd",
      "pred_ns": -0.036376991379310344,
      "actual_ns": -0.0376739,
      "err_ns": -0.0012969086206896588,
      "band_ns": 0.034846697766391294,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d25u25",
      "design": "gcd",
      "pred_ns": -0.03906919137931034,
      "actual_ns": -0.0417844,
      "err_ns": -0.002715208620689656,
      "band_ns": 0.034846697766391294,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d25u35",
      "design": "gcd",
      "pred_ns": -0.03738649137931034,
      "actual_ns": -0.0384003,
      "err_ns": -0.0010138086206896574,
      "band_ns": 0.034846697766391294,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d25u45",
      "design": "gcd",
      "pred_ns": -0.036393691379310346,
      "actual_ns": -0.0381096,
      "err_ns": -0.0017159086206896546,
      "band_ns": 0.034846697766391294,
      "inside": true
    },
    {
      "variant": "camp_ibex_q1_d15u50",
      "design": "ibex",
      "pred_ns": 0.037765964999999985,
      "actual_ns": 0.0362255,
      "err_ns": -0.001540464999999984,
      "band_ns": 0.17329613761447135,
      "inside": true
    },
    {
      "variant": "camp_ibex_q1_d25u50",
      "design": "ibex",
      "pred_ns": 0.06671296500000001,
      "actual_ns": 0.039892,
      "err_ns": -0.026820965000000016,
      "band_ns": 0.17329613761447135,
      "inside": true
    },
    {
      "variant": "camp_ibex_q1_d20u40",
      "design": "ibex",
      "pred_ns": 0.05818096499999997,
      "actual_ns": 0.0161107,
      "err_ns": -0.042070264999999975,
      "band_ns": 0.17329613761447135,
      "inside": true
    },
    {
      "variant": "camp_ibex_q1_d20u60",
      "design": "ibex",
      "pred_ns": 0.08180396499999998,
      "actual_ns": 0.0423498,
      "err_ns": -0.03945416499999998,
      "band_ns": 0.17329613761447135,
      "inside": true
    },
    {
      "variant": "camp_gcd_q4_d25u35_c055",
      "design": "gcd",
      "pred_ns": 0.023415208620689652,
      "actual_ns": 0.0130203,
      "err_ns": -0.010394908620689652,
      "band_ns": 0.034846697766391294,
      "inside": true
    }
  ],
  "supported": true,
  "verdict": "I2 supported (13/13 holdout inside per-design \u00b12\u03c3)"
}
```

## I3_stop_precision

**Verdict:** I3 supported (STOP precision 100% on 11 verified rejects)

```json
{
  "n_verified": 11,
  "n_lose": 11,
  "precision": 1.0,
  "bar": 0.8,
  "rows": [
    {
      "variant": "camp_gcd_dse_small",
      "loses": true,
      "via": "replay",
      "policy": "STOP"
    },
    {
      "variant": "camp_gcd_dse_fast",
      "loses": true,
      "via": "replay",
      "policy": "STOP"
    },
    {
      "variant": "camp_gcd_dse_fixedb",
      "loses": true,
      "via": "replay",
      "policy": "STOP"
    },
    {
      "variant": "camp_gcd_clk040_b",
      "loses": true,
      "via": "replay",
      "policy": "STOP"
    },
    {
      "variant": "camp_gcd_clk040_c",
      "loses": true,
      "via": "replay",
      "policy": "STOP"
    },
    {
      "variant": "camp_gcd_clk055_b",
      "loses": true,
      "via": "replay",
      "policy": "STOP"
    },
    {
      "variant": "camp_gcd_clk055_c",
      "loses": true,
      "via": "replay",
      "policy": "STOP"
    },
    {
      "variant": "camp_gcd_clk070_b",
      "loses": true,
      "via": "replay",
      "policy": "STOP"
    },
    {
      "variant": "camp_gcd_clk070_c",
      "loses": true,
      "via": "replay",
      "policy": "STOP"
    },
    {
      "variant": "camp_gcd_clk090_b",
      "loses": true,
      "via": "replay",
      "policy": "STOP"
    },
    {
      "variant": "camp_gcd_clk090_c",
      "loses": true,
      "via": "replay",
      "policy": "STOP"
    }
  ],
  "supported": true,
  "verdict": "I3 supported (STOP precision 100% on 11 verified rejects)"
}
```

## I4_area_regime

**Verdict:** I4 not supported (no closed candidate ≥10% smaller than a closed base)

```json
{
  "n_candidates": 13,
  "hits": [],
  "area_frac": 0.1,
  "supported": false,
  "verdict": "I4 not supported (no closed candidate \u226510% smaller than a closed base)"
}
```

## I5_proxy_correlation

**Verdict:** I5 supported (place Spearman 0.890 ≥ 0.6; F1 Spearman 0.866)

```json
{
  "n_place_pairs": 104,
  "n_f1_pairs": 3,
  "place_spearman": 0.8898259423079771,
  "f1_spearman": 0.8660254037844387,
  "bar": 0.6,
  "min_n": 8,
  "supported": true,
  "verdict": "I5 supported (place Spearman 0.890 \u2265 0.6; F1 Spearman 0.866)"
}
```

## gate_diagnostics

**Verdict:** gate FP=54 FN=6 precision=0.239 (23 product-wins among 92 challengers)

```json
{
  "n_challengers": 92,
  "n_promoted": 71,
  "n_real_wins": 23,
  "tp": 17,
  "fp": 54,
  "fn": 6,
  "tn": 15,
  "precision": 0.23943661971830985,
  "recall": 0.7391304347826086,
  "verdict": "gate FP=54 FN=6 precision=0.239 (23 product-wins among 92 challengers)"
}
```

## QoR_vs_base

**Verdict:** QoR vs base: 12 reference slots, 92 challengers, 92 with IR, 92 with GRT WL, 21 product wins (same die), 29 wrong_die (moved floorplan)

Table names say **what the recipe does** and (in § Recipes) what advantage or downside we saw. The `camp_*` id is only the ORFS path.

IR worst = max VDD drop. **IR mean** = average drop on the die (VDD_nom − V_avg; the ORFS `drop__average` key on VDD is actually a voltage). **Density** = stdcell utilization on the core. **Congestion** = GRT WL / core area (JSON has no overflow fraction; `congestion_*_s` are runtimes).

Product win: fixed floorplan (same area, size, shape). Timing ±5 ps and (area or power or leakage or IR −10%), without worsening any by 10%. Or timing +5 ps without worsening the four. A moved die is `wrong_die` (lab). See `product.md`.

### Recipes (what they do, what we learned)

| Recipe | What it does | Advantage / outcome |
|---|---|---|
| ORFS default @ 0.82 ns (`camp_aes_base`) | Official design recipe: synthesis and config physical knobs. | Slot reference. Deltas read against this row. |
| ORFS default @ 6 ns (`camp_dynamic_node_base`) | Official design recipe: synthesis and config physical knobs. | Slot reference. Deltas read against this row. |
| ORFS default @ 0.4 ns (`camp_gcd_clk040_a`) | Official design recipe: synthesis and config physical knobs. | Slot reference. Deltas read against this row. |
| ORFS default — area synthesis, util 35, place +0.20 (`camp_gcd_base`) | Official gcd recipe: ABC area, floorplan util 35%, GPL density addon 0.20, TNS repair 100%. | Reference. WNS −37 ps, area 940 µm², IR worst 6.67 mV / mean ~2.6 mV. |
| ORFS default @ 0.55 ns (`camp_gcd_clk055_a`) | Official design recipe: synthesis and config physical knobs. | Slot reference. Deltas read against this row. |
| ORFS default @ 0.7 ns (`camp_gcd_clk070_a`) | Official design recipe: synthesis and config physical knobs. | Slot reference. Deltas read against this row. |
| ORFS default @ 0.9 ns (`camp_gcd_clk090_a`) | Official design recipe: synthesis and config physical knobs. | Slot reference. Deltas read against this row. |
| ORFS default @ 1.98 ns (`camp_ibex_clk198_a`) | Official design recipe: synthesis and config physical knobs. | Slot reference. Deltas read against this row. |
| ORFS default — area synthesis, util 50, place +0.20 (`camp_ibex_base`) | Official ibex recipe: ABC area, util 50%, density addon 0.20. | Reference. WNS +22 ps, power 108 mW, IR worst 124 mV. |
| ORFS default @ 2.75 ns (`camp_ibex_clk275_a`) | Official design recipe: synthesis and config physical knobs. | Slot reference. Deltas read against this row. |
| ORFS default @ 3.52 ns (`camp_ibex_clk352_a`) | Official design recipe: synthesis and config physical knobs. | Slot reference. Deltas read against this row. |
| ORFS default @ 1 ns (`camp_spi_base`) | Official design recipe: synthesis and config physical knobs. | Slot reference. Deltas read against this row. |
| Netlist DSE rewrite (sub_twos_complement) — place/route same as default (`camp_gcd_dse_small`) | Only changes mapped Verilog. Floorplan/place/CTS = default. | Lose: WNS −338 vs −37 ps. Synthesis rewrite is not a product win. |
| ABC delay synthesis on the same physical recipe (`camp_gcd_dse_fast`) | ABC speed, default util/density. | Lose: WNS −187 ps, power +41%. ABC delay does not beat ABC area + physical knobs. |
| Netlist DSE rewrite on default die (geometry control) (`camp_gcd_dse_fixedb`) | Same DSE Verilog as B, DIE_AREA locked to A. | Lose: still ~−350 ps. Not a die-size problem. |
| Netlist DSE / rewrite @ 0.4 ns (`camp_gcd_clk040_b`) | Changes the netlist. Physical knobs stay those of default. | In campaign: inverted proxy (H1), no §5 win. |
| Netlist DSE / rewrite @ 0.4 ns (`camp_gcd_clk040_c`) | Changes the netlist. Physical knobs stay those of default. | In campaign: inverted proxy (H1), no §5 win. |
| Netlist DSE / rewrite @ 0.55 ns (`camp_gcd_clk055_b`) | Changes the netlist. Physical knobs stay those of default. | In campaign: inverted proxy (H1), no §5 win. |
| Netlist DSE / rewrite @ 0.55 ns (`camp_gcd_clk055_c`) | Changes the netlist. Physical knobs stay those of default. | In campaign: inverted proxy (H1), no §5 win. |
| Netlist DSE / rewrite @ 0.7 ns (`camp_gcd_clk070_b`) | Changes the netlist. Physical knobs stay those of default. | In campaign: inverted proxy (H1), no §5 win. |
| Netlist DSE / rewrite @ 0.7 ns (`camp_gcd_clk070_c`) | Changes the netlist. Physical knobs stay those of default. | In campaign: inverted proxy (H1), no §5 win. |
| Netlist DSE / rewrite @ 0.9 ns (`camp_gcd_clk090_b`) | Changes the netlist. Physical knobs stay those of default. | In campaign: inverted proxy (H1), no §5 win. |
| Netlist DSE / rewrite @ 0.9 ns (`camp_gcd_clk090_c`) | Changes the netlist. Physical knobs stay those of default. | In campaign: inverted proxy (H1), no §5 win. |
| ABC delay synthesis @ 1 ns (`camp_spi_abcspeed`) | ABC speed script, same floorplan/place as default. | In campaign: no §5 win. Not the synthesis method to use by default. |
| ABC delay synthesis @ 2.2 ns (`camp_ibex_abcspeed`) | ABC speed script, same floorplan/place as default. | In campaign: no §5 win. Not the synthesis method to use by default. |
| ABC delay synthesis @ 1.98 ns (`camp_ibex_clk198_s`) | ABC speed script, same floorplan/place as default. | In campaign: no §5 win. Not the synthesis method to use by default. |
| ABC delay synthesis @ 2.75 ns (`camp_ibex_clk275_s`) | ABC speed script, same floorplan/place as default. | In campaign: no §5 win. Not the synthesis method to use by default. |
| ABC delay synthesis @ 3.52 ns (`camp_ibex_clk352_s`) | ABC speed script, same floorplan/place as default. | In campaign: no §5 win. Not the synthesis method to use by default. |
| Sparser placement, util 25 (`camp_gcd_q1_d15u25`) | Same ORFS netlist. PLACE_DENSITY_LB_ADDON 0.2→0.15; CORE_UTILIZATION=25. | Physical knobs, not a new Verilog. |
| Sparser placement, util 35 (`camp_gcd_q1_d15u35`) | Same ORFS netlist. PLACE_DENSITY_LB_ADDON 0.2→0.15; CORE_UTILIZATION=35. | Physical knobs, not a new Verilog. |
| Sparser placement, util 45 (`camp_gcd_q1_d15u45`) | Same ORFS netlist. PLACE_DENSITY_LB_ADDON 0.2→0.15; CORE_UTILIZATION=45. | Physical knobs, not a new Verilog. |
| Util 25 (`camp_gcd_q1_d20u25`) | Same ORFS netlist. CORE_UTILIZATION=25. | Physical knobs, not a new Verilog. |
| Util 45 (`camp_gcd_q1_d20u45`) | Same ORFS netlist. CORE_UTILIZATION=45. | Physical knobs, not a new Verilog. |
| Denser placement, util 25 (`camp_gcd_q1_d25u25`) | Same ORFS netlist. PLACE_DENSITY_LB_ADDON 0.2→0.25; CORE_UTILIZATION=25. | Physical knobs, not a new Verilog. |
| Denser placement, same die — fewer repair buffers (`camp_gcd_q1_d25u35`) | Same netlist and same util 35. Only PLACE_DENSITY_LB_ADDON 0.20→0.25. | §5 win: area −10.5%, power −13%, leak −14%, IR −8%, WL −8%. |
| Denser placement, util 45 (`camp_gcd_q1_d25u45`) | Same ORFS netlist. PLACE_DENSITY_LB_ADDON 0.2→0.25; CORE_UTILIZATION=45. | Physical knobs, not a new Verilog. |
| Sparser placement, same die (`camp_ibex_q1_d15u50`) | Same netlist and util 50. PLACE_DENSITY_LB_ADDON 0.20→0.15. | §5 win slack (+36 vs +22 ps). Area/power ~same. |
| Denser placement, same die (`camp_ibex_q1_d25u50`) | Same netlist and util 50. PLACE_DENSITY_LB_ADDON 0.20→0.25. | §5 win slack (+40 vs +22 ps). Area/power ~same. |
| Looser core — larger die, longer wires (`camp_ibex_q1_d20u40`) | Same netlist. CORE_UTILIZATION 50→40. | Lose: WNS −6 ps, WL +5%. Counterexample to tighter core. |
| Tighter core — smaller die, shorter wires (`camp_ibex_q1_d20u60`) | Same netlist and same density addon 0.20. CORE_UTILIZATION 50→60. | Lab (smaller die, util 50→60). Better slack/IR, but moved the floorplan. Not a product win. |
| Denser placement at the clock where the default closes (0.55 ns) (`camp_gcd_q4_d25u35_c055`) | Same knobs as gcd win, SDC 0.55 ns (area regime). | False I4: closes like default, area 698 vs 697. Win does not transfer across clock. |
| Denser placement (`camp_spi_place_denser`) | Same official netlist. PLACE_DENSITY_LB_ADDON 0.20→0.25. Util stays config default (8). | Transfer miss on spi: WNS −1.5 ps (tie), area +0.2%, same 22 buffers. The gcd lever does not transfer on an already closed, sparse die. |
| Half TNS repair (`camp_spi_repair_half_tns`) | Same official netlist. TNS_END_PERCENT 100→50. Util stays 8. | On spi changes nothing: already met timing. |
| Sparser placement (`camp_spi_place_sparser`) | Slightly wider cells (density addon 0.20→0.15). | On spi almost same as default. Slightly longer wires. |
| Cell padding +1 site (`camp_spi_cell_pad_plus`) | One site of extra space between cells. | On spi almost same. Slightly longer wires. |
| Setup margin on repair (`camp_spi_repair_setup_margin`) | Asks for 50 ps more on timing repair. | On spi changes nothing: already met timing. |
| Denser clock buffers (`camp_spi_cts_closer_bufs`) | Clock buffers every 80 µm. | On spi changes nothing (clock tree already small). |
| Floorplan wider than tall (`camp_spi_aspect_wide`) | 2:1 rectangle instead of a square. | On spi slightly worse: more cells, area +3%, worse IR. |
| Tighter core (`camp_spi_core_tighter`) | Util 8→18: smaller die. | On spi: area −2.6%, wires −18%, slack +3 ps. Worse IR. Not enough for a win. |
| Looser core (`camp_spi_core_looser`) | Util 8→5: larger die (minimum 5). | On spi: larger die, area +2%, slack almost same. |
| Hierarchical synthesis (`camp_spi_synth_hier`) | Yosys without flatten before ABC. | On spi identical to default (Verilog is already flat). |
| Setup margin on repair (`camp_gcd_repair_setup_margin`) | Asks for 50 ps more on timing repair. | On gcd: slack slightly worse, IR much worse. Loses. |
| Floorplan wider than tall (`camp_gcd_aspect_wide`) | 2:1 rectangle instead of a square. | Lab (shape 2:1). IR −61% but moved the floorplan. Not a product win. |
| Denser placement (`camp_aes_place_denser`) | Same official netlist. Density addon +0.05. Die locked by config. | On aes almost same as default (slack −8.6 vs −8.9 ps). |
| Setup margin on repair (`camp_aes_repair_setup_margin`) | Asks for 50 ps more on timing repair. Same netlist, die locked. | On aes: first to close (+17 vs −9 ps). IR −12%. Area/power +3%. Win. |
| Hierarchical synthesis (`camp_gcd_synth_hier`) | Yosys without flatten before ABC. | On gcd: loses. Slack −5 ps, power +150%, IR +155%. Do not use here. |
| Cell padding +1 site (`camp_gcd_cell_pad_plus`) | One site of extra space between cells. Same netlist, same die. | On gcd: win. IR −19%, area −7%, power −8%. Slack −3.6 ps (within 5 ps). |
| Half TNS repair (`camp_gcd_repair_half_tns`) | TNS_END_PERCENT 100→50: repairs fewer violated paths. | On gcd: loses. IR +19%. Slack and area almost same. |
| Denser clock buffers (`camp_gcd_cts_closer_bufs`) | Clock buffers every 80 µm. | On gcd: identical to default. No-op. |
| Hierarchical synthesis (`camp_ibex_synth_hier`) | Yosys without flatten before ABC. | On ibex: loses. Slack +8 ps, but IR +18%. |
| Floorplan wider than tall (`camp_ibex_aspect_wide`) | 2:1 rectangle instead of a square. | Lab (shape 2:1). IR −31% but moved the floorplan. Not a product win. |
| Cell padding +1 site (`camp_ibex_cell_pad_plus`) | One site of extra space between cells. Same netlist, same die. | On ibex: win. IR −36%. Slack and area ~same. |
| Half TNS repair (`camp_ibex_repair_half_tns`) | TNS_END_PERCENT 100→50: repairs fewer violated paths. | On ibex: identical to default (already met timing). No-op. |
| Setup margin on repair (`camp_ibex_repair_setup_margin`) | Asks for 50 ps more on timing repair. | On ibex: win. Slack +41 ps. Area/power/IR ~same. |
| Denser clock buffers (`camp_ibex_cts_closer_bufs`) | Clock buffers every 80 µm. | On ibex: slack +4 ps. Not enough for a win. Tie. |
| ABC delay synthesis (`camp_aes_synth_delay`) | Yosys + ABC speed script. Same RTL, different mapping. | On aes: identical to default (official config is already ABC speed). No-op. |
| Hierarchical synthesis (`camp_aes_synth_hier`) | Yosys without flatten before ABC. | On aes: loses. IR +16%. Slack ~same. |
| Sparser placement (`camp_aes_place_sparser`) | Density addon −0.05. Die locked by config. | On aes: win. IR −13%. Slack −0.9 ps (within 5 ps). |
| Cell padding +1 site (`camp_aes_cell_pad_plus`) | One site of extra space between cells. Die locked. | On aes: loses. Slack −21 ps. Better IR not enough. |
| Half TNS repair (`camp_aes_repair_half_tns`) | TNS_END_PERCENT 100→50. Die locked. | On aes: loses. Slack −16 ps. |
| Denser clock buffers (`camp_aes_cts_closer_bufs`) | Clock buffers every 80 µm. Die locked. | On aes: win. Slack +8 ps. Area/power/IR ~same. |
| ABC delay synthesis (`camp_dynamic_node_synth_delay`) | Yosys + ABC speed script. Same RTL, different mapping. | On dynamic_node: identical to default. No-op. |
| Tighter core (`camp_dynamic_node_core_tighter`) | CORE_UTILIZATION +10 vs default. | Lab (smaller die). Slack +66 ps but moved the floorplan. Not a product win. |
| Looser core (`camp_dynamic_node_core_looser`) | CORE_UTILIZATION −10 vs default. | Lab (larger die). Slack +101 ps, IR −14% but moved the floorplan. Not a product win. |
| Floorplan wider than tall (`camp_dynamic_node_aspect_wide`) | 2:1 rectangle instead of a square. | Lab (shape 2:1). Slack +56 ps but moved the floorplan. Not a product win. |
| Denser placement (`camp_dynamic_node_place_denser`) | Density addon +0.05. Same netlist. | On dynamic_node: loses. IR +32%. Slack −30 ps. |
| Sparser placement (`camp_dynamic_node_place_sparser`) | Density addon −0.05. Same netlist. | On dynamic_node: loses. IR +15%. |
| Cell padding +1 site (`camp_dynamic_node_cell_pad_plus`) | One site of extra space between cells. | On dynamic_node: loses. Slack −49 ps, IR +18%. |
| Half TNS repair (`camp_dynamic_node_repair_half_tns`) | TNS_END_PERCENT 100→50. | On dynamic_node: identical to default (already closed by 3.3 ns). No-op. |
| Setup margin on repair (`camp_dynamic_node_repair_setup_margin`) | Asks for 50 ps more on timing repair. | On dynamic_node: identical to default. No-op. |
| Denser clock buffers (`camp_dynamic_node_cts_closer_bufs`) | Clock buffers every 80 µm. | On dynamic_node: win. Slack +23 ps. Area/power/IR ~same. |
| Placement without timing-driven (`camp_spi_place_notiming`) | GPL_TIMING_DRIVEN=0. Same official netlist. | On spi: loses. IR +48%. Area +2%. Slack −1 ps. |
| Hold margin on repair (`camp_spi_hold_margin`) | HOLD_SLACK_MARGIN=0.05 ns. | On spi: identical to default. No-op. |
| Sparser clock buffers (`camp_spi_cts_sparser`) | CTS_BUF_DISTANCE=200. | On spi: identical to default (tree already small). No-op. |
| No TNS repair (`camp_spi_repair_skip`) | TNS_END_PERCENT=0. | On spi: identical to default (already met timing). No-op. |
| Looser core + wider floorplan (`camp_gcd_core_looser_aspect_wide`) | Util −10 and 2:1 rectangle. Same official netlist. | On gcd: loses. Area +12%, power +12%. Better IR not enough. |
| Looser core + cell padding (`camp_gcd_core_looser_cell_pad_plus`) | Util −10 and one extra site between cells. Same netlist. | Lab (larger die + pad). IR −48% but moved the floorplan. Not a product win. |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_629d82b6b171`) | TPE PLACE_DENSITY_LB_ADDON=0.25, cell_pad=1, TNS_END_PERCENT=100, SETUP_SLACK_MARGIN=0.0, HOLD_SLACK_MARGIN=0.0, CTS_BUF_DISTANCE=100.0, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_f651b02ee7eb`) | TPE PLACE_DENSITY_LB_ADDON=0.1923278878709371, cell_pad=1, TNS_END_PERCENT=72, SETUP_SLACK_MARGIN=0.020973367064114973, HOLD_SLACK_MARGIN=0.01182096068324799, CTS_BUF_DISTANCE=167.9189103120568, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_b71c38a0023d`) | TPE PLACE_DENSITY_LB_ADDON=0.2806052483214573, cell_pad=0, TNS_END_PERCENT=61, SETUP_SLACK_MARGIN=0.0038681245951359034, HOLD_SLACK_MARGIN=0.012210230420351537, CTS_BUF_DISTANCE=103.71485547903293, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_541d4717174a`) | TPE PLACE_DENSITY_LB_ADDON=0.2192676355902049, cell_pad=0, TNS_END_PERCENT=98, SETUP_SLACK_MARGIN=0.011905011766467712, HOLD_SLACK_MARGIN=0.021065798763759285, CTS_BUF_DISTANCE=151.12326670139456, GPL_TIMING_DRIVEN=0. Transfer cook. Official yosys netlist. Policy EVALUATE. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_bbfef932911f`) | TPE PLACE_DENSITY_LB_ADDON=0.15442847617634087, cell_pad=1, TNS_END_PERCENT=63, SETUP_SLACK_MARGIN=0.024229845791076076, HOLD_SLACK_MARGIN=0.024220227395465546, CTS_BUF_DISTANCE=85.6741463933144, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_bc517c38052a`) | TPE PLACE_DENSITY_LB_ADDON=0.15000000000000002, cell_pad=1, TNS_END_PERCENT=100, SETUP_SLACK_MARGIN=0.0, HOLD_SLACK_MARGIN=0.0, CTS_BUF_DISTANCE=100.0, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_2fcef4b2e86a`) | TPE PLACE_DENSITY_LB_ADDON=0.15000000000000002, cell_pad=0, TNS_END_PERCENT=100, SETUP_SLACK_MARGIN=0.05, HOLD_SLACK_MARGIN=0.0, CTS_BUF_DISTANCE=100.0, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_629d82b6b171`) | TPE PLACE_DENSITY_LB_ADDON=0.25, cell_pad=1, TNS_END_PERCENT=100, SETUP_SLACK_MARGIN=0.0, HOLD_SLACK_MARGIN=0.0, CTS_BUF_DISTANCE=100.0, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_f651b02ee7eb`) | TPE PLACE_DENSITY_LB_ADDON=0.1923278878709371, cell_pad=1, TNS_END_PERCENT=72, SETUP_SLACK_MARGIN=0.020973367064114973, HOLD_SLACK_MARGIN=0.01182096068324799, CTS_BUF_DISTANCE=167.9189103120568, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_193e6b9d41e7`) | TPE PLACE_DENSITY_LB_ADDON=0.1977945324187764, cell_pad=1, TNS_END_PERCENT=90, SETUP_SLACK_MARGIN=0.012553435524257656, HOLD_SLACK_MARGIN=0.00568980127697498, CTS_BUF_DISTANCE=161.13025412661705, GPL_TIMING_DRIVEN=0. Transfer cook. Official yosys netlist. Policy EVALUATE. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_541d4717174a`) | TPE PLACE_DENSITY_LB_ADDON=0.2192676355902049, cell_pad=0, TNS_END_PERCENT=98, SETUP_SLACK_MARGIN=0.011905011766467712, HOLD_SLACK_MARGIN=0.021065798763759285, CTS_BUF_DISTANCE=151.12326670139456, GPL_TIMING_DRIVEN=0. Transfer cook. Official yosys netlist. Policy EVALUATE. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_2fcef4b2e86a`) | TPE PLACE_DENSITY_LB_ADDON=0.15000000000000002, cell_pad=0, TNS_END_PERCENT=100, SETUP_SLACK_MARGIN=0.05, HOLD_SLACK_MARGIN=0.0, CTS_BUF_DISTANCE=100.0, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. Restamp after FLOORPLAN_DEF pin fix. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_46fd62ade675`) | TPE PLACE_DENSITY_LB_ADDON=0.2, cell_pad=0, TNS_END_PERCENT=100, SETUP_SLACK_MARGIN=0.05, HOLD_SLACK_MARGIN=0.0, CTS_BUF_DISTANCE=80.0, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. Restamp after FLOORPLAN_DEF pin fix. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_0ba37a6392ad`) | TPE PLACE_DENSITY_LB_ADDON=0.15000000000000002, cell_pad=0, TNS_END_PERCENT=100, SETUP_SLACK_MARGIN=0.0, HOLD_SLACK_MARGIN=0.0, CTS_BUF_DISTANCE=80.0, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. Restamp after FLOORPLAN_DEF pin fix. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_4ef81abb0c78`) | TPE PLACE_DENSITY_LB_ADDON=0.1923278878709371, cell_pad=1, TNS_END_PERCENT=72, SETUP_SLACK_MARGIN=0.05058647195761991, HOLD_SLACK_MARGIN=0.01182096068324799, CTS_BUF_DISTANCE=167.9189103120568, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. Restamp after FLOORPLAN_DEF pin fix. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_15631ca56973`) | TPE PLACE_DENSITY_LB_ADDON=0.23204295480744758, cell_pad=0, TNS_END_PERCENT=58, SETUP_SLACK_MARGIN=0.07169568941723761, HOLD_SLACK_MARGIN=0.007505614437699804, CTS_BUF_DISTANCE=119.99323243951466, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. Restamp after FLOORPLAN_DEF pin fix. | — |
| TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_b9bc5638dab3`) | TPE PLACE_DENSITY_LB_ADDON=0.23010693798102466, cell_pad=1, TNS_END_PERCENT=78, SETUP_SLACK_MARGIN=0.020111012306568164, HOLD_SLACK_MARGIN=0.029056008256546962, CTS_BUF_DISTANCE=100.34702039383953, GPL_TIMING_DRIVEN=1. Transfer cook. Official yosys netlist. Policy EVALUATE. Restamp after FLOORPLAN_DEF pin fix. | — |

### Reference flow (absolute, one row per design@clock)

| Design | Clock ns | Recipe | WNS ps | TNS ns | Area µm² | Power mW | Leak µW | IR worst | IR mean | Density % | Cong. WL/core | GRT WL | fmax MHz | setup viol |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aes | 0.820 | ORFS default @ 0.82 ns (`camp_aes_base`) | -8.9 | -0.024 | 19921.3 | 315.081 | 493.36 | 81.28 | 38.89 | 37.7 | 6.68 | 352701 | 1206.4 | 5 |
| dynamic_node | 6.000 | ORFS default @ 6 ns (`camp_dynamic_node_base`) | 3353.8 | 0.000 | 22540.0 | 8.765 | 429.78 | 1.78 | 1.03 | 43.6 | 5.01 | 259047 | 377.9 | 0 |
| gcd | 0.400 | ORFS default @ 0.4 ns (`camp_gcd_clk040_a`) | -85.8 | -2.479 | 908.4 | 4.213 | 23.93 | 10.83 | 3.45 | 53.0 | 4.31 | 7381 | 2058.4 | 46 |
| gcd | 0.460 | ORFS default — area synthesis, util 35, place +0.20 (`camp_gcd_base`) | -37.2 | -0.595 | 940.3 | 3.932 | 25.64 | 6.67 | 2.64 | 54.9 | 4.43 | 7589 | 2011.4 | 38 |
| gcd | 0.550 | ORFS default @ 0.55 ns (`camp_gcd_clk055_a`) | 13.4 | 0.000 | 696.7 | 2.210 | 16.52 | 3.44 | 1.40 | 40.7 | 3.72 | 6369 | 1863.4 | 0 |
| gcd | 0.700 | ORFS default @ 0.7 ns (`camp_gcd_clk070_a`) | 128.2 | 0.000 | 682.6 | 1.705 | 15.92 | 3.13 | 1.19 | 39.9 | 3.71 | 6346 | 1748.8 | 0 |
| gcd | 0.900 | ORFS default @ 0.9 ns (`camp_gcd_clk090_a`) | 289.1 | 0.000 | 683.1 | 1.335 | 15.93 | 2.96 | 0.96 | 39.9 | 3.76 | 6446 | 1636.8 | 0 |
| ibex | 1.980 | ORFS default @ 1.98 ns (`camp_ibex_clk198_a`) | -23.1 | -0.033 | 30879.4 | 120.508 | 694.93 | 95.41 | 14.45 | 50.1 | 7.16 | 441009 | 499.2 | 4 |
| ibex | 2.200 | ORFS default — area synthesis, util 50, place +0.20 (`camp_ibex_base`) | 22.4 | 0.000 | 30735.2 | 107.868 | 688.21 | 123.77 | 13.11 | 49.9 | 7.12 | 438851 | 459.2 | 0 |
| ibex | 2.750 | ORFS default @ 2.75 ns (`camp_ibex_clk275_a`) | 285.0 | 0.000 | 30707.3 | 86.457 | 685.80 | 76.31 | 10.48 | 49.8 | 7.14 | 440282 | 405.7 | 0 |
| ibex | 3.520 | ORFS default @ 3.52 ns (`camp_ibex_clk352_a`) | 806.7 | 0.000 | 30683.1 | 67.642 | 684.74 | 62.18 | 8.18 | 49.8 | 7.15 | 440701 | 368.6 | 0 |
| spi | 1.000 | ORFS default @ 1 ns (`camp_spi_base`) | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |

### All flows (reference + challengers, absolute values)

| Design | Clock ns | Recipe | Role | Product | WNS ps | TNS ns | Area µm² | Power mW | Leak µW | IR worst | IR mean | Density % | Cong. | GRT WL | fmax | setup |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aes | 0.820 | ORFS default @ 0.82 ns (`camp_aes_base`) | reference | — | -8.9 | -0.024 | 19921.3 | 315.081 | 493.36 | 81.28 | 38.89 | 37.7 | 6.68 | 352701 | 1206.4 | 5 |
| aes | 0.820 | Denser clock buffers (`camp_aes_cts_closer_bufs`) | challenger | win | -1.3 | -0.001 | 19918.3 | 315.049 | 493.14 | 81.46 | 38.90 | 37.7 | 6.68 | 352659 | 1217.7 | 1 |
| aes | 0.820 | Sparser placement (`camp_aes_place_sparser`) | challenger | win | -9.8 | -0.040 | 20141.3 | 318.074 | 500.30 | 70.95 | 36.59 | 38.2 | 6.82 | 359772 | 1205.1 | 11 |
| aes | 0.820 | Setup margin on repair (`camp_aes_repair_setup_margin`) | challenger | win | 16.9 | 0.000 | 20470.3 | 322.686 | 513.84 | 71.85 | 39.30 | 38.8 | 6.74 | 355611 | 1245.1 | 0 |
| aes | 0.820 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_15631ca56973`) | challenger | win | 33.0 | 0.000 | 20764.5 | 328.528 | 526.11 | 80.96 | 40.84 | 39.3 | 6.74 | 355813 | 1270.6 | 0 |
| aes | 0.820 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_2fcef4b2e86a`) | challenger | win | 20.4 | 0.000 | 20720.9 | 327.534 | 522.75 | 76.91 | 38.04 | 39.3 | 6.93 | 365831 | 1250.6 | 0 |
| aes | 0.820 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_46fd62ade675`) | challenger | win | 20.3 | 0.000 | 20487.9 | 323.059 | 514.52 | 73.43 | 39.30 | 38.8 | 6.74 | 355933 | 1250.4 | 0 |
| aes | 0.820 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_4ef81abb0c78`) | challenger | win | 17.7 | 0.000 | 20710.8 | 331.285 | 520.09 | 79.04 | 37.84 | 39.2 | 7.49 | 395314 | 1246.4 | 0 |
| aes | 0.820 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_b9bc5638dab3`) | challenger | win | 0.3 | 0.000 | 20384.4 | 322.224 | 507.35 | 71.85 | 36.20 | 38.6 | 7.27 | 383746 | 1220.0 | 0 |
| aes | 0.820 | Cell padding +1 site (`camp_aes_cell_pad_plus`) | challenger | lose | -29.8 | -0.117 | 20140.5 | 323.238 | 500.57 | 70.79 | 37.08 | 38.2 | 7.42 | 391436 | 1176.8 | 15 |
| aes | 0.820 | Denser placement (`camp_aes_place_denser`) | challenger | tie | -8.6 | -0.014 | 20077.9 | 315.833 | 498.26 | 81.48 | 39.49 | 38.0 | 6.60 | 348150 | 1206.8 | 3 |
| aes | 0.820 | Half TNS repair (`camp_aes_repair_half_tns`) | challenger | lose | -25.3 | -0.154 | 20330.6 | 318.954 | 506.63 | 72.50 | 38.87 | 38.5 | 6.78 | 357677 | 1183.0 | 12 |
| aes | 0.820 | ABC delay synthesis (`camp_aes_synth_delay`) | challenger | tie | -8.9 | -0.024 | 19921.3 | 315.081 | 493.36 | 81.28 | 38.89 | 37.7 | 6.68 | 352701 | 1206.4 | 5 |
| aes | 0.820 | Hierarchical synthesis (`camp_aes_synth_hier`) | challenger | lose | -9.1 | -0.013 | 19676.8 | 320.394 | 485.27 | 94.04 | 39.40 | 37.3 | 6.58 | 347289 | 1206.2 | 3 |
| aes | 0.820 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_0ba37a6392ad`) | challenger | lose | -38.5 | -0.166 | 20131.1 | 317.917 | 500.08 | 70.87 | 36.57 | 38.1 | 6.82 | 359860 | 1164.9 | 14 |
| dynamic_node | 6.000 | ORFS default @ 6 ns (`camp_dynamic_node_base`) | reference | — | 3353.8 | 0.000 | 22540.0 | 8.765 | 429.78 | 1.78 | 1.03 | 43.6 | 5.01 | 259047 | 377.9 | 0 |
| dynamic_node | 6.000 | Denser clock buffers (`camp_dynamic_node_cts_closer_bufs`) | challenger | win | 3377.1 | 0.000 | 22545.4 | 8.770 | 429.91 | 1.79 | 1.03 | 43.6 | 5.01 | 259270 | 381.3 | 0 |
| dynamic_node | 6.000 | Floorplan wider than tall (`camp_dynamic_node_aspect_wide`) | challenger | wrong_die | 3410.2 | 0.000 | 22538.2 | 8.778 | 429.52 | 1.61 | 0.94 | 43.4 | 5.16 | 268210 | 386.1 | 0 |
| dynamic_node | 6.000 | Cell padding +1 site (`camp_dynamic_node_cell_pad_plus`) | challenger | lose | 3304.8 | 0.000 | 22596.2 | 8.856 | 431.99 | 2.11 | 1.01 | 43.7 | 5.35 | 277042 | 371.0 | 0 |
| dynamic_node | 6.000 | Looser core (`camp_dynamic_node_core_looser`) | challenger | wrong_die | 3454.7 | 0.000 | 22631.5 | 8.858 | 431.55 | 1.54 | 0.78 | 32.6 | 3.96 | 274700 | 392.9 | 0 |
| dynamic_node | 6.000 | Tighter core (`camp_dynamic_node_core_tighter`) | challenger | wrong_die | 3419.9 | 0.000 | 22515.6 | 8.739 | 429.59 | 1.95 | 1.08 | 54.4 | 6.06 | 250896 | 387.6 | 0 |
| dynamic_node | 6.000 | Denser placement (`camp_dynamic_node_place_denser`) | challenger | lose | 3323.9 | 0.000 | 22559.5 | 8.786 | 430.44 | 2.35 | 1.07 | 43.6 | 4.97 | 257144 | 373.7 | 0 |
| dynamic_node | 6.000 | Sparser placement (`camp_dynamic_node_place_sparser`) | challenger | lose | 3391.6 | 0.000 | 22578.1 | 8.802 | 431.16 | 2.04 | 1.02 | 43.6 | 5.02 | 259900 | 383.4 | 0 |
| dynamic_node | 6.000 | Half TNS repair (`camp_dynamic_node_repair_half_tns`) | challenger | tie | 3353.8 | 0.000 | 22540.0 | 8.765 | 429.78 | 1.78 | 1.03 | 43.6 | 5.01 | 259047 | 377.9 | 0 |
| dynamic_node | 6.000 | Setup margin on repair (`camp_dynamic_node_repair_setup_margin`) | challenger | tie | 3353.8 | 0.000 | 22540.0 | 8.765 | 429.78 | 1.78 | 1.03 | 43.6 | 5.01 | 259047 | 377.9 | 0 |
| dynamic_node | 6.000 | ABC delay synthesis (`camp_dynamic_node_synth_delay`) | challenger | tie | 3353.8 | 0.000 | 22540.0 | 8.765 | 429.78 | 1.78 | 1.03 | 43.6 | 5.01 | 259047 | 377.9 | 0 |
| gcd | 0.400 | ORFS default @ 0.4 ns (`camp_gcd_clk040_a`) | reference | — | -85.8 | -2.479 | 908.4 | 4.213 | 23.93 | 10.83 | 3.45 | 53.0 | 4.31 | 7381 | 2058.4 | 46 |
| gcd | 0.400 | Netlist DSE / rewrite @ 0.4 ns (`camp_gcd_clk040_b`) | challenger | wrong_die | -389.7 | -15.483 | 631.5 | 2.903 | 15.34 | 5.51 | 2.06 | 55.6 | 4.00 | 4545 | 1266.4 | 47 |
| gcd | 0.400 | Netlist DSE / rewrite @ 0.4 ns (`camp_gcd_clk040_c`) | challenger | lose | -234.8 | -7.769 | 919.3 | 6.101 | 23.89 | 10.62 | 3.92 | 54.2 | 4.77 | 8088 | 1575.3 | 48 |
| gcd | 0.460 | ORFS default — area synthesis, util 35, place +0.20 (`camp_gcd_base`) | reference | — | -37.2 | -0.595 | 940.3 | 3.932 | 25.64 | 6.67 | 2.64 | 54.9 | 4.43 | 7589 | 2011.4 | 38 |
| gcd | 0.460 | Cell padding +1 site (`camp_gcd_cell_pad_plus`) | challenger | win | -40.8 | -0.415 | 875.7 | 3.617 | 23.49 | 5.37 | 2.11 | 51.1 | 4.50 | 7714 | 1997.0 | 12 |
| gcd | 0.460 | Denser placement, same die — fewer repair buffers (`camp_gcd_q1_d25u35`) | challenger | win | -38.4 | -0.354 | 841.6 | 3.434 | 22.03 | 6.15 | 2.23 | 49.1 | 4.07 | 6971 | 2006.4 | 11 |
| gcd | 0.460 | Floorplan wider than tall (`camp_gcd_aspect_wide`) | challenger | wrong_die | -38.1 | -0.345 | 907.6 | 3.723 | 24.36 | 2.62 | 1.29 | 51.7 | 4.19 | 7350 | 2007.7 | 17 |
| gcd | 0.460 | Looser core + wider floorplan (`camp_gcd_core_looser_aspect_wide`) | challenger | wrong_die | -40.6 | -0.960 | 1054.7 | 4.388 | 29.63 | 6.07 | 1.45 | 42.9 | 3.35 | 8236 | 1997.7 | 45 |
| gcd | 0.460 | Looser core + cell padding (`camp_gcd_core_looser_cell_pad_plus`) | challenger | wrong_die | -41.3 | -0.551 | 922.2 | 3.799 | 24.97 | 3.49 | 2.07 | 37.7 | 3.50 | 8564 | 1995.0 | 43 |
| gcd | 0.460 | Denser clock buffers (`camp_gcd_cts_closer_bufs`) | challenger | tie | -37.2 | -0.595 | 940.3 | 3.932 | 25.64 | 6.67 | 2.64 | 54.9 | 4.43 | 7589 | 2011.4 | 38 |
| gcd | 0.460 | ABC delay synthesis on the same physical recipe (`camp_gcd_dse_fast`) | challenger | lose | -186.9 | -5.981 | 963.5 | 5.527 | 25.02 | 8.26 | 3.14 | 56.8 | 4.60 | 7814 | 1545.9 | 46 |
| gcd | 0.460 | Netlist DSE rewrite on default die (geometry control) (`camp_gcd_dse_fixedb`) | challenger | lose | -349.5 | -13.025 | 635.5 | 2.539 | 15.15 | 4.70 | 1.63 | 37.1 | 2.94 | 5038 | 1235.3 | 46 |
| gcd | 0.460 | Netlist DSE rewrite (sub_twos_complement) — place/route same as default (`camp_gcd_dse_small`) | challenger | wrong_die | -338.3 | -13.090 | 609.9 | 2.428 | 14.53 | 3.33 | 1.37 | 53.7 | 3.93 | 4465 | 1252.7 | 46 |
| gcd | 0.460 | Sparser placement, util 25 (`camp_gcd_q1_d15u25`) | challenger | wrong_die | -44.4 | -0.344 | 874.3 | 3.631 | 22.98 | 4.95 | 2.24 | 35.7 | 3.07 | 7506 | 1982.5 | 12 |
| gcd | 0.460 | Sparser placement, util 35 (`camp_gcd_q1_d15u35`) | challenger | lose | -43.7 | -0.744 | 981.3 | 3.995 | 27.29 | 6.76 | 2.64 | 57.3 | 4.47 | 7660 | 1985.3 | 43 |
| gcd | 0.460 | Sparser placement, util 45 (`camp_gcd_q1_d15u45`) | challenger | wrong_die | -36.0 | -0.308 | 861.8 | 3.481 | 22.99 | 10.05 | 2.55 | 63.6 | 4.89 | 6631 | 2016.2 | 11 |
| gcd | 0.460 | Util 25 (`camp_gcd_q1_d20u25`) | challenger | wrong_die | -36.3 | -0.886 | 952.8 | 3.860 | 25.89 | 4.11 | 2.28 | 38.9 | 3.24 | 7928 | 2015.0 | 45 |
| gcd | 0.460 | Util 45 (`camp_gcd_q1_d20u45`) | challenger | wrong_die | -37.7 | -1.040 | 956.5 | 4.016 | 26.05 | 5.72 | 2.33 | 70.6 | 5.44 | 7378 | 2009.3 | 45 |
| gcd | 0.460 | Denser placement, util 25 (`camp_gcd_q1_d25u25`) | challenger | wrong_die | -41.8 | -0.326 | 861.0 | 3.542 | 22.56 | 4.93 | 2.23 | 35.2 | 2.95 | 7216 | 1992.9 | 12 |
| gcd | 0.460 | Denser placement, util 45 (`camp_gcd_q1_d25u45`) | challenger | wrong_die | -38.1 | -0.584 | 860.8 | 3.545 | 22.79 | 6.87 | 2.47 | 63.5 | 5.08 | 6882 | 2007.6 | 42 |
| gcd | 0.460 | Half TNS repair (`camp_gcd_repair_half_tns`) | challenger | lose | -36.6 | -0.549 | 894.6 | 3.677 | 24.00 | 7.97 | 2.59 | 52.2 | 4.31 | 7381 | 2013.6 | 43 |
| gcd | 0.460 | Setup margin on repair (`camp_gcd_repair_setup_margin`) | challenger | lose | -41.1 | -0.512 | 963.7 | 3.995 | 26.41 | 12.22 | 3.12 | 56.3 | 4.50 | 7700 | 1995.7 | 26 |
| gcd | 0.460 | Hierarchical synthesis (`camp_gcd_synth_hier`) | challenger | wrong_die | -42.1 | -0.400 | 889.2 | 9.840 | 23.83 | 17.00 | 6.74 | 49.3 | 4.02 | 7244 | 1991.7 | 16 |
| gcd | 0.460 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_541d4717174a`) | challenger | lose | -43.4 | -0.965 | 945.6 | 3.852 | 26.11 | 5.26 | 2.41 | 55.2 | 4.26 | 7293 | 1986.6 | 45 |
| gcd | 0.460 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_629d82b6b171`) | challenger | tie | -41.6 | -0.451 | 883.4 | 3.643 | 23.66 | 6.91 | 2.59 | 51.6 | 4.62 | 7920 | 1993.7 | 20 |
| gcd | 0.460 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_b71c38a0023d`) | challenger | tie | -39.9 | -0.999 | 966.1 | 4.072 | 26.85 | 7.15 | 2.72 | 56.4 | 4.31 | 7375 | 2000.5 | 44 |
| gcd | 0.460 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_bbfef932911f`) | challenger | lose | -44.6 | -0.855 | 892.7 | 3.646 | 24.01 | 5.43 | 2.17 | 52.1 | 4.86 | 8319 | 1981.9 | 45 |
| gcd | 0.460 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_f651b02ee7eb`) | challenger | lose | -47.3 | -0.842 | 947.2 | 3.918 | 25.80 | 6.01 | 2.24 | 55.3 | 5.16 | 8837 | 1971.3 | 44 |
| gcd | 0.550 | ORFS default @ 0.55 ns (`camp_gcd_clk055_a`) | reference | — | 13.4 | 0.000 | 696.7 | 2.210 | 16.52 | 3.44 | 1.40 | 40.7 | 3.72 | 6369 | 1863.4 | 0 |
| gcd | 0.550 | Netlist DSE / rewrite @ 0.55 ns (`camp_gcd_clk055_b`) | challenger | wrong_die | -251.2 | -9.079 | 611.0 | 2.033 | 14.35 | 5.05 | 1.46 | 53.8 | 4.04 | 4594 | 1248.2 | 43 |
| gcd | 0.550 | Netlist DSE / rewrite @ 0.55 ns (`camp_gcd_clk055_c`) | challenger | lose | -109.3 | -1.409 | 799.6 | 3.783 | 19.40 | 6.86 | 2.38 | 47.1 | 4.60 | 7800 | 1516.9 | 39 |
| gcd | 0.550 | Denser placement at the clock where the default closes (0.55 ns) (`camp_gcd_q4_d25u35_c055`) | challenger | tie | 13.0 | 0.000 | 697.7 | 2.217 | 16.57 | 3.43 | 1.41 | 40.7 | 3.68 | 6309 | 1862.3 | 0 |
| gcd | 0.700 | ORFS default @ 0.7 ns (`camp_gcd_clk070_a`) | reference | — | 128.2 | 0.000 | 682.6 | 1.705 | 15.92 | 3.13 | 1.19 | 39.9 | 3.71 | 6346 | 1748.8 | 0 |
| gcd | 0.700 | Netlist DSE / rewrite @ 0.7 ns (`camp_gcd_clk070_b`) | challenger | wrong_die | -128.3 | -3.498 | 582.8 | 1.534 | 13.62 | 2.45 | 0.94 | 51.3 | 3.62 | 4118 | 1207.3 | 39 |
| gcd | 0.700 | Netlist DSE / rewrite @ 0.7 ns (`camp_gcd_clk070_c`) | challenger | lose | 3.3 | 0.000 | 702.2 | 2.486 | 16.08 | 3.55 | 1.56 | 41.4 | 4.22 | 7164 | 1435.3 | 0 |
| gcd | 0.900 | ORFS default @ 0.9 ns (`camp_gcd_clk090_a`) | reference | — | 289.1 | 0.000 | 683.1 | 1.335 | 15.93 | 2.96 | 0.96 | 39.9 | 3.76 | 6446 | 1636.8 | 0 |
| gcd | 0.900 | Netlist DSE / rewrite @ 0.9 ns (`camp_gcd_clk090_b`) | challenger | wrong_die | 4.7 | 0.000 | 518.7 | 1.039 | 11.59 | 2.32 | 0.65 | 45.6 | 3.52 | 4004 | 1116.9 | 0 |
| gcd | 0.900 | Netlist DSE / rewrite @ 0.9 ns (`camp_gcd_clk090_c`) | challenger | lose | 121.6 | 0.000 | 676.7 | 1.820 | 15.12 | 2.61 | 1.14 | 39.9 | 4.04 | 6857 | 1284.7 | 0 |
| ibex | 1.980 | ORFS default @ 1.98 ns (`camp_ibex_clk198_a`) | reference | — | -23.1 | -0.033 | 30879.4 | 120.508 | 694.93 | 95.41 | 14.45 | 50.1 | 7.16 | 441009 | 499.2 | 4 |
| ibex | 1.980 | ABC delay synthesis @ 1.98 ns (`camp_ibex_clk198_s`) | challenger | wrong_die | -61.1 | -7.110 | 33052.1 | 117.855 | 727.21 | 65.97 | 11.31 | 56.0 | 7.34 | 432835 | 489.9 | 301 |
| ibex | 2.200 | ORFS default — area synthesis, util 50, place +0.20 (`camp_ibex_base`) | reference | — | 22.4 | 0.000 | 30735.2 | 107.868 | 688.21 | 123.77 | 13.11 | 49.9 | 7.12 | 438851 | 459.2 | 0 |
| ibex | 2.200 | Cell padding +1 site (`camp_ibex_cell_pad_plus`) | challenger | win | 21.8 | 0.000 | 30751.2 | 108.247 | 688.60 | 78.68 | 12.14 | 49.9 | 7.60 | 468115 | 459.1 | 0 |
| ibex | 2.200 | Sparser placement, same die (`camp_ibex_q1_d15u50`) | challenger | win | 36.2 | 0.000 | 30748.3 | 107.922 | 688.40 | 125.04 | 12.76 | 49.9 | 7.22 | 445041 | 462.2 | 0 |
| ibex | 2.200 | Denser placement, same die (`camp_ibex_q1_d25u50`) | challenger | win | 39.9 | 0.000 | 30711.0 | 107.344 | 687.50 | 116.96 | 13.41 | 49.8 | 7.02 | 432786 | 462.9 | 0 |
| ibex | 2.200 | Setup margin on repair (`camp_ibex_repair_setup_margin`) | challenger | win | 63.5 | 0.000 | 30743.7 | 107.966 | 688.50 | 123.77 | 13.12 | 49.9 | 7.12 | 438976 | 468.1 | 0 |
| ibex | 2.200 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_193e6b9d41e7`) | challenger | win | 19.5 | 0.000 | 32082.8 | 114.968 | 743.81 | 76.58 | 12.70 | 52.1 | 9.36 | 576791 | 458.6 | 0 |
| ibex | 2.200 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_2fcef4b2e86a`) | challenger | win | 64.8 | 0.000 | 30753.9 | 107.963 | 688.57 | 125.35 | 12.76 | 49.9 | 7.22 | 445218 | 468.3 | 0 |
| ibex | 2.200 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_541d4717174a`) | challenger | win | 54.9 | 0.000 | 32098.0 | 113.862 | 743.86 | 82.98 | 13.24 | 52.1 | 8.86 | 545800 | 466.2 | 0 |
| ibex | 2.200 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_629d82b6b171`) | challenger | win | 34.2 | 0.000 | 30789.8 | 108.212 | 689.97 | 89.94 | 12.38 | 50.0 | 7.60 | 468334 | 461.7 | 0 |
| ibex | 2.200 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_bc517c38052a`) | challenger | win | 48.7 | 0.000 | 30774.1 | 108.699 | 689.47 | 85.67 | 12.09 | 49.9 | 7.62 | 469853 | 464.8 | 0 |
| ibex | 2.200 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_f651b02ee7eb`) | challenger | win | 57.3 | 0.000 | 30791.4 | 108.756 | 690.25 | 78.31 | 12.28 | 50.0 | 7.64 | 470677 | 466.7 | 0 |
| ibex | 2.200 | ABC delay synthesis @ 2.2 ns (`camp_ibex_abcspeed`) | challenger | wrong_die | 20.4 | 0.000 | 30575.4 | 90.815 | 640.35 | 49.13 | 8.77 | 51.8 | 7.16 | 422381 | 458.8 | 0 |
| ibex | 2.200 | Floorplan wider than tall (`camp_ibex_aspect_wide`) | challenger | wrong_die | 24.9 | 0.000 | 30796.4 | 109.442 | 690.62 | 85.83 | 10.49 | 49.9 | 7.62 | 470857 | 459.7 | 0 |
| ibex | 2.200 | Denser clock buffers (`camp_ibex_cts_closer_bufs`) | challenger | tie | 26.5 | 0.000 | 30740.6 | 107.785 | 688.33 | 123.79 | 13.09 | 49.9 | 7.11 | 438255 | 460.1 | 0 |
| ibex | 2.200 | Looser core — larger die, longer wires (`camp_ibex_q1_d20u40`) | challenger | wrong_die | 16.1 | 0.000 | 30776.7 | 108.105 | 688.77 | 71.23 | 8.81 | 39.9 | 5.97 | 460215 | 457.9 | 0 |
| ibex | 2.200 | Tighter core — smaller die, shorter wires (`camp_ibex_q1_d20u60`) | challenger | wrong_die | 42.3 | 0.000 | 30686.0 | 107.499 | 688.06 | 86.24 | 12.65 | 59.6 | 8.17 | 420930 | 463.5 | 0 |
| ibex | 2.200 | Half TNS repair (`camp_ibex_repair_half_tns`) | challenger | tie | 22.4 | 0.000 | 30735.2 | 107.868 | 688.21 | 123.77 | 13.11 | 49.9 | 7.12 | 438851 | 459.2 | 0 |
| ibex | 2.200 | Hierarchical synthesis (`camp_ibex_synth_hier`) | challenger | lose | 30.9 | 0.000 | 30728.3 | 108.751 | 685.46 | 145.53 | 14.34 | 49.7 | 7.04 | 434867 | 461.0 | 0 |
| ibex | 2.750 | ORFS default @ 2.75 ns (`camp_ibex_clk275_a`) | reference | — | 285.0 | 0.000 | 30707.3 | 86.457 | 685.80 | 76.31 | 10.48 | 49.8 | 7.14 | 440282 | 405.7 | 0 |
| ibex | 2.750 | ABC delay synthesis @ 2.75 ns (`camp_ibex_clk275_s`) | challenger | wrong_die | 166.3 | 0.000 | 30065.2 | 70.620 | 621.71 | 26.41 | 6.77 | 51.0 | 7.08 | 417747 | 387.0 | 0 |
| ibex | 3.520 | ORFS default @ 3.52 ns (`camp_ibex_clk352_a`) | reference | — | 806.7 | 0.000 | 30683.1 | 67.642 | 684.74 | 62.18 | 8.18 | 49.8 | 7.15 | 440701 | 368.6 | 0 |
| ibex | 3.520 | ABC delay synthesis @ 3.52 ns (`camp_ibex_clk352_s`) | challenger | wrong_die | 597.2 | 0.000 | 30033.5 | 55.188 | 620.45 | 30.35 | 5.33 | 50.9 | 7.11 | 419434 | 342.1 | 0 |
| spi | 1.000 | ORFS default @ 1 ns (`camp_spi_base`) | reference | — | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |
| spi | 1.000 | ABC delay synthesis @ 1 ns (`camp_spi_abcspeed`) | challenger | wrong_die | 600.8 | 0.000 | 265.7 | 0.313 | 5.80 | 1.06 | 0.62 | 9.2 | 0.65 | 1889 | 2505.0 | 0 |
| spi | 1.000 | Floorplan wider than tall (`camp_spi_aspect_wide`) | challenger | wrong_die | 611.7 | 0.000 | 275.6 | 0.304 | 5.32 | 1.77 | 0.61 | 9.9 | 0.81 | 2268 | 2575.6 | 0 |
| spi | 1.000 | Cell padding +1 site (`camp_spi_cell_pad_plus`) | challenger | tie | 612.5 | 0.000 | 267.6 | 0.302 | 5.32 | 0.93 | 0.52 | 9.4 | 0.83 | 2368 | 2580.3 | 0 |
| spi | 1.000 | Looser core (`camp_spi_core_looser`) | challenger | wrong_die | 611.7 | 0.000 | 272.9 | 0.300 | 5.32 | 1.15 | 0.54 | 6.0 | 0.51 | 2308 | 2575.4 | 0 |
| spi | 1.000 | Tighter core (`camp_spi_core_tighter`) | challenger | wrong_die | 615.5 | 0.000 | 260.7 | 0.298 | 5.32 | 2.09 | 1.10 | 21.0 | 1.49 | 1855 | 2600.5 | 0 |
| spi | 1.000 | Denser clock buffers (`camp_spi_cts_closer_bufs`) | challenger | tie | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |
| spi | 1.000 | Sparser clock buffers (`camp_spi_cts_sparser`) | challenger | tie | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |
| spi | 1.000 | Hold margin on repair (`camp_spi_hold_margin`) | challenger | tie | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |
| spi | 1.000 | Denser placement (`camp_spi_place_denser`) | challenger | tie | 610.7 | 0.000 | 268.1 | 0.307 | 5.35 | 1.07 | 0.56 | 9.4 | 0.78 | 2205 | 2569.0 | 0 |
| spi | 1.000 | Placement without timing-driven (`camp_spi_place_notiming`) | challenger | lose | 611.0 | 0.000 | 272.4 | 0.303 | 5.52 | 1.44 | 0.57 | 9.6 | 0.75 | 2140 | 2570.8 | 0 |
| spi | 1.000 | Sparser placement (`camp_spi_place_sparser`) | challenger | tie | 613.3 | 0.000 | 267.6 | 0.303 | 5.32 | 1.04 | 0.50 | 9.4 | 0.82 | 2317 | 2586.1 | 0 |
| spi | 1.000 | Half TNS repair (`camp_spi_repair_half_tns`) | challenger | tie | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |
| spi | 1.000 | Setup margin on repair (`camp_spi_repair_setup_margin`) | challenger | tie | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |
| spi | 1.000 | No TNS repair (`camp_spi_repair_skip`) | challenger | tie | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |
| spi | 1.000 | Hierarchical synthesis (`camp_spi_synth_hier`) | challenger | tie | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |

### Challengers vs the reference in the same slot (Δ)

ΔWNS = cand − reference (ps; + better). Percent columns = 100·(cand−reference)/reference (− better for area/power/leak/IR/WL).

| Design | Clock | Recipe | Product | ΔWNS | Δarea % | Δpower % | Δleak % | ΔIR worst % | ΔIR mean % | ΔWL % | Δcong % | Δdens % |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gcd | 0.460 | Netlist DSE rewrite (sub_twos_complement) — place/route same as default (`camp_gcd_dse_small`) | wrong_die | -301.13 | -35.13 | -38.26 | -43.36 | -50.08 | -48.11 | -41.16 | -11.33 | -2.25 |
| gcd | 0.460 | ABC delay synthesis on the same physical recipe (`camp_gcd_dse_fast`) | lose | -149.72 | 2.46 | 40.56 | -2.42 | 23.84 | 18.95 | 2.96 | 3.90 | 3.39 |
| gcd | 0.460 | Netlist DSE rewrite on default die (geometry control) (`camp_gcd_dse_fixedb`) | lose | -312.32 | -32.42 | -35.43 | -40.94 | -29.48 | -38.13 | -33.61 | -33.61 | -32.42 |
| gcd | 0.400 | Netlist DSE / rewrite @ 0.4 ns (`camp_gcd_clk040_b`) | wrong_die | -303.84 | -30.48 | -31.10 | -35.91 | -49.07 | -40.10 | -38.42 | -7.20 | 4.76 |
| gcd | 0.400 | Netlist DSE / rewrite @ 0.4 ns (`camp_gcd_clk040_c`) | lose | -149.00 | 1.20 | 44.81 | -0.18 | -1.87 | 13.85 | 9.58 | 10.57 | 2.12 |
| gcd | 0.550 | Netlist DSE / rewrite @ 0.55 ns (`camp_gcd_clk055_b`) | wrong_die | -264.54 | -12.29 | -8.00 | -13.14 | 46.66 | 3.95 | -27.87 | 8.70 | 32.17 |
| gcd | 0.550 | Netlist DSE / rewrite @ 0.55 ns (`camp_gcd_clk055_c`) | lose | -122.61 | 14.78 | 71.23 | 17.42 | 99.49 | 70.20 | 22.47 | 23.58 | 15.82 |
| gcd | 0.700 | Netlist DSE / rewrite @ 0.7 ns (`camp_gcd_clk070_b`) | wrong_die | -256.48 | -14.61 | -10.03 | -14.41 | -21.85 | -21.35 | -35.11 | -2.21 | 28.68 |
| gcd | 0.700 | Netlist DSE / rewrite @ 0.7 ns (`camp_gcd_clk070_c`) | lose | -124.89 | 2.88 | 45.86 | 1.01 | 13.24 | 30.57 | 12.89 | 13.92 | 3.82 |
| gcd | 0.900 | Netlist DSE / rewrite @ 0.9 ns (`camp_gcd_clk090_b`) | wrong_die | -284.37 | -24.07 | -22.18 | -27.24 | -21.62 | -32.26 | -37.88 | -6.39 | 14.44 |
| gcd | 0.900 | Netlist DSE / rewrite @ 0.9 ns (`camp_gcd_clk090_c`) | lose | -167.44 | -0.93 | 36.36 | -5.05 | -12.06 | 17.91 | 6.38 | 7.34 | -0.03 |
| spi | 1.000 | ABC delay synthesis @ 1 ns (`camp_spi_abcspeed`) | wrong_die | -11.43 | -0.70 | 3.93 | 9.05 | 8.38 | 17.44 | -16.30 | -18.05 | -2.77 |
| ibex | 2.200 | ABC delay synthesis @ 2.2 ns (`camp_ibex_abcspeed`) | wrong_die | -2.02 | -0.52 | -15.81 | -6.95 | -60.31 | -33.12 | -3.75 | 0.55 | 3.92 |
| ibex | 1.980 | ABC delay synthesis @ 1.98 ns (`camp_ibex_clk198_s`) | wrong_die | -37.97 | 7.04 | -2.20 | 4.65 | -30.86 | -21.73 | -1.85 | 2.53 | 11.82 |
| ibex | 2.750 | ABC delay synthesis @ 2.75 ns (`camp_ibex_clk275_s`) | wrong_die | -118.73 | -2.09 | -18.32 | -9.35 | -65.39 | -35.41 | -5.12 | -0.88 | 2.28 |
| ibex | 3.520 | ABC delay synthesis @ 3.52 ns (`camp_ibex_clk352_s`) | wrong_die | -209.54 | -2.12 | -18.41 | -9.39 | -51.20 | -34.88 | -4.83 | -0.57 | 2.26 |
| gcd | 0.460 | Sparser placement, util 25 (`camp_gcd_q1_d15u25`) | wrong_die | -7.24 | -7.02 | -7.67 | -10.40 | -25.74 | -15.03 | -1.09 | -30.82 | -34.97 |
| gcd | 0.460 | Sparser placement, util 35 (`camp_gcd_q1_d15u35`) | lose | -6.53 | 4.36 | 1.60 | 6.40 | 1.47 | 0.29 | 0.94 | 0.94 | 4.36 |
| gcd | 0.460 | Sparser placement, util 45 (`camp_gcd_q1_d15u45`) | wrong_die | 1.19 | -8.35 | -11.48 | -10.36 | 50.74 | -3.30 | -12.62 | 10.39 | 15.79 |
| gcd | 0.460 | Util 25 (`camp_gcd_q1_d20u25`) | wrong_die | 0.89 | 1.33 | -1.84 | 0.96 | -38.32 | -13.47 | 4.47 | -26.94 | -29.13 |
| gcd | 0.460 | Util 45 (`camp_gcd_q1_d20u45`) | wrong_die | -0.51 | 1.73 | 2.11 | 1.60 | -14.27 | -11.82 | -2.78 | 22.82 | 28.51 |
| gcd | 0.460 | Denser placement, util 25 (`camp_gcd_q1_d25u25`) | wrong_die | -4.62 | -8.43 | -9.94 | -12.03 | -26.09 | -15.53 | -4.92 | -33.50 | -35.96 |
| gcd | 0.460 | Denser placement, same die — fewer repair buffers (`camp_gcd_q1_d25u35`) | win | -1.23 | -10.50 | -12.67 | -14.11 | -7.69 | -15.28 | -8.14 | -8.14 | -10.50 |
| gcd | 0.460 | Denser placement, util 45 (`camp_gcd_q1_d25u45`) | wrong_die | -0.94 | -8.46 | -9.86 | -11.14 | 3.11 | -6.16 | -9.32 | 14.56 | 15.65 |
| ibex | 2.200 | Sparser placement, same die (`camp_ibex_q1_d15u50`) | win | 13.81 | 0.04 | 0.05 | 0.03 | 1.02 | -2.67 | 1.41 | 1.41 | 0.04 |
| ibex | 2.200 | Denser placement, same die (`camp_ibex_q1_d25u50`) | win | 17.48 | -0.08 | -0.49 | -0.10 | -5.50 | 2.29 | -1.38 | -1.38 | -0.08 |
| ibex | 2.200 | Looser core — larger die, longer wires (`camp_ibex_q1_d20u40`) | wrong_die | -6.30 | 0.14 | 0.22 | 0.08 | -42.45 | -32.77 | 4.87 | -16.18 | -19.96 |
| ibex | 2.200 | Tighter core — smaller die, shorter wires (`camp_ibex_q1_d20u60`) | wrong_die | 19.94 | -0.16 | -0.34 | -0.02 | -30.33 | -3.53 | -4.08 | 14.79 | 19.49 |
| gcd | 0.550 | Denser placement at the clock where the default closes (0.55 ns) (`camp_gcd_q4_d25u35_c055`) | tie | -0.33 | 0.15 | 0.35 | 0.26 | -0.31 | 0.67 | -0.94 | -0.94 | 0.15 |
| spi | 1.000 | Denser placement (`camp_spi_place_denser`) | tie | -1.48 | 0.20 | 2.07 | 0.54 | 9.81 | 6.79 | -2.30 | -2.30 | 0.20 |
| spi | 1.000 | Half TNS repair (`camp_spi_repair_half_tns`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| spi | 1.000 | Sparser placement (`camp_spi_place_sparser`) | tie | 1.08 | 0.00 | 0.64 | 0.00 | 6.93 | -4.24 | 2.66 | 2.66 | 0.00 |
| spi | 1.000 | Cell padding +1 site (`camp_spi_cell_pad_plus`) | tie | 0.22 | 0.00 | 0.30 | 0.00 | -5.22 | -2.07 | 4.92 | 4.92 | 0.00 |
| spi | 1.000 | Setup margin on repair (`camp_spi_repair_setup_margin`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| spi | 1.000 | Denser clock buffers (`camp_spi_cts_closer_bufs`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| spi | 1.000 | Floorplan wider than tall (`camp_spi_aspect_wide`) | wrong_die | -0.50 | 2.98 | 1.02 | 0.00 | 80.90 | 15.14 | 0.49 | 2.25 | 4.79 |
| spi | 1.000 | Tighter core (`camp_spi_core_tighter`) | wrong_die | 3.22 | -2.58 | -1.06 | 0.00 | 113.72 | 108.34 | -17.81 | 87.72 | 122.50 |
| spi | 1.000 | Looser core (`camp_spi_core_looser`) | wrong_die | -0.53 | 1.99 | -0.12 | 0.00 | 17.74 | 2.49 | 2.26 | -36.10 | -36.27 |
| spi | 1.000 | Hierarchical synthesis (`camp_spi_synth_hier`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| gcd | 0.460 | Setup margin on repair (`camp_gcd_repair_setup_margin`) | lose | -3.90 | 2.49 | 1.60 | 3.00 | 83.24 | 18.20 | 1.46 | 1.46 | 2.49 |
| gcd | 0.460 | Floorplan wider than tall (`camp_gcd_aspect_wide`) | wrong_die | -0.91 | -3.48 | -5.33 | -5.01 | -60.72 | -51.13 | -3.15 | -5.44 | -5.76 |
| aes | 0.820 | Denser placement (`camp_aes_place_denser`) | tie | 0.28 | 0.79 | 0.24 | 0.99 | 0.25 | 1.54 | -1.29 | -1.29 | 0.79 |
| aes | 0.820 | Setup margin on repair (`camp_aes_repair_setup_margin`) | win | 25.78 | 2.76 | 2.41 | 4.15 | -11.59 | 1.07 | 0.83 | 0.83 | 2.76 |
| gcd | 0.460 | Hierarchical synthesis (`camp_gcd_synth_hier`) | wrong_die | -4.91 | -5.43 | 150.23 | -7.08 | 154.99 | 155.61 | -4.55 | -9.36 | -10.20 |
| gcd | 0.460 | Cell padding +1 site (`camp_gcd_cell_pad_plus`) | win | -3.59 | -6.87 | -8.01 | -8.40 | -19.40 | -19.84 | 1.65 | 1.65 | -6.87 |
| gcd | 0.460 | Half TNS repair (`camp_gcd_repair_half_tns`) | lose | 0.55 | -4.87 | -6.49 | -6.41 | 19.47 | -1.98 | -2.74 | -2.74 | -4.87 |
| gcd | 0.460 | Denser clock buffers (`camp_gcd_cts_closer_bufs`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| ibex | 2.200 | Hierarchical synthesis (`camp_ibex_synth_hier`) | lose | 8.46 | -0.02 | 0.82 | -0.40 | 17.58 | 9.38 | -0.91 | -1.13 | -0.25 |
| ibex | 2.200 | Floorplan wider than tall (`camp_ibex_aspect_wide`) | wrong_die | 2.48 | 0.20 | 1.46 | 0.35 | -30.65 | -19.97 | 7.29 | 7.07 | -0.01 |
| ibex | 2.200 | Cell padding +1 site (`camp_ibex_cell_pad_plus`) | win | -0.66 | 0.05 | 0.35 | 0.06 | -36.43 | -7.40 | 6.67 | 6.67 | 0.05 |
| ibex | 2.200 | Half TNS repair (`camp_ibex_repair_half_tns`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| ibex | 2.200 | Setup margin on repair (`camp_ibex_repair_setup_margin`) | win | 41.11 | 0.03 | 0.09 | 0.04 | -0.00 | 0.08 | 0.03 | 0.03 | 0.03 |
| ibex | 2.200 | Denser clock buffers (`camp_ibex_cts_closer_bufs`) | tie | 4.11 | 0.02 | -0.08 | 0.02 | 0.01 | -0.15 | -0.14 | -0.14 | 0.02 |
| aes | 0.820 | ABC delay synthesis (`camp_aes_synth_delay`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| aes | 0.820 | Hierarchical synthesis (`camp_aes_synth_hier`) | lose | -0.15 | -1.23 | 1.69 | -1.64 | 15.70 | 1.32 | -1.53 | -1.53 | -1.23 |
| aes | 0.820 | Sparser placement (`camp_aes_place_sparser`) | win | -0.86 | 1.10 | 0.95 | 1.41 | -12.71 | -5.91 | 2.00 | 2.00 | 1.10 |
| aes | 0.820 | Cell padding +1 site (`camp_aes_cell_pad_plus`) | lose | -20.83 | 1.10 | 2.59 | 1.46 | -12.91 | -4.66 | 10.98 | 10.98 | 1.10 |
| aes | 0.820 | Half TNS repair (`camp_aes_repair_half_tns`) | lose | -16.37 | 2.05 | 1.23 | 2.69 | -10.80 | -0.05 | 1.41 | 1.41 | 2.05 |
| aes | 0.820 | Denser clock buffers (`camp_aes_cts_closer_bufs`) | win | 7.67 | -0.02 | -0.01 | -0.04 | 0.23 | 0.04 | -0.01 | -0.01 | -0.01 |
| dynamic_node | 6.000 | ABC delay synthesis (`camp_dynamic_node_synth_delay`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| dynamic_node | 6.000 | Tighter core (`camp_dynamic_node_core_tighter`) | wrong_die | 66.10 | -0.11 | -0.30 | -0.05 | 9.36 | 4.53 | -3.15 | 21.00 | 24.80 |
| dynamic_node | 6.000 | Looser core (`camp_dynamic_node_core_looser`) | wrong_die | 100.82 | 0.41 | 1.06 | 0.41 | -13.69 | -24.59 | 6.04 | -20.88 | -25.08 |
| dynamic_node | 6.000 | Floorplan wider than tall (`camp_dynamic_node_aspect_wide`) | wrong_die | 56.36 | -0.01 | 0.15 | -0.06 | -9.72 | -9.04 | 3.54 | 3.16 | -0.37 |
| dynamic_node | 6.000 | Denser placement (`camp_dynamic_node_place_denser`) | lose | -29.90 | 0.09 | 0.23 | 0.15 | 31.70 | 3.41 | -0.73 | -0.73 | 0.09 |
| dynamic_node | 6.000 | Sparser placement (`camp_dynamic_node_place_sparser`) | lose | 37.72 | 0.17 | 0.42 | 0.32 | 14.60 | -0.94 | 0.33 | 0.33 | 0.17 |
| dynamic_node | 6.000 | Cell padding +1 site (`camp_dynamic_node_cell_pad_plus`) | lose | -49.05 | 0.25 | 1.03 | 0.51 | 18.19 | -2.49 | 6.95 | 6.95 | 0.25 |
| dynamic_node | 6.000 | Half TNS repair (`camp_dynamic_node_repair_half_tns`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| dynamic_node | 6.000 | Setup margin on repair (`camp_dynamic_node_repair_setup_margin`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| dynamic_node | 6.000 | Denser clock buffers (`camp_dynamic_node_cts_closer_bufs`) | win | 23.22 | 0.02 | 0.06 | 0.03 | 0.30 | -0.45 | 0.09 | 0.09 | 0.02 |
| spi | 1.000 | Placement without timing-driven (`camp_spi_place_notiming`) | lose | -1.23 | 1.79 | 0.86 | 3.83 | 47.69 | 8.66 | -5.18 | -5.18 | 1.79 |
| spi | 1.000 | Hold margin on repair (`camp_spi_hold_margin`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| spi | 1.000 | Sparser clock buffers (`camp_spi_cts_sparser`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| spi | 1.000 | No TNS repair (`camp_spi_repair_skip`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| gcd | 0.460 | Looser core + wider floorplan (`camp_gcd_core_looser_aspect_wide`) | wrong_die | -3.40 | 12.16 | 11.58 | 15.54 | -8.94 | -44.97 | 8.53 | -24.47 | -21.93 |
| gcd | 0.460 | Looser core + cell padding (`camp_gcd_core_looser_cell_pad_plus`) | wrong_die | -4.09 | -1.92 | -3.41 | -2.64 | -47.60 | -21.36 | 12.85 | -21.07 | -31.41 |
| gcd | 0.460 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_629d82b6b171`) | tie | -4.42 | -6.05 | -7.36 | -7.75 | 3.62 | -1.83 | 4.36 | 4.36 | -6.05 |
| gcd | 0.460 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_f651b02ee7eb`) | lose | -10.11 | 0.74 | -0.37 | 0.60 | -9.89 | -15.14 | 16.44 | 16.44 | 0.74 |
| gcd | 0.460 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_b71c38a0023d`) | tie | -2.70 | 2.74 | 3.54 | 4.68 | 7.18 | 2.98 | -2.82 | -2.82 | 2.74 |
| gcd | 0.460 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_541d4717174a`) | lose | -6.21 | 0.57 | -2.04 | 1.82 | -21.06 | -8.50 | -3.90 | -3.90 | 0.57 |
| gcd | 0.460 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_gcd_tpe_bbfef932911f`) | lose | -7.40 | -5.06 | -7.30 | -6.36 | -18.61 | -17.86 | 9.62 | 9.62 | -5.06 |
| ibex | 2.200 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_bc517c38052a`) | win | 26.28 | 0.13 | 0.77 | 0.18 | -30.78 | -7.75 | 7.06 | 7.06 | 0.13 |
| ibex | 2.200 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_2fcef4b2e86a`) | win | 42.37 | 0.06 | 0.09 | 0.05 | 1.27 | -2.67 | 1.45 | 1.45 | 0.06 |
| ibex | 2.200 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_629d82b6b171`) | win | 11.79 | 0.18 | 0.32 | 0.26 | -27.33 | -5.56 | 6.72 | 6.72 | 0.18 |
| ibex | 2.200 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_f651b02ee7eb`) | win | 34.92 | 0.18 | 0.82 | 0.30 | -36.73 | -6.30 | 7.25 | 7.25 | 0.18 |
| ibex | 2.200 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_193e6b9d41e7`) | win | -2.94 | 4.38 | 6.58 | 8.08 | -38.13 | -3.13 | 31.43 | 31.43 | 4.38 |
| ibex | 2.200 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_ibex_tpe_541d4717174a`) | win | 32.48 | 4.43 | 5.56 | 8.09 | -32.96 | 0.97 | 24.37 | 24.37 | 4.43 |
| aes | 0.820 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_2fcef4b2e86a`) | win | 29.30 | 4.01 | 3.95 | 5.96 | -5.37 | -2.17 | 3.72 | 3.72 | 4.01 |
| aes | 0.820 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_46fd62ade675`) | win | 29.19 | 2.84 | 2.53 | 4.29 | -9.66 | 1.06 | 0.92 | 0.92 | 2.84 |
| aes | 0.820 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_0ba37a6392ad`) | lose | -29.54 | 1.05 | 0.90 | 1.36 | -12.81 | -5.97 | 2.03 | 2.03 | 1.05 |
| aes | 0.820 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_4ef81abb0c78`) | win | 26.63 | 3.96 | 5.14 | 5.42 | -2.75 | -2.69 | 12.08 | 12.08 | 3.96 |
| aes | 0.820 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_15631ca56973`) | win | 41.89 | 4.23 | 4.27 | 6.64 | -0.39 | 5.02 | 0.88 | 0.88 | 4.23 |
| aes | 0.820 | TPE PLACE_DENSITY_LB_ADDON=0 (`camp_aes_tpe_b9bc5638dab3`) | win | 9.26 | 2.32 | 2.27 | 2.84 | -11.60 | -6.92 | 8.80 | 8.80 | 2.32 |

### Side-by-side sheets (reference column + each challenger)

#### aes @ 0.820 ns — reference: ORFS default @ 0.82 ns (1/4)

| Metric | `ORFS default @ 0.82 ns` | `Denser clock buffers` | `Sparser placement` | `Setup margin on repair` | `TPE PLACE_DENSITY_LB_ADDON=0` |
|---|---|---|---|---|---|
| WNS (ps) | -8.9 | -1.3 | -9.8 | 16.9 | 33.0 |
| TNS (ns) | -0.024 | -0.001 | -0.040 | 0.000 | 0.000 |
| stdcell area (µm²) | 19921.3 | 19918.3 | 20141.3 | 20470.3 | 20764.5 |
| total power (mW) | 315.081 | 315.049 | 318.074 | 322.686 | 328.528 |
| leakage (µW) | 493.36 | 493.14 | 500.30 | 513.84 | 526.11 |
| IR worst VDD (mV) | 81.28 | 81.46 | 70.95 | 71.85 | 80.96 |
| IR mean VDD (mV) | 38.89 | 38.90 | 36.59 | 39.30 | 40.84 |
| cell density (%) | 37.7 | 37.7 | 38.2 | 38.8 | 39.3 |
| congestion WL/core | 6.68 | 6.68 | 6.82 | 6.74 | 6.74 |
| GRT wirelength | 352701 | 352659 | 359772 | 355611 | 355813 |
| fmax (MHz) | 1206.4 | 1217.7 | 1205.1 | 1245.1 | 1270.6 |
| setup violations | 5 | 1 | 11 | 0 | 0 |

#### aes @ 0.820 ns — reference: ORFS default @ 0.82 ns (2/4)

| Metric | `ORFS default @ 0.82 ns` | `TPE PLACE_DENSITY_LB_ADDON=0` | `TPE PLACE_DENSITY_LB_ADDON=0` | `TPE PLACE_DENSITY_LB_ADDON=0` | `TPE PLACE_DENSITY_LB_ADDON=0` |
|---|---|---|---|---|---|
| WNS (ps) | -8.9 | 20.4 | 20.3 | 17.7 | 0.3 |
| TNS (ns) | -0.024 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 19921.3 | 20720.9 | 20487.9 | 20710.8 | 20384.4 |
| total power (mW) | 315.081 | 327.534 | 323.059 | 331.285 | 322.224 |
| leakage (µW) | 493.36 | 522.75 | 514.52 | 520.09 | 507.35 |
| IR worst VDD (mV) | 81.28 | 76.91 | 73.43 | 79.04 | 71.85 |
| IR mean VDD (mV) | 38.89 | 38.04 | 39.30 | 37.84 | 36.20 |
| cell density (%) | 37.7 | 39.3 | 38.8 | 39.2 | 38.6 |
| congestion WL/core | 6.68 | 6.93 | 6.74 | 7.49 | 7.27 |
| GRT wirelength | 352701 | 365831 | 355933 | 395314 | 383746 |
| fmax (MHz) | 1206.4 | 1250.6 | 1250.4 | 1246.4 | 1220.0 |
| setup violations | 5 | 0 | 0 | 0 | 0 |

#### aes @ 0.820 ns — reference: ORFS default @ 0.82 ns (3/4)

| Metric | `ORFS default @ 0.82 ns` | `Cell padding +1 site` | `Denser placement` | `Half TNS repair` | `ABC delay synthesis` |
|---|---|---|---|---|---|
| WNS (ps) | -8.9 | -29.8 | -8.6 | -25.3 | -8.9 |
| TNS (ns) | -0.024 | -0.117 | -0.014 | -0.154 | -0.024 |
| stdcell area (µm²) | 19921.3 | 20140.5 | 20077.9 | 20330.6 | 19921.3 |
| total power (mW) | 315.081 | 323.238 | 315.833 | 318.954 | 315.081 |
| leakage (µW) | 493.36 | 500.57 | 498.26 | 506.63 | 493.36 |
| IR worst VDD (mV) | 81.28 | 70.79 | 81.48 | 72.50 | 81.28 |
| IR mean VDD (mV) | 38.89 | 37.08 | 39.49 | 38.87 | 38.89 |
| cell density (%) | 37.7 | 38.2 | 38.0 | 38.5 | 37.7 |
| congestion WL/core | 6.68 | 7.42 | 6.60 | 6.78 | 6.68 |
| GRT wirelength | 352701 | 391436 | 348150 | 357677 | 352701 |
| fmax (MHz) | 1206.4 | 1176.8 | 1206.8 | 1183.0 | 1206.4 |
| setup violations | 5 | 15 | 3 | 12 | 5 |

#### aes @ 0.820 ns — reference: ORFS default @ 0.82 ns (4/4)

| Metric | `ORFS default @ 0.82 ns` | `Hierarchical synthesis` | `TPE PLACE_DENSITY_LB_ADDON=0` |
|---|---|---|---|
| WNS (ps) | -8.9 | -9.1 | -38.5 |
| TNS (ns) | -0.024 | -0.013 | -0.166 |
| stdcell area (µm²) | 19921.3 | 19676.8 | 20131.1 |
| total power (mW) | 315.081 | 320.394 | 317.917 |
| leakage (µW) | 493.36 | 485.27 | 500.08 |
| IR worst VDD (mV) | 81.28 | 94.04 | 70.87 |
| IR mean VDD (mV) | 38.89 | 39.40 | 36.57 |
| cell density (%) | 37.7 | 37.3 | 38.1 |
| congestion WL/core | 6.68 | 6.58 | 6.82 |
| GRT wirelength | 352701 | 347289 | 359860 |
| fmax (MHz) | 1206.4 | 1206.2 | 1164.9 |
| setup violations | 5 | 3 | 14 |

#### dynamic_node @ 6.000 ns — reference: ORFS default @ 6 ns (1/3)

| Metric | `ORFS default @ 6 ns` | `Denser clock buffers` | `Floorplan wider than tall` | `Cell padding +1 site` | `Looser core` |
|---|---|---|---|---|---|
| WNS (ps) | 3353.8 | 3377.1 | 3410.2 | 3304.8 | 3454.7 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 22540.0 | 22545.4 | 22538.2 | 22596.2 | 22631.5 |
| total power (mW) | 8.765 | 8.770 | 8.778 | 8.856 | 8.858 |
| leakage (µW) | 429.78 | 429.91 | 429.52 | 431.99 | 431.55 |
| IR worst VDD (mV) | 1.78 | 1.79 | 1.61 | 2.11 | 1.54 |
| IR mean VDD (mV) | 1.03 | 1.03 | 0.94 | 1.01 | 0.78 |
| cell density (%) | 43.6 | 43.6 | 43.4 | 43.7 | 32.6 |
| congestion WL/core | 5.01 | 5.01 | 5.16 | 5.35 | 3.96 |
| GRT wirelength | 259047 | 259270 | 268210 | 277042 | 274700 |
| fmax (MHz) | 377.9 | 381.3 | 386.1 | 371.0 | 392.9 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### dynamic_node @ 6.000 ns — reference: ORFS default @ 6 ns (2/3)

| Metric | `ORFS default @ 6 ns` | `Tighter core` | `Denser placement` | `Sparser placement` | `Half TNS repair` |
|---|---|---|---|---|---|
| WNS (ps) | 3353.8 | 3419.9 | 3323.9 | 3391.6 | 3353.8 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 22540.0 | 22515.6 | 22559.5 | 22578.1 | 22540.0 |
| total power (mW) | 8.765 | 8.739 | 8.786 | 8.802 | 8.765 |
| leakage (µW) | 429.78 | 429.59 | 430.44 | 431.16 | 429.78 |
| IR worst VDD (mV) | 1.78 | 1.95 | 2.35 | 2.04 | 1.78 |
| IR mean VDD (mV) | 1.03 | 1.08 | 1.07 | 1.02 | 1.03 |
| cell density (%) | 43.6 | 54.4 | 43.6 | 43.6 | 43.6 |
| congestion WL/core | 5.01 | 6.06 | 4.97 | 5.02 | 5.01 |
| GRT wirelength | 259047 | 250896 | 257144 | 259900 | 259047 |
| fmax (MHz) | 377.9 | 387.6 | 373.7 | 383.4 | 377.9 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### dynamic_node @ 6.000 ns — reference: ORFS default @ 6 ns (3/3)

| Metric | `ORFS default @ 6 ns` | `Setup margin on repair` | `ABC delay synthesis` |
|---|---|---|---|
| WNS (ps) | 3353.8 | 3353.8 | 3353.8 |
| TNS (ns) | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 22540.0 | 22540.0 | 22540.0 |
| total power (mW) | 8.765 | 8.765 | 8.765 |
| leakage (µW) | 429.78 | 429.78 | 429.78 |
| IR worst VDD (mV) | 1.78 | 1.78 | 1.78 |
| IR mean VDD (mV) | 1.03 | 1.03 | 1.03 |
| cell density (%) | 43.6 | 43.6 | 43.6 |
| congestion WL/core | 5.01 | 5.01 | 5.01 |
| GRT wirelength | 259047 | 259047 | 259047 |
| fmax (MHz) | 377.9 | 377.9 | 377.9 |
| setup violations | 0 | 0 | 0 |

#### gcd @ 0.400 ns — reference: ORFS default @ 0.4 ns

| Metric | `ORFS default @ 0.4 ns` | `Netlist DSE / rewrite @ 0.4 ns` | `Netlist DSE / rewrite @ 0.4 ns` |
|---|---|---|---|
| WNS (ps) | -85.8 | -389.7 | -234.8 |
| TNS (ns) | -2.479 | -15.483 | -7.769 |
| stdcell area (µm²) | 908.4 | 631.5 | 919.3 |
| total power (mW) | 4.213 | 2.903 | 6.101 |
| leakage (µW) | 23.93 | 15.34 | 23.89 |
| IR worst VDD (mV) | 10.83 | 5.51 | 10.62 |
| IR mean VDD (mV) | 3.45 | 2.06 | 3.92 |
| cell density (%) | 53.0 | 55.6 | 54.2 |
| congestion WL/core | 4.31 | 4.00 | 4.77 |
| GRT wirelength | 7381 | 4545 | 8088 |
| fmax (MHz) | 2058.4 | 1266.4 | 1575.3 |
| setup violations | 46 | 47 | 48 |

#### gcd @ 0.460 ns — reference: ORFS default — area synthesis, util 35, place +0.20 (1/6)

| Metric | `ORFS default — area synthesis, util 35, place +0.20` | `Cell padding +1 site` | `Denser placement, same die — fewer repair buffers` | `Floorplan wider than tall` | `Looser core + wider floorplan` |
|---|---|---|---|---|---|
| WNS (ps) | -37.2 | -40.8 | -38.4 | -38.1 | -40.6 |
| TNS (ns) | -0.595 | -0.415 | -0.354 | -0.345 | -0.960 |
| stdcell area (µm²) | 940.3 | 875.7 | 841.6 | 907.6 | 1054.7 |
| total power (mW) | 3.932 | 3.617 | 3.434 | 3.723 | 4.388 |
| leakage (µW) | 25.64 | 23.49 | 22.03 | 24.36 | 29.63 |
| IR worst VDD (mV) | 6.67 | 5.37 | 6.15 | 2.62 | 6.07 |
| IR mean VDD (mV) | 2.64 | 2.11 | 2.23 | 1.29 | 1.45 |
| cell density (%) | 54.9 | 51.1 | 49.1 | 51.7 | 42.9 |
| congestion WL/core | 4.43 | 4.50 | 4.07 | 4.19 | 3.35 |
| GRT wirelength | 7589 | 7714 | 6971 | 7350 | 8236 |
| fmax (MHz) | 2011.4 | 1997.0 | 2006.4 | 2007.7 | 1997.7 |
| setup violations | 38 | 12 | 11 | 17 | 45 |

#### gcd @ 0.460 ns — reference: ORFS default — area synthesis, util 35, place +0.20 (2/6)

| Metric | `ORFS default — area synthesis, util 35, place +0.20` | `Looser core + cell padding` | `Denser clock buffers` | `ABC delay synthesis on the same physical recipe` | `Netlist DSE rewrite on default die (geometry control)` |
|---|---|---|---|---|---|
| WNS (ps) | -37.2 | -41.3 | -37.2 | -186.9 | -349.5 |
| TNS (ns) | -0.595 | -0.551 | -0.595 | -5.981 | -13.025 |
| stdcell area (µm²) | 940.3 | 922.2 | 940.3 | 963.5 | 635.5 |
| total power (mW) | 3.932 | 3.799 | 3.932 | 5.527 | 2.539 |
| leakage (µW) | 25.64 | 24.97 | 25.64 | 25.02 | 15.15 |
| IR worst VDD (mV) | 6.67 | 3.49 | 6.67 | 8.26 | 4.70 |
| IR mean VDD (mV) | 2.64 | 2.07 | 2.64 | 3.14 | 1.63 |
| cell density (%) | 54.9 | 37.7 | 54.9 | 56.8 | 37.1 |
| congestion WL/core | 4.43 | 3.50 | 4.43 | 4.60 | 2.94 |
| GRT wirelength | 7589 | 8564 | 7589 | 7814 | 5038 |
| fmax (MHz) | 2011.4 | 1995.0 | 2011.4 | 1545.9 | 1235.3 |
| setup violations | 38 | 43 | 38 | 46 | 46 |

#### gcd @ 0.460 ns — reference: ORFS default — area synthesis, util 35, place +0.20 (3/6)

| Metric | `ORFS default — area synthesis, util 35, place +0.20` | `Netlist DSE rewrite (sub_twos_complement) — place/route same as default` | `Sparser placement, util 25` | `Sparser placement, util 35` | `Sparser placement, util 45` |
|---|---|---|---|---|---|
| WNS (ps) | -37.2 | -338.3 | -44.4 | -43.7 | -36.0 |
| TNS (ns) | -0.595 | -13.090 | -0.344 | -0.744 | -0.308 |
| stdcell area (µm²) | 940.3 | 609.9 | 874.3 | 981.3 | 861.8 |
| total power (mW) | 3.932 | 2.428 | 3.631 | 3.995 | 3.481 |
| leakage (µW) | 25.64 | 14.53 | 22.98 | 27.29 | 22.99 |
| IR worst VDD (mV) | 6.67 | 3.33 | 4.95 | 6.76 | 10.05 |
| IR mean VDD (mV) | 2.64 | 1.37 | 2.24 | 2.64 | 2.55 |
| cell density (%) | 54.9 | 53.7 | 35.7 | 57.3 | 63.6 |
| congestion WL/core | 4.43 | 3.93 | 3.07 | 4.47 | 4.89 |
| GRT wirelength | 7589 | 4465 | 7506 | 7660 | 6631 |
| fmax (MHz) | 2011.4 | 1252.7 | 1982.5 | 1985.3 | 2016.2 |
| setup violations | 38 | 46 | 12 | 43 | 11 |

#### gcd @ 0.460 ns — reference: ORFS default — area synthesis, util 35, place +0.20 (4/6)

| Metric | `ORFS default — area synthesis, util 35, place +0.20` | `Util 25` | `Util 45` | `Denser placement, util 25` | `Denser placement, util 45` |
|---|---|---|---|---|---|
| WNS (ps) | -37.2 | -36.3 | -37.7 | -41.8 | -38.1 |
| TNS (ns) | -0.595 | -0.886 | -1.040 | -0.326 | -0.584 |
| stdcell area (µm²) | 940.3 | 952.8 | 956.5 | 861.0 | 860.8 |
| total power (mW) | 3.932 | 3.860 | 4.016 | 3.542 | 3.545 |
| leakage (µW) | 25.64 | 25.89 | 26.05 | 22.56 | 22.79 |
| IR worst VDD (mV) | 6.67 | 4.11 | 5.72 | 4.93 | 6.87 |
| IR mean VDD (mV) | 2.64 | 2.28 | 2.33 | 2.23 | 2.47 |
| cell density (%) | 54.9 | 38.9 | 70.6 | 35.2 | 63.5 |
| congestion WL/core | 4.43 | 3.24 | 5.44 | 2.95 | 5.08 |
| GRT wirelength | 7589 | 7928 | 7378 | 7216 | 6882 |
| fmax (MHz) | 2011.4 | 2015.0 | 2009.3 | 1992.9 | 2007.6 |
| setup violations | 38 | 45 | 45 | 12 | 42 |

#### gcd @ 0.460 ns — reference: ORFS default — area synthesis, util 35, place +0.20 (5/6)

| Metric | `ORFS default — area synthesis, util 35, place +0.20` | `Half TNS repair` | `Setup margin on repair` | `Hierarchical synthesis` | `TPE PLACE_DENSITY_LB_ADDON=0` |
|---|---|---|---|---|---|
| WNS (ps) | -37.2 | -36.6 | -41.1 | -42.1 | -43.4 |
| TNS (ns) | -0.595 | -0.549 | -0.512 | -0.400 | -0.965 |
| stdcell area (µm²) | 940.3 | 894.6 | 963.7 | 889.2 | 945.6 |
| total power (mW) | 3.932 | 3.677 | 3.995 | 9.840 | 3.852 |
| leakage (µW) | 25.64 | 24.00 | 26.41 | 23.83 | 26.11 |
| IR worst VDD (mV) | 6.67 | 7.97 | 12.22 | 17.00 | 5.26 |
| IR mean VDD (mV) | 2.64 | 2.59 | 3.12 | 6.74 | 2.41 |
| cell density (%) | 54.9 | 52.2 | 56.3 | 49.3 | 55.2 |
| congestion WL/core | 4.43 | 4.31 | 4.50 | 4.02 | 4.26 |
| GRT wirelength | 7589 | 7381 | 7700 | 7244 | 7293 |
| fmax (MHz) | 2011.4 | 2013.6 | 1995.7 | 1991.7 | 1986.6 |
| setup violations | 38 | 43 | 26 | 16 | 45 |

#### gcd @ 0.460 ns — reference: ORFS default — area synthesis, util 35, place +0.20 (6/6)

| Metric | `ORFS default — area synthesis, util 35, place +0.20` | `TPE PLACE_DENSITY_LB_ADDON=0` | `TPE PLACE_DENSITY_LB_ADDON=0` | `TPE PLACE_DENSITY_LB_ADDON=0` | `TPE PLACE_DENSITY_LB_ADDON=0` |
|---|---|---|---|---|---|
| WNS (ps) | -37.2 | -41.6 | -39.9 | -44.6 | -47.3 |
| TNS (ns) | -0.595 | -0.451 | -0.999 | -0.855 | -0.842 |
| stdcell area (µm²) | 940.3 | 883.4 | 966.1 | 892.7 | 947.2 |
| total power (mW) | 3.932 | 3.643 | 4.072 | 3.646 | 3.918 |
| leakage (µW) | 25.64 | 23.66 | 26.85 | 24.01 | 25.80 |
| IR worst VDD (mV) | 6.67 | 6.91 | 7.15 | 5.43 | 6.01 |
| IR mean VDD (mV) | 2.64 | 2.59 | 2.72 | 2.17 | 2.24 |
| cell density (%) | 54.9 | 51.6 | 56.4 | 52.1 | 55.3 |
| congestion WL/core | 4.43 | 4.62 | 4.31 | 4.86 | 5.16 |
| GRT wirelength | 7589 | 7920 | 7375 | 8319 | 8837 |
| fmax (MHz) | 2011.4 | 1993.7 | 2000.5 | 1981.9 | 1971.3 |
| setup violations | 38 | 20 | 44 | 45 | 44 |

#### gcd @ 0.550 ns — reference: ORFS default @ 0.55 ns

| Metric | `ORFS default @ 0.55 ns` | `Netlist DSE / rewrite @ 0.55 ns` | `Netlist DSE / rewrite @ 0.55 ns` | `Denser placement at the clock where the default closes (0.55 ns)` |
|---|---|---|---|---|
| WNS (ps) | 13.4 | -251.2 | -109.3 | 13.0 |
| TNS (ns) | 0.000 | -9.079 | -1.409 | 0.000 |
| stdcell area (µm²) | 696.7 | 611.0 | 799.6 | 697.7 |
| total power (mW) | 2.210 | 2.033 | 3.783 | 2.217 |
| leakage (µW) | 16.52 | 14.35 | 19.40 | 16.57 |
| IR worst VDD (mV) | 3.44 | 5.05 | 6.86 | 3.43 |
| IR mean VDD (mV) | 1.40 | 1.46 | 2.38 | 1.41 |
| cell density (%) | 40.7 | 53.8 | 47.1 | 40.7 |
| congestion WL/core | 3.72 | 4.04 | 4.60 | 3.68 |
| GRT wirelength | 6369 | 4594 | 7800 | 6309 |
| fmax (MHz) | 1863.4 | 1248.2 | 1516.9 | 1862.3 |
| setup violations | 0 | 43 | 39 | 0 |

#### gcd @ 0.700 ns — reference: ORFS default @ 0.7 ns

| Metric | `ORFS default @ 0.7 ns` | `Netlist DSE / rewrite @ 0.7 ns` | `Netlist DSE / rewrite @ 0.7 ns` |
|---|---|---|---|
| WNS (ps) | 128.2 | -128.3 | 3.3 |
| TNS (ns) | 0.000 | -3.498 | 0.000 |
| stdcell area (µm²) | 682.6 | 582.8 | 702.2 |
| total power (mW) | 1.705 | 1.534 | 2.486 |
| leakage (µW) | 15.92 | 13.62 | 16.08 |
| IR worst VDD (mV) | 3.13 | 2.45 | 3.55 |
| IR mean VDD (mV) | 1.19 | 0.94 | 1.56 |
| cell density (%) | 39.9 | 51.3 | 41.4 |
| congestion WL/core | 3.71 | 3.62 | 4.22 |
| GRT wirelength | 6346 | 4118 | 7164 |
| fmax (MHz) | 1748.8 | 1207.3 | 1435.3 |
| setup violations | 0 | 39 | 0 |

#### gcd @ 0.900 ns — reference: ORFS default @ 0.9 ns

| Metric | `ORFS default @ 0.9 ns` | `Netlist DSE / rewrite @ 0.9 ns` | `Netlist DSE / rewrite @ 0.9 ns` |
|---|---|---|---|
| WNS (ps) | 289.1 | 4.7 | 121.6 |
| TNS (ns) | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 683.1 | 518.7 | 676.7 |
| total power (mW) | 1.335 | 1.039 | 1.820 |
| leakage (µW) | 15.93 | 11.59 | 15.12 |
| IR worst VDD (mV) | 2.96 | 2.32 | 2.61 |
| IR mean VDD (mV) | 0.96 | 0.65 | 1.14 |
| cell density (%) | 39.9 | 45.6 | 39.9 |
| congestion WL/core | 3.76 | 3.52 | 4.04 |
| GRT wirelength | 6446 | 4004 | 6857 |
| fmax (MHz) | 1636.8 | 1116.9 | 1284.7 |
| setup violations | 0 | 0 | 0 |

#### ibex @ 1.980 ns — reference: ORFS default @ 1.98 ns

| Metric | `ORFS default @ 1.98 ns` | `ABC delay synthesis @ 1.98 ns` |
|---|---|---|
| WNS (ps) | -23.1 | -61.1 |
| TNS (ns) | -0.033 | -7.110 |
| stdcell area (µm²) | 30879.4 | 33052.1 |
| total power (mW) | 120.508 | 117.855 |
| leakage (µW) | 694.93 | 727.21 |
| IR worst VDD (mV) | 95.41 | 65.97 |
| IR mean VDD (mV) | 14.45 | 11.31 |
| cell density (%) | 50.1 | 56.0 |
| congestion WL/core | 7.16 | 7.34 |
| GRT wirelength | 441009 | 432835 |
| fmax (MHz) | 499.2 | 489.9 |
| setup violations | 4 | 301 |

#### ibex @ 2.200 ns — reference: ORFS default — area synthesis, util 50, place +0.20 (1/5)

| Metric | `ORFS default — area synthesis, util 50, place +0.20` | `Cell padding +1 site` | `Sparser placement, same die` | `Denser placement, same die` | `Setup margin on repair` |
|---|---|---|---|---|---|
| WNS (ps) | 22.4 | 21.8 | 36.2 | 39.9 | 63.5 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 30735.2 | 30751.2 | 30748.3 | 30711.0 | 30743.7 |
| total power (mW) | 107.868 | 108.247 | 107.922 | 107.344 | 107.966 |
| leakage (µW) | 688.21 | 688.60 | 688.40 | 687.50 | 688.50 |
| IR worst VDD (mV) | 123.77 | 78.68 | 125.04 | 116.96 | 123.77 |
| IR mean VDD (mV) | 13.11 | 12.14 | 12.76 | 13.41 | 13.12 |
| cell density (%) | 49.9 | 49.9 | 49.9 | 49.8 | 49.9 |
| congestion WL/core | 7.12 | 7.60 | 7.22 | 7.02 | 7.12 |
| GRT wirelength | 438851 | 468115 | 445041 | 432786 | 438976 |
| fmax (MHz) | 459.2 | 459.1 | 462.2 | 462.9 | 468.1 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### ibex @ 2.200 ns — reference: ORFS default — area synthesis, util 50, place +0.20 (2/5)

| Metric | `ORFS default — area synthesis, util 50, place +0.20` | `TPE PLACE_DENSITY_LB_ADDON=0` | `TPE PLACE_DENSITY_LB_ADDON=0` | `TPE PLACE_DENSITY_LB_ADDON=0` | `TPE PLACE_DENSITY_LB_ADDON=0` |
|---|---|---|---|---|---|
| WNS (ps) | 22.4 | 19.5 | 64.8 | 54.9 | 34.2 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 30735.2 | 32082.8 | 30753.9 | 32098.0 | 30789.8 |
| total power (mW) | 107.868 | 114.968 | 107.963 | 113.862 | 108.212 |
| leakage (µW) | 688.21 | 743.81 | 688.57 | 743.86 | 689.97 |
| IR worst VDD (mV) | 123.77 | 76.58 | 125.35 | 82.98 | 89.94 |
| IR mean VDD (mV) | 13.11 | 12.70 | 12.76 | 13.24 | 12.38 |
| cell density (%) | 49.9 | 52.1 | 49.9 | 52.1 | 50.0 |
| congestion WL/core | 7.12 | 9.36 | 7.22 | 8.86 | 7.60 |
| GRT wirelength | 438851 | 576791 | 445218 | 545800 | 468334 |
| fmax (MHz) | 459.2 | 458.6 | 468.3 | 466.2 | 461.7 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### ibex @ 2.200 ns — reference: ORFS default — area synthesis, util 50, place +0.20 (3/5)

| Metric | `ORFS default — area synthesis, util 50, place +0.20` | `TPE PLACE_DENSITY_LB_ADDON=0` | `TPE PLACE_DENSITY_LB_ADDON=0` | `ABC delay synthesis @ 2.2 ns` | `Floorplan wider than tall` |
|---|---|---|---|---|---|
| WNS (ps) | 22.4 | 48.7 | 57.3 | 20.4 | 24.9 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 30735.2 | 30774.1 | 30791.4 | 30575.4 | 30796.4 |
| total power (mW) | 107.868 | 108.699 | 108.756 | 90.815 | 109.442 |
| leakage (µW) | 688.21 | 689.47 | 690.25 | 640.35 | 690.62 |
| IR worst VDD (mV) | 123.77 | 85.67 | 78.31 | 49.13 | 85.83 |
| IR mean VDD (mV) | 13.11 | 12.09 | 12.28 | 8.77 | 10.49 |
| cell density (%) | 49.9 | 49.9 | 50.0 | 51.8 | 49.9 |
| congestion WL/core | 7.12 | 7.62 | 7.64 | 7.16 | 7.62 |
| GRT wirelength | 438851 | 469853 | 470677 | 422381 | 470857 |
| fmax (MHz) | 459.2 | 464.8 | 466.7 | 458.8 | 459.7 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### ibex @ 2.200 ns — reference: ORFS default — area synthesis, util 50, place +0.20 (4/5)

| Metric | `ORFS default — area synthesis, util 50, place +0.20` | `Denser clock buffers` | `Looser core — larger die, longer wires` | `Tighter core — smaller die, shorter wires` | `Half TNS repair` |
|---|---|---|---|---|---|
| WNS (ps) | 22.4 | 26.5 | 16.1 | 42.3 | 22.4 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 30735.2 | 30740.6 | 30776.7 | 30686.0 | 30735.2 |
| total power (mW) | 107.868 | 107.785 | 108.105 | 107.499 | 107.868 |
| leakage (µW) | 688.21 | 688.33 | 688.77 | 688.06 | 688.21 |
| IR worst VDD (mV) | 123.77 | 123.79 | 71.23 | 86.24 | 123.77 |
| IR mean VDD (mV) | 13.11 | 13.09 | 8.81 | 12.65 | 13.11 |
| cell density (%) | 49.9 | 49.9 | 39.9 | 59.6 | 49.9 |
| congestion WL/core | 7.12 | 7.11 | 5.97 | 8.17 | 7.12 |
| GRT wirelength | 438851 | 438255 | 460215 | 420930 | 438851 |
| fmax (MHz) | 459.2 | 460.1 | 457.9 | 463.5 | 459.2 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### ibex @ 2.200 ns — reference: ORFS default — area synthesis, util 50, place +0.20 (5/5)

| Metric | `ORFS default — area synthesis, util 50, place +0.20` | `Hierarchical synthesis` |
|---|---|---|
| WNS (ps) | 22.4 | 30.9 |
| TNS (ns) | 0.000 | 0.000 |
| stdcell area (µm²) | 30735.2 | 30728.3 |
| total power (mW) | 107.868 | 108.751 |
| leakage (µW) | 688.21 | 685.46 |
| IR worst VDD (mV) | 123.77 | 145.53 |
| IR mean VDD (mV) | 13.11 | 14.34 |
| cell density (%) | 49.9 | 49.7 |
| congestion WL/core | 7.12 | 7.04 |
| GRT wirelength | 438851 | 434867 |
| fmax (MHz) | 459.2 | 461.0 |
| setup violations | 0 | 0 |

#### ibex @ 2.750 ns — reference: ORFS default @ 2.75 ns

| Metric | `ORFS default @ 2.75 ns` | `ABC delay synthesis @ 2.75 ns` |
|---|---|---|
| WNS (ps) | 285.0 | 166.3 |
| TNS (ns) | 0.000 | 0.000 |
| stdcell area (µm²) | 30707.3 | 30065.2 |
| total power (mW) | 86.457 | 70.620 |
| leakage (µW) | 685.80 | 621.71 |
| IR worst VDD (mV) | 76.31 | 26.41 |
| IR mean VDD (mV) | 10.48 | 6.77 |
| cell density (%) | 49.8 | 51.0 |
| congestion WL/core | 7.14 | 7.08 |
| GRT wirelength | 440282 | 417747 |
| fmax (MHz) | 405.7 | 387.0 |
| setup violations | 0 | 0 |

#### ibex @ 3.520 ns — reference: ORFS default @ 3.52 ns

| Metric | `ORFS default @ 3.52 ns` | `ABC delay synthesis @ 3.52 ns` |
|---|---|---|
| WNS (ps) | 806.7 | 597.2 |
| TNS (ns) | 0.000 | 0.000 |
| stdcell area (µm²) | 30683.1 | 30033.5 |
| total power (mW) | 67.642 | 55.188 |
| leakage (µW) | 684.74 | 620.45 |
| IR worst VDD (mV) | 62.18 | 30.35 |
| IR mean VDD (mV) | 8.18 | 5.33 |
| cell density (%) | 49.8 | 50.9 |
| congestion WL/core | 7.15 | 7.11 |
| GRT wirelength | 440701 | 419434 |
| fmax (MHz) | 368.6 | 342.1 |
| setup violations | 0 | 0 |

#### spi @ 1.000 ns — reference: ORFS default @ 1 ns (1/4)

| Metric | `ORFS default @ 1 ns` | `ABC delay synthesis @ 1 ns` | `Floorplan wider than tall` | `Cell padding +1 site` | `Looser core` |
|---|---|---|---|---|---|
| WNS (ps) | 612.2 | 600.8 | 611.7 | 612.5 | 611.7 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 267.6 | 265.7 | 275.6 | 267.6 | 272.9 |
| total power (mW) | 0.301 | 0.313 | 0.304 | 0.302 | 0.300 |
| leakage (µW) | 5.32 | 5.80 | 5.32 | 5.32 | 5.32 |
| IR worst VDD (mV) | 0.98 | 1.06 | 1.77 | 0.93 | 1.15 |
| IR mean VDD (mV) | 0.53 | 0.62 | 0.61 | 0.52 | 0.54 |
| cell density (%) | 9.4 | 9.2 | 9.9 | 9.4 | 6.0 |
| congestion WL/core | 0.79 | 0.65 | 0.81 | 0.83 | 0.51 |
| GRT wirelength | 2257 | 1889 | 2268 | 2368 | 2308 |
| fmax (MHz) | 2578.9 | 2505.0 | 2575.6 | 2580.3 | 2575.4 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### spi @ 1.000 ns — reference: ORFS default @ 1 ns (2/4)

| Metric | `ORFS default @ 1 ns` | `Tighter core` | `Denser clock buffers` | `Sparser clock buffers` | `Hold margin on repair` |
|---|---|---|---|---|---|
| WNS (ps) | 612.2 | 615.5 | 612.2 | 612.2 | 612.2 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 267.6 | 260.7 | 267.6 | 267.6 | 267.6 |
| total power (mW) | 0.301 | 0.298 | 0.301 | 0.301 | 0.301 |
| leakage (µW) | 5.32 | 5.32 | 5.32 | 5.32 | 5.32 |
| IR worst VDD (mV) | 0.98 | 2.09 | 0.98 | 0.98 | 0.98 |
| IR mean VDD (mV) | 0.53 | 1.10 | 0.53 | 0.53 | 0.53 |
| cell density (%) | 9.4 | 21.0 | 9.4 | 9.4 | 9.4 |
| congestion WL/core | 0.79 | 1.49 | 0.79 | 0.79 | 0.79 |
| GRT wirelength | 2257 | 1855 | 2257 | 2257 | 2257 |
| fmax (MHz) | 2578.9 | 2600.5 | 2578.9 | 2578.9 | 2578.9 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### spi @ 1.000 ns — reference: ORFS default @ 1 ns (3/4)

| Metric | `ORFS default @ 1 ns` | `Denser placement` | `Placement without timing-driven` | `Sparser placement` | `Half TNS repair` |
|---|---|---|---|---|---|
| WNS (ps) | 612.2 | 610.7 | 611.0 | 613.3 | 612.2 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 267.6 | 268.1 | 272.4 | 267.6 | 267.6 |
| total power (mW) | 0.301 | 0.307 | 0.303 | 0.303 | 0.301 |
| leakage (µW) | 5.32 | 5.35 | 5.52 | 5.32 | 5.32 |
| IR worst VDD (mV) | 0.98 | 1.07 | 1.44 | 1.04 | 0.98 |
| IR mean VDD (mV) | 0.53 | 0.56 | 0.57 | 0.50 | 0.53 |
| cell density (%) | 9.4 | 9.4 | 9.6 | 9.4 | 9.4 |
| congestion WL/core | 0.79 | 0.78 | 0.75 | 0.82 | 0.79 |
| GRT wirelength | 2257 | 2205 | 2140 | 2317 | 2257 |
| fmax (MHz) | 2578.9 | 2569.0 | 2570.8 | 2586.1 | 2578.9 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### spi @ 1.000 ns — reference: ORFS default @ 1 ns (4/4)

| Metric | `ORFS default @ 1 ns` | `Setup margin on repair` | `No TNS repair` | `Hierarchical synthesis` |
|---|---|---|---|---|
| WNS (ps) | 612.2 | 612.2 | 612.2 | 612.2 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 267.6 | 267.6 | 267.6 | 267.6 |
| total power (mW) | 0.301 | 0.301 | 0.301 | 0.301 |
| leakage (µW) | 5.32 | 5.32 | 5.32 | 5.32 |
| IR worst VDD (mV) | 0.98 | 0.98 | 0.98 | 0.98 |
| IR mean VDD (mV) | 0.53 | 0.53 | 0.53 | 0.53 |
| cell density (%) | 9.4 | 9.4 | 9.4 | 9.4 |
| congestion WL/core | 0.79 | 0.79 | 0.79 | 0.79 |
| GRT wirelength | 2257 | 2257 | 2257 | 2257 |
| fmax (MHz) | 2578.9 | 2578.9 | 2578.9 | 2578.9 |
| setup violations | 0 | 0 | 0 | 0 |


## synth_method

**Synthesis method (new challengers):** ABC `area` — Q1–Q4: 4 §5 wins on official netlist (ABC area) + physical knobs. ABC delay and DSE rewrites never won §5 (H1: proxy inverts).

```json
{
  "abc": "area",
  "ABC_AREA": 1,
  "ABC_SPEED": 0,
  "apply_to": "new challenger variants only",
  "never_apply_to": [
    "role=base",
    "FLOW_VARIANT=flowlab",
    "FLOW_VARIANT=learn"
  ],
  "avoid_as_default": [
    "abc_speed",
    "dse_rtl_rewrite"
  ],
  "why": "Q1\u2013Q4: 4 \u00a75 wins on official netlist (ABC area) + physical knobs. ABC delay and DSE rewrites never won \u00a75 (H1: proxy inverts).",
  "next_synth_axes": [
    "SYNTH_HIERARCHICAL",
    "TNS_END_PERCENT after map"
  ]
}
```

