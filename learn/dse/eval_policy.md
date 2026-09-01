# Next-iteration eval vs frozen I1–I5

Plan sha: `cf02fb91ed5b757ba057354b2f53cb18a75586e7cf7ccf895369767436f76c98`
Experiments: 88 (79 done)

I1–I5 bars stay frozen (historical). Product win is `dse.win_rule` (slack + area/power/IR).
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
      "n": 9,
      "mean_ns": 0.01746310111111111,
      "std_ns": 0.0233075819846737
    },
    "dynamic_node": {
      "n": 1,
      "mean_ns": -0.24974000000000007,
      "std_ns": 0.0
    },
    "gcd": {
      "n": 31,
      "mean_ns": -0.051335913225806454,
      "std_ns": 0.016897535892978866
    },
    "ibex": {
      "n": 18,
      "mean_ns": -0.19386905000000001,
      "std_ns": 0.09067479775393364
    },
    "spi": {
      "n": 12,
      "mean_ns": 0.028822666666666635,
      "std_ns": 0.004047935171357746
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
      "pred_ns": -0.04045129045454546,
      "actual_ns": -0.0444042,
      "err_ns": -0.00395290954545454,
      "band_ns": 0.039967437012810914,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d15u35",
      "design": "gcd",
      "pred_ns": -0.038470790454545455,
      "actual_ns": -0.0436955,
      "err_ns": -0.005224709545454544,
      "band_ns": 0.039967437012810914,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d15u45",
      "design": "gcd",
      "pred_ns": -0.035448990454545456,
      "actual_ns": -0.0359792,
      "err_ns": -0.0005302095454545463,
      "band_ns": 0.039967437012810914,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d20u25",
      "design": "gcd",
      "pred_ns": -0.040659970454545453,
      "actual_ns": -0.0362789,
      "err_ns": 0.004381070454545451,
      "band_ns": 0.039967437012810914,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d20u45",
      "design": "gcd",
      "pred_ns": -0.035951090454545455,
      "actual_ns": -0.0376739,
      "err_ns": -0.0017228095454545483,
      "band_ns": 0.039967437012810914,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d25u25",
      "design": "gcd",
      "pred_ns": -0.038643290454545454,
      "actual_ns": -0.0417844,
      "err_ns": -0.0031411095454545457,
      "band_ns": 0.039967437012810914,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d25u35",
      "design": "gcd",
      "pred_ns": -0.03696059045454546,
      "actual_ns": -0.0384003,
      "err_ns": -0.00143970954545454,
      "band_ns": 0.039967437012810914,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d25u45",
      "design": "gcd",
      "pred_ns": -0.035967790454545456,
      "actual_ns": -0.0381096,
      "err_ns": -0.002141809545454544,
      "band_ns": 0.039967437012810914,
      "inside": true
    },
    {
      "variant": "camp_ibex_q1_d15u50",
      "design": "ibex",
      "pred_ns": 0.04459407857142858,
      "actual_ns": 0.0362255,
      "err_ns": -0.00836857857142858,
      "band_ns": 0.2038724872748149,
      "inside": true
    },
    {
      "variant": "camp_ibex_q1_d25u50",
      "design": "ibex",
      "pred_ns": 0.07354107857142861,
      "actual_ns": 0.039892,
      "err_ns": -0.03364907857142861,
      "band_ns": 0.2038724872748149,
      "inside": true
    },
    {
      "variant": "camp_ibex_q1_d20u40",
      "design": "ibex",
      "pred_ns": 0.06500907857142857,
      "actual_ns": 0.0161107,
      "err_ns": -0.04889837857142857,
      "band_ns": 0.2038724872748149,
      "inside": true
    },
    {
      "variant": "camp_ibex_q1_d20u60",
      "design": "ibex",
      "pred_ns": 0.08863207857142857,
      "actual_ns": 0.0423498,
      "err_ns": -0.046282278571428574,
      "band_ns": 0.2038724872748149,
      "inside": true
    },
    {
      "variant": "camp_gcd_q4_d25u35_c055",
      "design": "gcd",
      "pred_ns": 0.023841109545454542,
      "actual_ns": 0.0130203,
      "err_ns": -0.010820809545454542,
      "band_ns": 0.039967437012810914,
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

**Verdict:** I5 supported (place Spearman 0.905 ≥ 0.6; F1 Spearman 0.866)

```json
{
  "n_place_pairs": 71,
  "n_f1_pairs": 3,
  "place_spearman": 0.9050570869915824,
  "f1_spearman": 0.8660254037844387,
  "bar": 0.6,
  "min_n": 8,
  "supported": true,
  "verdict": "I5 supported (place Spearman 0.905 \u2265 0.6; F1 Spearman 0.866)"
}
```

## gate_diagnostics

**Verdict:** gate FP=37 FN=1 precision=0.159 (8 product-wins among 59 challengers)

```json
{
  "n_challengers": 59,
  "n_promoted": 44,
  "n_real_wins": 8,
  "tp": 7,
  "fp": 37,
  "fn": 1,
  "tn": 14,
  "precision": 0.1590909090909091,
  "recall": 0.875,
  "verdict": "gate FP=37 FN=1 precision=0.159 (8 product-wins among 59 challengers)"
}
```

## QoR_vs_base

**Verdict:** QoR vs base: 12 reference slots, 59 challengers, 59 with IR, 59 with GRT WL, 16 product wins

I nomi in tabella dicono **cosa fa** la ricetta e (nella § Ricette) qual è il vantaggio o lo svantaggio. L'id `camp_*` resta solo il path ORFS.

IR worst = drop VDD massimo. **IR mean** = drop medio sul die (VDD_nom − V_avg; la chiave ORFS `drop__average` su VDD è in realtà una tensione). **Density** = utilizzazione stdcell sul core. **Congestion** = GRT WL / area core (i JSON non hanno overflow fraction; `congestion_*_s` sono runtime).

Vittoria prodotto: timing ±5 ps e (area o potenza o IR −10%), senza peggiorare nessuno del 10%. Oppure timing +5 ps senza peggiorare area/potenza/IR. Vedi `product.md`.

### Ricette (cosa fanno, che vantaggio hanno)

| Ricetta | Cosa fa | Vantaggio / esito |
|---|---|---|
| ORFS default @ 0.82 ns (`camp_aes_base`) | Ricetta ufficiale del design: sintesi e knob fisici di config. | Reference dello slot. I delta si leggono contro questa riga. |
| ORFS default @ 6 ns (`camp_dynamic_node_base`) | Ricetta ufficiale del design: sintesi e knob fisici di config. | Reference dello slot. I delta si leggono contro questa riga. |
| ORFS default @ 0.4 ns (`camp_gcd_clk040_a`) | Ricetta ufficiale del design: sintesi e knob fisici di config. | Reference dello slot. I delta si leggono contro questa riga. |
| ORFS default — sintesi area, util 35, place +0.20 (`camp_gcd_base`) | Ricetta ufficiale gcd: ABC area, floorplan util 35%, GPL density addon 0.20, TNS repair 100%. | Reference. WNS −37 ps, area 940 µm², IR worst 6.67 mV / mean ~2.6 mV. |
| ORFS default @ 0.55 ns (`camp_gcd_clk055_a`) | Ricetta ufficiale del design: sintesi e knob fisici di config. | Reference dello slot. I delta si leggono contro questa riga. |
| ORFS default @ 0.7 ns (`camp_gcd_clk070_a`) | Ricetta ufficiale del design: sintesi e knob fisici di config. | Reference dello slot. I delta si leggono contro questa riga. |
| ORFS default @ 0.9 ns (`camp_gcd_clk090_a`) | Ricetta ufficiale del design: sintesi e knob fisici di config. | Reference dello slot. I delta si leggono contro questa riga. |
| ORFS default @ 1.98 ns (`camp_ibex_clk198_a`) | Ricetta ufficiale del design: sintesi e knob fisici di config. | Reference dello slot. I delta si leggono contro questa riga. |
| ORFS default — sintesi area, util 50, place +0.20 (`camp_ibex_base`) | Ricetta ufficiale ibex: ABC area, util 50%, density addon 0.20. | Reference. WNS +22 ps, power 108 mW, IR worst 124 mV. |
| ORFS default @ 2.75 ns (`camp_ibex_clk275_a`) | Ricetta ufficiale del design: sintesi e knob fisici di config. | Reference dello slot. I delta si leggono contro questa riga. |
| ORFS default @ 3.52 ns (`camp_ibex_clk352_a`) | Ricetta ufficiale del design: sintesi e knob fisici di config. | Reference dello slot. I delta si leggono contro questa riga. |
| ORFS default @ 1 ns (`camp_spi_base`) | Ricetta ufficiale del design: sintesi e knob fisici di config. | Reference dello slot. I delta si leggono contro questa riga. |
| Netlist DSE rewrite (sub_twos_complement) — place/route uguale al default (`camp_gcd_dse_small`) | Cambia solo il Verilog mappato. Floorplan/place/CTS = default. | Lose: WNS −338 vs −37 ps. Il rewrite di sintesi non è un win di prodotto. |
| Sintesi ABC delay sulla stessa ricetta fisica (`camp_gcd_dse_fast`) | ABC speed, util/density del default. | Lose: WNS −187 ps, power +41%. ABC delay non batte ABC area + knob fisici. |
| Netlist DSE rewrite sul die del default (controllo geometria) (`camp_gcd_dse_fixedb`) | Stesso Verilog DSE di B, DIE_AREA bloccata su A. | Lose: ancora ~−350 ps. Non è un problema di die. |
| Netlist DSE / rewrite @ 0.4 ns (`camp_gcd_clk040_b`) | Cambia la netlist. I knob fisici restano quelli del default. | In campagna: proxy invertito (H1), nessun win §5. |
| Netlist DSE / rewrite @ 0.4 ns (`camp_gcd_clk040_c`) | Cambia la netlist. I knob fisici restano quelli del default. | In campagna: proxy invertito (H1), nessun win §5. |
| Netlist DSE / rewrite @ 0.55 ns (`camp_gcd_clk055_b`) | Cambia la netlist. I knob fisici restano quelli del default. | In campagna: proxy invertito (H1), nessun win §5. |
| Netlist DSE / rewrite @ 0.55 ns (`camp_gcd_clk055_c`) | Cambia la netlist. I knob fisici restano quelli del default. | In campagna: proxy invertito (H1), nessun win §5. |
| Netlist DSE / rewrite @ 0.7 ns (`camp_gcd_clk070_b`) | Cambia la netlist. I knob fisici restano quelli del default. | In campagna: proxy invertito (H1), nessun win §5. |
| Netlist DSE / rewrite @ 0.7 ns (`camp_gcd_clk070_c`) | Cambia la netlist. I knob fisici restano quelli del default. | In campagna: proxy invertito (H1), nessun win §5. |
| Netlist DSE / rewrite @ 0.9 ns (`camp_gcd_clk090_b`) | Cambia la netlist. I knob fisici restano quelli del default. | In campagna: proxy invertito (H1), nessun win §5. |
| Netlist DSE / rewrite @ 0.9 ns (`camp_gcd_clk090_c`) | Cambia la netlist. I knob fisici restano quelli del default. | In campagna: proxy invertito (H1), nessun win §5. |
| Sintesi ABC delay @ 1 ns (`camp_spi_abcspeed`) | Script ABC speed, stesso floorplan/place del default. | In campagna: nessun win §5. Non è il metodo di sintesi da usare di default. |
| Sintesi ABC delay @ 2.2 ns (`camp_ibex_abcspeed`) | Script ABC speed, stesso floorplan/place del default. | In campagna: nessun win §5. Non è il metodo di sintesi da usare di default. |
| Sintesi ABC delay @ 1.98 ns (`camp_ibex_clk198_s`) | Script ABC speed, stesso floorplan/place del default. | In campagna: nessun win §5. Non è il metodo di sintesi da usare di default. |
| Sintesi ABC delay @ 2.75 ns (`camp_ibex_clk275_s`) | Script ABC speed, stesso floorplan/place del default. | In campagna: nessun win §5. Non è il metodo di sintesi da usare di default. |
| Sintesi ABC delay @ 3.52 ns (`camp_ibex_clk352_s`) | Script ABC speed, stesso floorplan/place del default. | In campagna: nessun win §5. Non è il metodo di sintesi da usare di default. |
| Place più sparso, util 25 (`camp_gcd_q1_d15u25`) | Stessa netlist ORFS. PLACE_DENSITY_LB_ADDON 0.2→0.15; CORE_UTILIZATION=25. | Knob fisici, non un nuovo Verilog. |
| Place più sparso, util 35 (`camp_gcd_q1_d15u35`) | Stessa netlist ORFS. PLACE_DENSITY_LB_ADDON 0.2→0.15; CORE_UTILIZATION=35. | Knob fisici, non un nuovo Verilog. |
| Place più sparso, util 45 (`camp_gcd_q1_d15u45`) | Stessa netlist ORFS. PLACE_DENSITY_LB_ADDON 0.2→0.15; CORE_UTILIZATION=45. | Knob fisici, non un nuovo Verilog. |
| Util 25 (`camp_gcd_q1_d20u25`) | Stessa netlist ORFS. CORE_UTILIZATION=25. | Knob fisici, non un nuovo Verilog. |
| Util 45 (`camp_gcd_q1_d20u45`) | Stessa netlist ORFS. CORE_UTILIZATION=45. | Knob fisici, non un nuovo Verilog. |
| Place più denso, util 25 (`camp_gcd_q1_d25u25`) | Stessa netlist ORFS. PLACE_DENSITY_LB_ADDON 0.2→0.25; CORE_UTILIZATION=25. | Knob fisici, non un nuovo Verilog. |
| Place più denso, stesso die — meno buffer di repair (`camp_gcd_q1_d25u35`) | Stessa netlist e stesso util 35. Solo PLACE_DENSITY_LB_ADDON 0.20→0.25. | §5 win: area −10.5%, power −13%, leak −14%, IR −8%, WL −8%. |
| Place più denso, util 45 (`camp_gcd_q1_d25u45`) | Stessa netlist ORFS. PLACE_DENSITY_LB_ADDON 0.2→0.25; CORE_UTILIZATION=45. | Knob fisici, non un nuovo Verilog. |
| Place più sparso, stesso die (`camp_ibex_q1_d15u50`) | Stessa netlist e util 50. PLACE_DENSITY_LB_ADDON 0.20→0.15. | §5 win slack (+36 vs +22 ps). Area/power ~iso. |
| Place più denso, stesso die (`camp_ibex_q1_d25u50`) | Stessa netlist e util 50. PLACE_DENSITY_LB_ADDON 0.20→0.25. | §5 win slack (+40 vs +22 ps). Area/power ~iso. |
| Core più largo — die più grande, fili più lunghi (`camp_ibex_q1_d20u40`) | Stessa netlist. CORE_UTILIZATION 50→40. | Lose: WNS −6 ps, WL +5%. Controesempio del core stretto. |
| Core più stretto — die più piccolo, fili più corti (`camp_ibex_q1_d20u60`) | Stessa netlist e stesso density addon 0.20. CORE_UTILIZATION 50→60. | §5 win: WNS +42 vs +22 ps; IR −30%; WL −4%; power ~iso. |
| Place più denso al clock dove il default chiude (0.55 ns) (`camp_gcd_q4_d25u35_c055`) | Stessi knob del win gcd, SDC 0.55 ns (regime area). | I4 falsa: chiude come il default, area 698 vs 697. Il win non transferisce di clock. |
| Place più denso (`camp_spi_place_denser`) | Stessa netlist ufficiale. PLACE_DENSITY_LB_ADDON 0.20→0.25. Util resta il default di config (8). | Transfer miss su spi: WNS −1.5 ps (tie), area +0.2%, stessi 22 buffer. Il lever gcd non transferisce su un die già chiuso e sparso. |
| Repair TNS a metà (`camp_spi_repair_half_tns`) | Stessa netlist ufficiale. TNS_END_PERCENT 100→50. Util resta 8. | Su spi non cambia nulla: era già in orario. |
| Place più sparso (`camp_spi_place_sparser`) | Celle un po’ più larghe (density addon 0.20→0.15). | Su spi quasi uguale al default. Fili un po’ più lunghi. |
| Padding celle +1 site (`camp_spi_cell_pad_plus`) | Un site di spazio extra tra le celle. | Su spi quasi uguale. Fili un po’ più lunghi. |
| Margine di setup sul repair (`camp_spi_repair_setup_margin`) | Chiede 50 ps in più al repair di timing. | Su spi non cambia nulla: era già in orario. |
| Buffer di clock più fitti (`camp_spi_cts_closer_bufs`) | Buffer di clock ogni 80 µm. | Su spi non cambia nulla (albero di clock già piccolo). |
| Floorplan più largo che alto (`camp_spi_aspect_wide`) | Rettangolo 2:1 invece di un quadrato. | Su spi un po’ peggio: più celle, area +3%, IR peggiore. |
| Core più stretto (`camp_spi_core_tighter`) | Util 8→18: die più piccolo. | Su spi: area −2.6%, fili −18%, slack +3 ps. IR peggiore. Non basta per un win. |
| Core più largo (`camp_spi_core_looser`) | Util 8→5: die più grande (minimo 5). | Su spi: die più grande, area +2%, slack quasi uguale. |
| Sintesi gerarchica (`camp_spi_synth_hier`) | Yosys senza flatten prima di ABC. | Su spi identico al default (il Verilog è già piatto). |
| Margine di setup sul repair (`camp_gcd_repair_setup_margin`) | Chiede 50 ps in più al repair di timing. | Su gcd: slack un filo peggio, IR molto peggio. Perde. |
| Floorplan più largo che alto (`camp_gcd_aspect_wide`) | Rettangolo 2:1 invece di un quadrato. | Su gcd: slack uguale, IR −61%. Win su IR. |
| Place più denso (`camp_aes_place_denser`) | Stessa netlist ufficiale. Density addon +0.05. Die bloccato dal config. | Su aes quasi uguale al default (slack −8.6 vs −8.9 ps). |
| Margine di setup sul repair (`camp_aes_repair_setup_margin`) | Chiede 50 ps in più al repair di timing. Stessa netlist, die bloccato. | Su aes: primo a chiudere (+17 vs −9 ps). IR −12%. Area/potenza +3%. Win. |
| Sintesi gerarchica (`camp_gcd_synth_hier`) | Yosys senza flatten prima di ABC. | Su gcd: perde. Slack −5 ps, potenza +150%, IR +155%. Non usarla qui. |
| Padding celle +1 site (`camp_gcd_cell_pad_plus`) | Un site di spazio extra tra le celle. Stessa netlist, stesso die. | Su gcd: win. IR −19%, area −7%, potenza −8%. Slack −3.6 ps (dentro 5 ps). |
| Repair TNS a metà (`camp_gcd_repair_half_tns`) | TNS_END_PERCENT 100→50: ripara meno path violati. | Su gcd: perde. IR +19%. Slack e area quasi uguali. |
| Buffer di clock più fitti (`camp_gcd_cts_closer_bufs`) | Buffer di clock ogni 80 µm. | Su gcd: identico al default. No-op. |
| Sintesi gerarchica (`camp_ibex_synth_hier`) | Yosys senza flatten prima di ABC. | Su ibex: perde. Slack +8 ps, ma IR +18%. |
| Floorplan più largo che alto (`camp_ibex_aspect_wide`) | Rettangolo 2:1 invece di un quadrato. | Su ibex: win. IR −31%. Slack +2.5 ps. |
| Padding celle +1 site (`camp_ibex_cell_pad_plus`) | Un site di spazio extra tra le celle. Stessa netlist, stesso die. | Su ibex: win. IR −36%. Slack e area ~iso. |
| Repair TNS a metà (`camp_ibex_repair_half_tns`) | TNS_END_PERCENT 100→50: ripara meno path violati. | Su ibex: identico al default (già in orario). No-op. |
| Margine di setup sul repair (`camp_ibex_repair_setup_margin`) | Chiede 50 ps in più al repair di timing. | Su ibex: win. Slack +41 ps. Area/potenza/IR ~iso. |
| Buffer di clock più fitti (`camp_ibex_cts_closer_bufs`) | Buffer di clock ogni 80 µm. | Su ibex: slack +4 ps. Non basta per un win. Pareggio. |
| Sintesi ABC delay (`camp_aes_synth_delay`) | Yosys + script ABC speed. Stesso RTL, altro mapping. | Su aes: identico al default (il config ufficiale è già ABC speed). No-op. |
| Sintesi gerarchica (`camp_aes_synth_hier`) | Yosys senza flatten prima di ABC. | Su aes: perde. IR +16%. Slack ~iso. |
| Place più sparso (`camp_aes_place_sparser`) | Density addon −0.05. Die bloccato dal config. | Su aes: win. IR −13%. Slack −0.9 ps (dentro 5 ps). |
| Padding celle +1 site (`camp_aes_cell_pad_plus`) | Un site di spazio extra tra le celle. Die bloccato. | Su aes: perde. Slack −21 ps. IR meglio non basta. |
| Repair TNS a metà (`camp_aes_repair_half_tns`) | TNS_END_PERCENT 100→50. Die bloccato. | Su aes: perde. Slack −16 ps. |
| Buffer di clock più fitti (`camp_aes_cts_closer_bufs`) | Buffer di clock ogni 80 µm. Die bloccato. | Su aes: win. Slack +8 ps. Area/potenza/IR ~iso. |

### Reference flow (absolute, one row per design@clock)

| Design | Clock ns | Ricetta | WNS ps | TNS ns | Area µm² | Power mW | Leak µW | IR worst | IR mean | Density % | Cong. WL/core | GRT WL | fmax MHz | setup viol |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aes | 0.820 | ORFS default @ 0.82 ns (`camp_aes_base`) | -8.9 | -0.024 | 19921.3 | 315.081 | 493.36 | 81.28 | 38.89 | 37.7 | 6.68 | 352701 | 1206.4 | 5 |
| dynamic_node | 6.000 | ORFS default @ 6 ns (`camp_dynamic_node_base`) | 3353.8 | 0.000 | 22540.0 | 8.765 | 429.78 | 1.78 | 1.03 | 43.6 | 5.01 | 259047 | 377.9 | 0 |
| gcd | 0.400 | ORFS default @ 0.4 ns (`camp_gcd_clk040_a`) | -85.8 | -2.479 | 908.4 | 4.213 | 23.93 | 10.83 | 3.45 | 53.0 | 4.31 | 7381 | 2058.4 | 46 |
| gcd | 0.460 | ORFS default — sintesi area, util 35, place +0.20 (`camp_gcd_base`) | -37.2 | -0.595 | 940.3 | 3.932 | 25.64 | 6.67 | 2.64 | 54.9 | 4.43 | 7589 | 2011.4 | 38 |
| gcd | 0.550 | ORFS default @ 0.55 ns (`camp_gcd_clk055_a`) | 13.4 | 0.000 | 696.7 | 2.210 | 16.52 | 3.44 | 1.40 | 40.7 | 3.72 | 6369 | 1863.4 | 0 |
| gcd | 0.700 | ORFS default @ 0.7 ns (`camp_gcd_clk070_a`) | 128.2 | 0.000 | 682.6 | 1.705 | 15.92 | 3.13 | 1.19 | 39.9 | 3.71 | 6346 | 1748.8 | 0 |
| gcd | 0.900 | ORFS default @ 0.9 ns (`camp_gcd_clk090_a`) | 289.1 | 0.000 | 683.1 | 1.335 | 15.93 | 2.96 | 0.96 | 39.9 | 3.76 | 6446 | 1636.8 | 0 |
| ibex | 1.980 | ORFS default @ 1.98 ns (`camp_ibex_clk198_a`) | -23.1 | -0.033 | 30879.4 | 120.508 | 694.93 | 95.41 | 14.45 | 50.1 | 7.16 | 441009 | 499.2 | 4 |
| ibex | 2.200 | ORFS default — sintesi area, util 50, place +0.20 (`camp_ibex_base`) | 22.4 | 0.000 | 30735.2 | 107.868 | 688.21 | 123.77 | 13.11 | 49.9 | 7.12 | 438851 | 459.2 | 0 |
| ibex | 2.750 | ORFS default @ 2.75 ns (`camp_ibex_clk275_a`) | 285.0 | 0.000 | 30707.3 | 86.457 | 685.80 | 76.31 | 10.48 | 49.8 | 7.14 | 440282 | 405.7 | 0 |
| ibex | 3.520 | ORFS default @ 3.52 ns (`camp_ibex_clk352_a`) | 806.7 | 0.000 | 30683.1 | 67.642 | 684.74 | 62.18 | 8.18 | 49.8 | 7.15 | 440701 | 368.6 | 0 |
| spi | 1.000 | ORFS default @ 1 ns (`camp_spi_base`) | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |

### All flows (reference + challengers, absolute values)

| Design | Clock ns | Ricetta | Role | Prodotto | WNS ps | TNS ns | Area µm² | Power mW | Leak µW | IR worst | IR mean | Density % | Cong. | GRT WL | fmax | setup |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aes | 0.820 | ORFS default @ 0.82 ns (`camp_aes_base`) | reference | — | -8.9 | -0.024 | 19921.3 | 315.081 | 493.36 | 81.28 | 38.89 | 37.7 | 6.68 | 352701 | 1206.4 | 5 |
| aes | 0.820 | Buffer di clock più fitti (`camp_aes_cts_closer_bufs`) | challenger | win | -1.3 | -0.001 | 19918.3 | 315.049 | 493.14 | 81.46 | 38.90 | 37.7 | 6.68 | 352659 | 1217.7 | 1 |
| aes | 0.820 | Place più sparso (`camp_aes_place_sparser`) | challenger | win | -9.8 | -0.040 | 20141.3 | 318.074 | 500.30 | 70.95 | 36.59 | 38.2 | 6.82 | 359772 | 1205.1 | 11 |
| aes | 0.820 | Margine di setup sul repair (`camp_aes_repair_setup_margin`) | challenger | win | 16.9 | 0.000 | 20470.3 | 322.686 | 513.84 | 71.85 | 39.30 | 38.8 | 6.74 | 355611 | 1245.1 | 0 |
| aes | 0.820 | Padding celle +1 site (`camp_aes_cell_pad_plus`) | challenger | lose | -29.8 | -0.117 | 20140.5 | 323.238 | 500.57 | 70.79 | 37.08 | 38.2 | 7.42 | 391436 | 1176.8 | 15 |
| aes | 0.820 | Place più denso (`camp_aes_place_denser`) | challenger | tie | -8.6 | -0.014 | 20077.9 | 315.833 | 498.26 | 81.48 | 39.49 | 38.0 | 6.60 | 348150 | 1206.8 | 3 |
| aes | 0.820 | Repair TNS a metà (`camp_aes_repair_half_tns`) | challenger | lose | -25.3 | -0.154 | 20330.6 | 318.954 | 506.63 | 72.50 | 38.87 | 38.5 | 6.78 | 357677 | 1183.0 | 12 |
| aes | 0.820 | Sintesi ABC delay (`camp_aes_synth_delay`) | challenger | tie | -8.9 | -0.024 | 19921.3 | 315.081 | 493.36 | 81.28 | 38.89 | 37.7 | 6.68 | 352701 | 1206.4 | 5 |
| aes | 0.820 | Sintesi gerarchica (`camp_aes_synth_hier`) | challenger | lose | -9.1 | -0.013 | 19676.8 | 320.394 | 485.27 | 94.04 | 39.40 | 37.3 | 6.58 | 347289 | 1206.2 | 3 |
| dynamic_node | 6.000 | ORFS default @ 6 ns (`camp_dynamic_node_base`) | reference | — | 3353.8 | 0.000 | 22540.0 | 8.765 | 429.78 | 1.78 | 1.03 | 43.6 | 5.01 | 259047 | 377.9 | 0 |
| gcd | 0.400 | ORFS default @ 0.4 ns (`camp_gcd_clk040_a`) | reference | — | -85.8 | -2.479 | 908.4 | 4.213 | 23.93 | 10.83 | 3.45 | 53.0 | 4.31 | 7381 | 2058.4 | 46 |
| gcd | 0.400 | Netlist DSE / rewrite @ 0.4 ns (`camp_gcd_clk040_b`) | challenger | lose | -389.7 | -15.483 | 631.5 | 2.903 | 15.34 | 5.51 | 2.06 | 55.6 | 4.00 | 4545 | 1266.4 | 47 |
| gcd | 0.400 | Netlist DSE / rewrite @ 0.4 ns (`camp_gcd_clk040_c`) | challenger | lose | -234.8 | -7.769 | 919.3 | 6.101 | 23.89 | 10.62 | 3.92 | 54.2 | 4.77 | 8088 | 1575.3 | 48 |
| gcd | 0.460 | ORFS default — sintesi area, util 35, place +0.20 (`camp_gcd_base`) | reference | — | -37.2 | -0.595 | 940.3 | 3.932 | 25.64 | 6.67 | 2.64 | 54.9 | 4.43 | 7589 | 2011.4 | 38 |
| gcd | 0.460 | Floorplan più largo che alto (`camp_gcd_aspect_wide`) | challenger | win | -38.1 | -0.345 | 907.6 | 3.723 | 24.36 | 2.62 | 1.29 | 51.7 | 4.19 | 7350 | 2007.7 | 17 |
| gcd | 0.460 | Padding celle +1 site (`camp_gcd_cell_pad_plus`) | challenger | win | -40.8 | -0.415 | 875.7 | 3.617 | 23.49 | 5.37 | 2.11 | 51.1 | 4.50 | 7714 | 1997.0 | 12 |
| gcd | 0.460 | Util 25 (`camp_gcd_q1_d20u25`) | challenger | win | -36.3 | -0.886 | 952.8 | 3.860 | 25.89 | 4.11 | 2.28 | 38.9 | 3.24 | 7928 | 2015.0 | 45 |
| gcd | 0.460 | Util 45 (`camp_gcd_q1_d20u45`) | challenger | win | -37.7 | -1.040 | 956.5 | 4.016 | 26.05 | 5.72 | 2.33 | 70.6 | 5.44 | 7378 | 2009.3 | 45 |
| gcd | 0.460 | Place più denso, util 25 (`camp_gcd_q1_d25u25`) | challenger | win | -41.8 | -0.326 | 861.0 | 3.542 | 22.56 | 4.93 | 2.23 | 35.2 | 2.95 | 7216 | 1992.9 | 12 |
| gcd | 0.460 | Place più denso, stesso die — meno buffer di repair (`camp_gcd_q1_d25u35`) | challenger | win | -38.4 | -0.354 | 841.6 | 3.434 | 22.03 | 6.15 | 2.23 | 49.1 | 4.07 | 6971 | 2006.4 | 11 |
| gcd | 0.460 | Buffer di clock più fitti (`camp_gcd_cts_closer_bufs`) | challenger | tie | -37.2 | -0.595 | 940.3 | 3.932 | 25.64 | 6.67 | 2.64 | 54.9 | 4.43 | 7589 | 2011.4 | 38 |
| gcd | 0.460 | Sintesi ABC delay sulla stessa ricetta fisica (`camp_gcd_dse_fast`) | challenger | lose | -186.9 | -5.981 | 963.5 | 5.527 | 25.02 | 8.26 | 3.14 | 56.8 | 4.60 | 7814 | 1545.9 | 46 |
| gcd | 0.460 | Netlist DSE rewrite sul die del default (controllo geometria) (`camp_gcd_dse_fixedb`) | challenger | lose | -349.5 | -13.025 | 635.5 | 2.539 | 15.15 | 4.70 | 1.63 | 37.1 | 2.94 | 5038 | 1235.3 | 46 |
| gcd | 0.460 | Netlist DSE rewrite (sub_twos_complement) — place/route uguale al default (`camp_gcd_dse_small`) | challenger | lose | -338.3 | -13.090 | 609.9 | 2.428 | 14.53 | 3.33 | 1.37 | 53.7 | 3.93 | 4465 | 1252.7 | 46 |
| gcd | 0.460 | Place più sparso, util 25 (`camp_gcd_q1_d15u25`) | challenger | lose | -44.4 | -0.344 | 874.3 | 3.631 | 22.98 | 4.95 | 2.24 | 35.7 | 3.07 | 7506 | 1982.5 | 12 |
| gcd | 0.460 | Place più sparso, util 35 (`camp_gcd_q1_d15u35`) | challenger | lose | -43.7 | -0.744 | 981.3 | 3.995 | 27.29 | 6.76 | 2.64 | 57.3 | 4.47 | 7660 | 1985.3 | 43 |
| gcd | 0.460 | Place più sparso, util 45 (`camp_gcd_q1_d15u45`) | challenger | lose | -36.0 | -0.308 | 861.8 | 3.481 | 22.99 | 10.05 | 2.55 | 63.6 | 4.89 | 6631 | 2016.2 | 11 |
| gcd | 0.460 | Place più denso, util 45 (`camp_gcd_q1_d25u45`) | challenger | tie | -38.1 | -0.584 | 860.8 | 3.545 | 22.79 | 6.87 | 2.47 | 63.5 | 5.08 | 6882 | 2007.6 | 42 |
| gcd | 0.460 | Repair TNS a metà (`camp_gcd_repair_half_tns`) | challenger | lose | -36.6 | -0.549 | 894.6 | 3.677 | 24.00 | 7.97 | 2.59 | 52.2 | 4.31 | 7381 | 2013.6 | 43 |
| gcd | 0.460 | Margine di setup sul repair (`camp_gcd_repair_setup_margin`) | challenger | lose | -41.1 | -0.512 | 963.7 | 3.995 | 26.41 | 12.22 | 3.12 | 56.3 | 4.50 | 7700 | 1995.7 | 26 |
| gcd | 0.460 | Sintesi gerarchica (`camp_gcd_synth_hier`) | challenger | lose | -42.1 | -0.400 | 889.2 | 9.840 | 23.83 | 17.00 | 6.74 | 49.3 | 4.02 | 7244 | 1991.7 | 16 |
| gcd | 0.550 | ORFS default @ 0.55 ns (`camp_gcd_clk055_a`) | reference | — | 13.4 | 0.000 | 696.7 | 2.210 | 16.52 | 3.44 | 1.40 | 40.7 | 3.72 | 6369 | 1863.4 | 0 |
| gcd | 0.550 | Netlist DSE / rewrite @ 0.55 ns (`camp_gcd_clk055_b`) | challenger | lose | -251.2 | -9.079 | 611.0 | 2.033 | 14.35 | 5.05 | 1.46 | 53.8 | 4.04 | 4594 | 1248.2 | 43 |
| gcd | 0.550 | Netlist DSE / rewrite @ 0.55 ns (`camp_gcd_clk055_c`) | challenger | lose | -109.3 | -1.409 | 799.6 | 3.783 | 19.40 | 6.86 | 2.38 | 47.1 | 4.60 | 7800 | 1516.9 | 39 |
| gcd | 0.550 | Place più denso al clock dove il default chiude (0.55 ns) (`camp_gcd_q4_d25u35_c055`) | challenger | tie | 13.0 | 0.000 | 697.7 | 2.217 | 16.57 | 3.43 | 1.41 | 40.7 | 3.68 | 6309 | 1862.3 | 0 |
| gcd | 0.700 | ORFS default @ 0.7 ns (`camp_gcd_clk070_a`) | reference | — | 128.2 | 0.000 | 682.6 | 1.705 | 15.92 | 3.13 | 1.19 | 39.9 | 3.71 | 6346 | 1748.8 | 0 |
| gcd | 0.700 | Netlist DSE / rewrite @ 0.7 ns (`camp_gcd_clk070_b`) | challenger | lose | -128.3 | -3.498 | 582.8 | 1.534 | 13.62 | 2.45 | 0.94 | 51.3 | 3.62 | 4118 | 1207.3 | 39 |
| gcd | 0.700 | Netlist DSE / rewrite @ 0.7 ns (`camp_gcd_clk070_c`) | challenger | lose | 3.3 | 0.000 | 702.2 | 2.486 | 16.08 | 3.55 | 1.56 | 41.4 | 4.22 | 7164 | 1435.3 | 0 |
| gcd | 0.900 | ORFS default @ 0.9 ns (`camp_gcd_clk090_a`) | reference | — | 289.1 | 0.000 | 683.1 | 1.335 | 15.93 | 2.96 | 0.96 | 39.9 | 3.76 | 6446 | 1636.8 | 0 |
| gcd | 0.900 | Netlist DSE / rewrite @ 0.9 ns (`camp_gcd_clk090_b`) | challenger | lose | 4.7 | 0.000 | 518.7 | 1.039 | 11.59 | 2.32 | 0.65 | 45.6 | 3.52 | 4004 | 1116.9 | 0 |
| gcd | 0.900 | Netlist DSE / rewrite @ 0.9 ns (`camp_gcd_clk090_c`) | challenger | lose | 121.6 | 0.000 | 676.7 | 1.820 | 15.12 | 2.61 | 1.14 | 39.9 | 4.04 | 6857 | 1284.7 | 0 |
| ibex | 1.980 | ORFS default @ 1.98 ns (`camp_ibex_clk198_a`) | reference | — | -23.1 | -0.033 | 30879.4 | 120.508 | 694.93 | 95.41 | 14.45 | 50.1 | 7.16 | 441009 | 499.2 | 4 |
| ibex | 1.980 | Sintesi ABC delay @ 1.98 ns (`camp_ibex_clk198_s`) | challenger | lose | -61.1 | -7.110 | 33052.1 | 117.855 | 727.21 | 65.97 | 11.31 | 56.0 | 7.34 | 432835 | 489.9 | 301 |
| ibex | 2.200 | ORFS default — sintesi area, util 50, place +0.20 (`camp_ibex_base`) | reference | — | 22.4 | 0.000 | 30735.2 | 107.868 | 688.21 | 123.77 | 13.11 | 49.9 | 7.12 | 438851 | 459.2 | 0 |
| ibex | 2.200 | Sintesi ABC delay @ 2.2 ns (`camp_ibex_abcspeed`) | challenger | win | 20.4 | 0.000 | 30575.4 | 90.815 | 640.35 | 49.13 | 8.77 | 51.8 | 7.16 | 422381 | 458.8 | 0 |
| ibex | 2.200 | Floorplan più largo che alto (`camp_ibex_aspect_wide`) | challenger | win | 24.9 | 0.000 | 30796.4 | 109.442 | 690.62 | 85.83 | 10.49 | 49.9 | 7.62 | 470857 | 459.7 | 0 |
| ibex | 2.200 | Padding celle +1 site (`camp_ibex_cell_pad_plus`) | challenger | win | 21.8 | 0.000 | 30751.2 | 108.247 | 688.60 | 78.68 | 12.14 | 49.9 | 7.60 | 468115 | 459.1 | 0 |
| ibex | 2.200 | Place più sparso, stesso die (`camp_ibex_q1_d15u50`) | challenger | win | 36.2 | 0.000 | 30748.3 | 107.922 | 688.40 | 125.04 | 12.76 | 49.9 | 7.22 | 445041 | 462.2 | 0 |
| ibex | 2.200 | Core più stretto — die più piccolo, fili più corti (`camp_ibex_q1_d20u60`) | challenger | win | 42.3 | 0.000 | 30686.0 | 107.499 | 688.06 | 86.24 | 12.65 | 59.6 | 8.17 | 420930 | 463.5 | 0 |
| ibex | 2.200 | Place più denso, stesso die (`camp_ibex_q1_d25u50`) | challenger | win | 39.9 | 0.000 | 30711.0 | 107.344 | 687.50 | 116.96 | 13.41 | 49.8 | 7.02 | 432786 | 462.9 | 0 |
| ibex | 2.200 | Margine di setup sul repair (`camp_ibex_repair_setup_margin`) | challenger | win | 63.5 | 0.000 | 30743.7 | 107.966 | 688.50 | 123.77 | 13.12 | 49.9 | 7.12 | 438976 | 468.1 | 0 |
| ibex | 2.200 | Buffer di clock più fitti (`camp_ibex_cts_closer_bufs`) | challenger | tie | 26.5 | 0.000 | 30740.6 | 107.785 | 688.33 | 123.79 | 13.09 | 49.9 | 7.11 | 438255 | 460.1 | 0 |
| ibex | 2.200 | Core più largo — die più grande, fili più lunghi (`camp_ibex_q1_d20u40`) | challenger | lose | 16.1 | 0.000 | 30776.7 | 108.105 | 688.77 | 71.23 | 8.81 | 39.9 | 5.97 | 460215 | 457.9 | 0 |
| ibex | 2.200 | Repair TNS a metà (`camp_ibex_repair_half_tns`) | challenger | tie | 22.4 | 0.000 | 30735.2 | 107.868 | 688.21 | 123.77 | 13.11 | 49.9 | 7.12 | 438851 | 459.2 | 0 |
| ibex | 2.200 | Sintesi gerarchica (`camp_ibex_synth_hier`) | challenger | lose | 30.9 | 0.000 | 30728.3 | 108.751 | 685.46 | 145.53 | 14.34 | 49.7 | 7.04 | 434867 | 461.0 | 0 |
| ibex | 2.750 | ORFS default @ 2.75 ns (`camp_ibex_clk275_a`) | reference | — | 285.0 | 0.000 | 30707.3 | 86.457 | 685.80 | 76.31 | 10.48 | 49.8 | 7.14 | 440282 | 405.7 | 0 |
| ibex | 2.750 | Sintesi ABC delay @ 2.75 ns (`camp_ibex_clk275_s`) | challenger | lose | 166.3 | 0.000 | 30065.2 | 70.620 | 621.71 | 26.41 | 6.77 | 51.0 | 7.08 | 417747 | 387.0 | 0 |
| ibex | 3.520 | ORFS default @ 3.52 ns (`camp_ibex_clk352_a`) | reference | — | 806.7 | 0.000 | 30683.1 | 67.642 | 684.74 | 62.18 | 8.18 | 49.8 | 7.15 | 440701 | 368.6 | 0 |
| ibex | 3.520 | Sintesi ABC delay @ 3.52 ns (`camp_ibex_clk352_s`) | challenger | lose | 597.2 | 0.000 | 30033.5 | 55.188 | 620.45 | 30.35 | 5.33 | 50.9 | 7.11 | 419434 | 342.1 | 0 |
| spi | 1.000 | ORFS default @ 1 ns (`camp_spi_base`) | reference | — | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |
| spi | 1.000 | Sintesi ABC delay @ 1 ns (`camp_spi_abcspeed`) | challenger | lose | 600.8 | 0.000 | 265.7 | 0.313 | 5.80 | 1.06 | 0.62 | 9.2 | 0.65 | 1889 | 2505.0 | 0 |
| spi | 1.000 | Floorplan più largo che alto (`camp_spi_aspect_wide`) | challenger | lose | 611.7 | 0.000 | 275.6 | 0.304 | 5.32 | 1.77 | 0.61 | 9.9 | 0.81 | 2268 | 2575.6 | 0 |
| spi | 1.000 | Padding celle +1 site (`camp_spi_cell_pad_plus`) | challenger | tie | 612.5 | 0.000 | 267.6 | 0.302 | 5.32 | 0.93 | 0.52 | 9.4 | 0.83 | 2368 | 2580.3 | 0 |
| spi | 1.000 | Core più largo (`camp_spi_core_looser`) | challenger | lose | 611.7 | 0.000 | 272.9 | 0.300 | 5.32 | 1.15 | 0.54 | 6.0 | 0.51 | 2308 | 2575.4 | 0 |
| spi | 1.000 | Core più stretto (`camp_spi_core_tighter`) | challenger | lose | 615.5 | 0.000 | 260.7 | 0.298 | 5.32 | 2.09 | 1.10 | 21.0 | 1.49 | 1855 | 2600.5 | 0 |
| spi | 1.000 | Buffer di clock più fitti (`camp_spi_cts_closer_bufs`) | challenger | tie | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |
| spi | 1.000 | Place più denso (`camp_spi_place_denser`) | challenger | tie | 610.7 | 0.000 | 268.1 | 0.307 | 5.35 | 1.07 | 0.56 | 9.4 | 0.78 | 2205 | 2569.0 | 0 |
| spi | 1.000 | Place più sparso (`camp_spi_place_sparser`) | challenger | tie | 613.3 | 0.000 | 267.6 | 0.303 | 5.32 | 1.04 | 0.50 | 9.4 | 0.82 | 2317 | 2586.1 | 0 |
| spi | 1.000 | Repair TNS a metà (`camp_spi_repair_half_tns`) | challenger | tie | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |
| spi | 1.000 | Margine di setup sul repair (`camp_spi_repair_setup_margin`) | challenger | tie | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |
| spi | 1.000 | Sintesi gerarchica (`camp_spi_synth_hier`) | challenger | tie | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 0.53 | 9.4 | 0.79 | 2257 | 2578.9 | 0 |

### Challengers vs the reference in the same slot (Δ)

ΔWNS = cand − reference (ps; + better). Percent columns = 100·(cand−reference)/reference (− better for area/power/leak/IR/WL).

| Design | Clock | Ricetta | Prodotto | ΔWNS | Δarea % | Δpower % | Δleak % | ΔIR worst % | ΔIR mean % | ΔWL % | Δcong % | Δdens % |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gcd | 0.460 | Netlist DSE rewrite (sub_twos_complement) — place/route uguale al default (`camp_gcd_dse_small`) | lose | -301.13 | -35.13 | -38.26 | -43.36 | -50.08 | -48.11 | -41.16 | -11.33 | -2.25 |
| gcd | 0.460 | Sintesi ABC delay sulla stessa ricetta fisica (`camp_gcd_dse_fast`) | lose | -149.72 | 2.46 | 40.56 | -2.42 | 23.84 | 18.95 | 2.96 | 3.90 | 3.39 |
| gcd | 0.460 | Netlist DSE rewrite sul die del default (controllo geometria) (`camp_gcd_dse_fixedb`) | lose | -312.32 | -32.42 | -35.43 | -40.94 | -29.48 | -38.13 | -33.61 | -33.61 | -32.42 |
| gcd | 0.400 | Netlist DSE / rewrite @ 0.4 ns (`camp_gcd_clk040_b`) | lose | -303.84 | -30.48 | -31.10 | -35.91 | -49.07 | -40.10 | -38.42 | -7.20 | 4.76 |
| gcd | 0.400 | Netlist DSE / rewrite @ 0.4 ns (`camp_gcd_clk040_c`) | lose | -149.00 | 1.20 | 44.81 | -0.18 | -1.87 | 13.85 | 9.58 | 10.57 | 2.12 |
| gcd | 0.550 | Netlist DSE / rewrite @ 0.55 ns (`camp_gcd_clk055_b`) | lose | -264.54 | -12.29 | -8.00 | -13.14 | 46.66 | 3.95 | -27.87 | 8.70 | 32.17 |
| gcd | 0.550 | Netlist DSE / rewrite @ 0.55 ns (`camp_gcd_clk055_c`) | lose | -122.61 | 14.78 | 71.23 | 17.42 | 99.49 | 70.20 | 22.47 | 23.58 | 15.82 |
| gcd | 0.700 | Netlist DSE / rewrite @ 0.7 ns (`camp_gcd_clk070_b`) | lose | -256.48 | -14.61 | -10.03 | -14.41 | -21.85 | -21.35 | -35.11 | -2.21 | 28.68 |
| gcd | 0.700 | Netlist DSE / rewrite @ 0.7 ns (`camp_gcd_clk070_c`) | lose | -124.89 | 2.88 | 45.86 | 1.01 | 13.24 | 30.57 | 12.89 | 13.92 | 3.82 |
| gcd | 0.900 | Netlist DSE / rewrite @ 0.9 ns (`camp_gcd_clk090_b`) | lose | -284.37 | -24.07 | -22.18 | -27.24 | -21.62 | -32.26 | -37.88 | -6.39 | 14.44 |
| gcd | 0.900 | Netlist DSE / rewrite @ 0.9 ns (`camp_gcd_clk090_c`) | lose | -167.44 | -0.93 | 36.36 | -5.05 | -12.06 | 17.91 | 6.38 | 7.34 | -0.03 |
| spi | 1.000 | Sintesi ABC delay @ 1 ns (`camp_spi_abcspeed`) | lose | -11.43 | -0.70 | 3.93 | 9.05 | 8.38 | 17.44 | -16.30 | -18.05 | -2.77 |
| ibex | 2.200 | Sintesi ABC delay @ 2.2 ns (`camp_ibex_abcspeed`) | win | -2.02 | -0.52 | -15.81 | -6.95 | -60.31 | -33.12 | -3.75 | 0.55 | 3.92 |
| ibex | 1.980 | Sintesi ABC delay @ 1.98 ns (`camp_ibex_clk198_s`) | lose | -37.97 | 7.04 | -2.20 | 4.65 | -30.86 | -21.73 | -1.85 | 2.53 | 11.82 |
| ibex | 2.750 | Sintesi ABC delay @ 2.75 ns (`camp_ibex_clk275_s`) | lose | -118.73 | -2.09 | -18.32 | -9.35 | -65.39 | -35.41 | -5.12 | -0.88 | 2.28 |
| ibex | 3.520 | Sintesi ABC delay @ 3.52 ns (`camp_ibex_clk352_s`) | lose | -209.54 | -2.12 | -18.41 | -9.39 | -51.20 | -34.88 | -4.83 | -0.57 | 2.26 |
| gcd | 0.460 | Place più sparso, util 25 (`camp_gcd_q1_d15u25`) | lose | -7.24 | -7.02 | -7.67 | -10.40 | -25.74 | -15.03 | -1.09 | -30.82 | -34.97 |
| gcd | 0.460 | Place più sparso, util 35 (`camp_gcd_q1_d15u35`) | lose | -6.53 | 4.36 | 1.60 | 6.40 | 1.47 | 0.29 | 0.94 | 0.94 | 4.36 |
| gcd | 0.460 | Place più sparso, util 45 (`camp_gcd_q1_d15u45`) | lose | 1.19 | -8.35 | -11.48 | -10.36 | 50.74 | -3.30 | -12.62 | 10.39 | 15.79 |
| gcd | 0.460 | Util 25 (`camp_gcd_q1_d20u25`) | win | 0.89 | 1.33 | -1.84 | 0.96 | -38.32 | -13.47 | 4.47 | -26.94 | -29.13 |
| gcd | 0.460 | Util 45 (`camp_gcd_q1_d20u45`) | win | -0.51 | 1.73 | 2.11 | 1.60 | -14.27 | -11.82 | -2.78 | 22.82 | 28.51 |
| gcd | 0.460 | Place più denso, util 25 (`camp_gcd_q1_d25u25`) | win | -4.62 | -8.43 | -9.94 | -12.03 | -26.09 | -15.53 | -4.92 | -33.50 | -35.96 |
| gcd | 0.460 | Place più denso, stesso die — meno buffer di repair (`camp_gcd_q1_d25u35`) | win | -1.23 | -10.50 | -12.67 | -14.11 | -7.69 | -15.28 | -8.14 | -8.14 | -10.50 |
| gcd | 0.460 | Place più denso, util 45 (`camp_gcd_q1_d25u45`) | tie | -0.94 | -8.46 | -9.86 | -11.14 | 3.11 | -6.16 | -9.32 | 14.56 | 15.65 |
| ibex | 2.200 | Place più sparso, stesso die (`camp_ibex_q1_d15u50`) | win | 13.81 | 0.04 | 0.05 | 0.03 | 1.02 | -2.67 | 1.41 | 1.41 | 0.04 |
| ibex | 2.200 | Place più denso, stesso die (`camp_ibex_q1_d25u50`) | win | 17.48 | -0.08 | -0.49 | -0.10 | -5.50 | 2.29 | -1.38 | -1.38 | -0.08 |
| ibex | 2.200 | Core più largo — die più grande, fili più lunghi (`camp_ibex_q1_d20u40`) | lose | -6.30 | 0.14 | 0.22 | 0.08 | -42.45 | -32.77 | 4.87 | -16.18 | -19.96 |
| ibex | 2.200 | Core più stretto — die più piccolo, fili più corti (`camp_ibex_q1_d20u60`) | win | 19.94 | -0.16 | -0.34 | -0.02 | -30.33 | -3.53 | -4.08 | 14.79 | 19.49 |
| gcd | 0.550 | Place più denso al clock dove il default chiude (0.55 ns) (`camp_gcd_q4_d25u35_c055`) | tie | -0.33 | 0.15 | 0.35 | 0.26 | -0.31 | 0.67 | -0.94 | -0.94 | 0.15 |
| spi | 1.000 | Place più denso (`camp_spi_place_denser`) | tie | -1.48 | 0.20 | 2.07 | 0.54 | 9.81 | 6.79 | -2.30 | -2.30 | 0.20 |
| spi | 1.000 | Repair TNS a metà (`camp_spi_repair_half_tns`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| spi | 1.000 | Place più sparso (`camp_spi_place_sparser`) | tie | 1.08 | 0.00 | 0.64 | 0.00 | 6.93 | -4.24 | 2.66 | 2.66 | 0.00 |
| spi | 1.000 | Padding celle +1 site (`camp_spi_cell_pad_plus`) | tie | 0.22 | 0.00 | 0.30 | 0.00 | -5.22 | -2.07 | 4.92 | 4.92 | 0.00 |
| spi | 1.000 | Margine di setup sul repair (`camp_spi_repair_setup_margin`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| spi | 1.000 | Buffer di clock più fitti (`camp_spi_cts_closer_bufs`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| spi | 1.000 | Floorplan più largo che alto (`camp_spi_aspect_wide`) | lose | -0.50 | 2.98 | 1.02 | 0.00 | 80.90 | 15.14 | 0.49 | 2.25 | 4.79 |
| spi | 1.000 | Core più stretto (`camp_spi_core_tighter`) | lose | 3.22 | -2.58 | -1.06 | 0.00 | 113.72 | 108.34 | -17.81 | 87.72 | 122.50 |
| spi | 1.000 | Core più largo (`camp_spi_core_looser`) | lose | -0.53 | 1.99 | -0.12 | 0.00 | 17.74 | 2.49 | 2.26 | -36.10 | -36.27 |
| spi | 1.000 | Sintesi gerarchica (`camp_spi_synth_hier`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| gcd | 0.460 | Margine di setup sul repair (`camp_gcd_repair_setup_margin`) | lose | -3.90 | 2.49 | 1.60 | 3.00 | 83.24 | 18.20 | 1.46 | 1.46 | 2.49 |
| gcd | 0.460 | Floorplan più largo che alto (`camp_gcd_aspect_wide`) | win | -0.91 | -3.48 | -5.33 | -5.01 | -60.72 | -51.13 | -3.15 | -5.44 | -5.76 |
| aes | 0.820 | Place più denso (`camp_aes_place_denser`) | tie | 0.28 | 0.79 | 0.24 | 0.99 | 0.25 | 1.54 | -1.29 | -1.29 | 0.79 |
| aes | 0.820 | Margine di setup sul repair (`camp_aes_repair_setup_margin`) | win | 25.78 | 2.76 | 2.41 | 4.15 | -11.59 | 1.07 | 0.83 | 0.83 | 2.76 |
| gcd | 0.460 | Sintesi gerarchica (`camp_gcd_synth_hier`) | lose | -4.91 | -5.43 | 150.23 | -7.08 | 154.99 | 155.61 | -4.55 | -9.36 | -10.20 |
| gcd | 0.460 | Padding celle +1 site (`camp_gcd_cell_pad_plus`) | win | -3.59 | -6.87 | -8.01 | -8.40 | -19.40 | -19.84 | 1.65 | 1.65 | -6.87 |
| gcd | 0.460 | Repair TNS a metà (`camp_gcd_repair_half_tns`) | lose | 0.55 | -4.87 | -6.49 | -6.41 | 19.47 | -1.98 | -2.74 | -2.74 | -4.87 |
| gcd | 0.460 | Buffer di clock più fitti (`camp_gcd_cts_closer_bufs`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| ibex | 2.200 | Sintesi gerarchica (`camp_ibex_synth_hier`) | lose | 8.46 | -0.02 | 0.82 | -0.40 | 17.58 | 9.38 | -0.91 | -1.13 | -0.25 |
| ibex | 2.200 | Floorplan più largo che alto (`camp_ibex_aspect_wide`) | win | 2.48 | 0.20 | 1.46 | 0.35 | -30.65 | -19.97 | 7.29 | 7.07 | -0.01 |
| ibex | 2.200 | Padding celle +1 site (`camp_ibex_cell_pad_plus`) | win | -0.66 | 0.05 | 0.35 | 0.06 | -36.43 | -7.40 | 6.67 | 6.67 | 0.05 |
| ibex | 2.200 | Repair TNS a metà (`camp_ibex_repair_half_tns`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| ibex | 2.200 | Margine di setup sul repair (`camp_ibex_repair_setup_margin`) | win | 41.11 | 0.03 | 0.09 | 0.04 | -0.00 | 0.08 | 0.03 | 0.03 | 0.03 |
| ibex | 2.200 | Buffer di clock più fitti (`camp_ibex_cts_closer_bufs`) | tie | 4.11 | 0.02 | -0.08 | 0.02 | 0.01 | -0.15 | -0.14 | -0.14 | 0.02 |
| aes | 0.820 | Sintesi ABC delay (`camp_aes_synth_delay`) | tie | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| aes | 0.820 | Sintesi gerarchica (`camp_aes_synth_hier`) | lose | -0.15 | -1.23 | 1.69 | -1.64 | 15.70 | 1.32 | -1.53 | -1.53 | -1.23 |
| aes | 0.820 | Place più sparso (`camp_aes_place_sparser`) | win | -0.86 | 1.10 | 0.95 | 1.41 | -12.71 | -5.91 | 2.00 | 2.00 | 1.10 |
| aes | 0.820 | Padding celle +1 site (`camp_aes_cell_pad_plus`) | lose | -20.83 | 1.10 | 2.59 | 1.46 | -12.91 | -4.66 | 10.98 | 10.98 | 1.10 |
| aes | 0.820 | Repair TNS a metà (`camp_aes_repair_half_tns`) | lose | -16.37 | 2.05 | 1.23 | 2.69 | -10.80 | -0.05 | 1.41 | 1.41 | 2.05 |
| aes | 0.820 | Buffer di clock più fitti (`camp_aes_cts_closer_bufs`) | win | 7.67 | -0.02 | -0.01 | -0.04 | 0.23 | 0.04 | -0.01 | -0.01 | -0.01 |

### Side-by-side sheets (reference column + each challenger)

#### aes @ 0.820 ns — reference: ORFS default @ 0.82 ns (1/2)

| Metric | `ORFS default @ 0.82 ns` | `Buffer di clock più fitti` | `Place più sparso` | `Margine di setup sul repair` | `Padding celle +1 site` |
|---|---|---|---|---|---|
| WNS (ps) | -8.9 | -1.3 | -9.8 | 16.9 | -29.8 |
| TNS (ns) | -0.024 | -0.001 | -0.040 | 0.000 | -0.117 |
| stdcell area (µm²) | 19921.3 | 19918.3 | 20141.3 | 20470.3 | 20140.5 |
| total power (mW) | 315.081 | 315.049 | 318.074 | 322.686 | 323.238 |
| leakage (µW) | 493.36 | 493.14 | 500.30 | 513.84 | 500.57 |
| IR worst VDD (mV) | 81.28 | 81.46 | 70.95 | 71.85 | 70.79 |
| IR mean VDD (mV) | 38.89 | 38.90 | 36.59 | 39.30 | 37.08 |
| cell density (%) | 37.7 | 37.7 | 38.2 | 38.8 | 38.2 |
| congestion WL/core | 6.68 | 6.68 | 6.82 | 6.74 | 7.42 |
| GRT wirelength | 352701 | 352659 | 359772 | 355611 | 391436 |
| fmax (MHz) | 1206.4 | 1217.7 | 1205.1 | 1245.1 | 1176.8 |
| setup violations | 5 | 1 | 11 | 0 | 15 |

#### aes @ 0.820 ns — reference: ORFS default @ 0.82 ns (2/2)

| Metric | `ORFS default @ 0.82 ns` | `Place più denso` | `Repair TNS a metà` | `Sintesi ABC delay` | `Sintesi gerarchica` |
|---|---|---|---|---|---|
| WNS (ps) | -8.9 | -8.6 | -25.3 | -8.9 | -9.1 |
| TNS (ns) | -0.024 | -0.014 | -0.154 | -0.024 | -0.013 |
| stdcell area (µm²) | 19921.3 | 20077.9 | 20330.6 | 19921.3 | 19676.8 |
| total power (mW) | 315.081 | 315.833 | 318.954 | 315.081 | 320.394 |
| leakage (µW) | 493.36 | 498.26 | 506.63 | 493.36 | 485.27 |
| IR worst VDD (mV) | 81.28 | 81.48 | 72.50 | 81.28 | 94.04 |
| IR mean VDD (mV) | 38.89 | 39.49 | 38.87 | 38.89 | 39.40 |
| cell density (%) | 37.7 | 38.0 | 38.5 | 37.7 | 37.3 |
| congestion WL/core | 6.68 | 6.60 | 6.78 | 6.68 | 6.58 |
| GRT wirelength | 352701 | 348150 | 357677 | 352701 | 347289 |
| fmax (MHz) | 1206.4 | 1206.8 | 1183.0 | 1206.4 | 1206.2 |
| setup violations | 5 | 3 | 12 | 5 | 3 |

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

#### gcd @ 0.460 ns — reference: ORFS default — sintesi area, util 35, place +0.20 (1/5)

| Metric | `ORFS default — sintesi area, util 35, place +0.20` | `Floorplan più largo che alto` | `Padding celle +1 site` | `Util 25` | `Util 45` |
|---|---|---|---|---|---|
| WNS (ps) | -37.2 | -38.1 | -40.8 | -36.3 | -37.7 |
| TNS (ns) | -0.595 | -0.345 | -0.415 | -0.886 | -1.040 |
| stdcell area (µm²) | 940.3 | 907.6 | 875.7 | 952.8 | 956.5 |
| total power (mW) | 3.932 | 3.723 | 3.617 | 3.860 | 4.016 |
| leakage (µW) | 25.64 | 24.36 | 23.49 | 25.89 | 26.05 |
| IR worst VDD (mV) | 6.67 | 2.62 | 5.37 | 4.11 | 5.72 |
| IR mean VDD (mV) | 2.64 | 1.29 | 2.11 | 2.28 | 2.33 |
| cell density (%) | 54.9 | 51.7 | 51.1 | 38.9 | 70.6 |
| congestion WL/core | 4.43 | 4.19 | 4.50 | 3.24 | 5.44 |
| GRT wirelength | 7589 | 7350 | 7714 | 7928 | 7378 |
| fmax (MHz) | 2011.4 | 2007.7 | 1997.0 | 2015.0 | 2009.3 |
| setup violations | 38 | 17 | 12 | 45 | 45 |

#### gcd @ 0.460 ns — reference: ORFS default — sintesi area, util 35, place +0.20 (2/5)

| Metric | `ORFS default — sintesi area, util 35, place +0.20` | `Place più denso, util 25` | `Place più denso, stesso die — meno buffer di repair` | `Buffer di clock più fitti` | `Sintesi ABC delay sulla stessa ricetta fisica` |
|---|---|---|---|---|---|
| WNS (ps) | -37.2 | -41.8 | -38.4 | -37.2 | -186.9 |
| TNS (ns) | -0.595 | -0.326 | -0.354 | -0.595 | -5.981 |
| stdcell area (µm²) | 940.3 | 861.0 | 841.6 | 940.3 | 963.5 |
| total power (mW) | 3.932 | 3.542 | 3.434 | 3.932 | 5.527 |
| leakage (µW) | 25.64 | 22.56 | 22.03 | 25.64 | 25.02 |
| IR worst VDD (mV) | 6.67 | 4.93 | 6.15 | 6.67 | 8.26 |
| IR mean VDD (mV) | 2.64 | 2.23 | 2.23 | 2.64 | 3.14 |
| cell density (%) | 54.9 | 35.2 | 49.1 | 54.9 | 56.8 |
| congestion WL/core | 4.43 | 2.95 | 4.07 | 4.43 | 4.60 |
| GRT wirelength | 7589 | 7216 | 6971 | 7589 | 7814 |
| fmax (MHz) | 2011.4 | 1992.9 | 2006.4 | 2011.4 | 1545.9 |
| setup violations | 38 | 12 | 11 | 38 | 46 |

#### gcd @ 0.460 ns — reference: ORFS default — sintesi area, util 35, place +0.20 (3/5)

| Metric | `ORFS default — sintesi area, util 35, place +0.20` | `Netlist DSE rewrite sul die del default (controllo geometria)` | `Netlist DSE rewrite (sub_twos_complement) — place/route uguale al default` | `Place più sparso, util 25` | `Place più sparso, util 35` |
|---|---|---|---|---|---|
| WNS (ps) | -37.2 | -349.5 | -338.3 | -44.4 | -43.7 |
| TNS (ns) | -0.595 | -13.025 | -13.090 | -0.344 | -0.744 |
| stdcell area (µm²) | 940.3 | 635.5 | 609.9 | 874.3 | 981.3 |
| total power (mW) | 3.932 | 2.539 | 2.428 | 3.631 | 3.995 |
| leakage (µW) | 25.64 | 15.15 | 14.53 | 22.98 | 27.29 |
| IR worst VDD (mV) | 6.67 | 4.70 | 3.33 | 4.95 | 6.76 |
| IR mean VDD (mV) | 2.64 | 1.63 | 1.37 | 2.24 | 2.64 |
| cell density (%) | 54.9 | 37.1 | 53.7 | 35.7 | 57.3 |
| congestion WL/core | 4.43 | 2.94 | 3.93 | 3.07 | 4.47 |
| GRT wirelength | 7589 | 5038 | 4465 | 7506 | 7660 |
| fmax (MHz) | 2011.4 | 1235.3 | 1252.7 | 1982.5 | 1985.3 |
| setup violations | 38 | 46 | 46 | 12 | 43 |

#### gcd @ 0.460 ns — reference: ORFS default — sintesi area, util 35, place +0.20 (4/5)

| Metric | `ORFS default — sintesi area, util 35, place +0.20` | `Place più sparso, util 45` | `Place più denso, util 45` | `Repair TNS a metà` | `Margine di setup sul repair` |
|---|---|---|---|---|---|
| WNS (ps) | -37.2 | -36.0 | -38.1 | -36.6 | -41.1 |
| TNS (ns) | -0.595 | -0.308 | -0.584 | -0.549 | -0.512 |
| stdcell area (µm²) | 940.3 | 861.8 | 860.8 | 894.6 | 963.7 |
| total power (mW) | 3.932 | 3.481 | 3.545 | 3.677 | 3.995 |
| leakage (µW) | 25.64 | 22.99 | 22.79 | 24.00 | 26.41 |
| IR worst VDD (mV) | 6.67 | 10.05 | 6.87 | 7.97 | 12.22 |
| IR mean VDD (mV) | 2.64 | 2.55 | 2.47 | 2.59 | 3.12 |
| cell density (%) | 54.9 | 63.6 | 63.5 | 52.2 | 56.3 |
| congestion WL/core | 4.43 | 4.89 | 5.08 | 4.31 | 4.50 |
| GRT wirelength | 7589 | 6631 | 6882 | 7381 | 7700 |
| fmax (MHz) | 2011.4 | 2016.2 | 2007.6 | 2013.6 | 1995.7 |
| setup violations | 38 | 11 | 42 | 43 | 26 |

#### gcd @ 0.460 ns — reference: ORFS default — sintesi area, util 35, place +0.20 (5/5)

| Metric | `ORFS default — sintesi area, util 35, place +0.20` | `Sintesi gerarchica` |
|---|---|---|
| WNS (ps) | -37.2 | -42.1 |
| TNS (ns) | -0.595 | -0.400 |
| stdcell area (µm²) | 940.3 | 889.2 |
| total power (mW) | 3.932 | 9.840 |
| leakage (µW) | 25.64 | 23.83 |
| IR worst VDD (mV) | 6.67 | 17.00 |
| IR mean VDD (mV) | 2.64 | 6.74 |
| cell density (%) | 54.9 | 49.3 |
| congestion WL/core | 4.43 | 4.02 |
| GRT wirelength | 7589 | 7244 |
| fmax (MHz) | 2011.4 | 1991.7 |
| setup violations | 38 | 16 |

#### gcd @ 0.550 ns — reference: ORFS default @ 0.55 ns

| Metric | `ORFS default @ 0.55 ns` | `Netlist DSE / rewrite @ 0.55 ns` | `Netlist DSE / rewrite @ 0.55 ns` | `Place più denso al clock dove il default chiude (0.55 ns)` |
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

| Metric | `ORFS default @ 1.98 ns` | `Sintesi ABC delay @ 1.98 ns` |
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

#### ibex @ 2.200 ns — reference: ORFS default — sintesi area, util 50, place +0.20 (1/3)

| Metric | `ORFS default — sintesi area, util 50, place +0.20` | `Sintesi ABC delay @ 2.2 ns` | `Floorplan più largo che alto` | `Padding celle +1 site` | `Place più sparso, stesso die` |
|---|---|---|---|---|---|
| WNS (ps) | 22.4 | 20.4 | 24.9 | 21.8 | 36.2 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 30735.2 | 30575.4 | 30796.4 | 30751.2 | 30748.3 |
| total power (mW) | 107.868 | 90.815 | 109.442 | 108.247 | 107.922 |
| leakage (µW) | 688.21 | 640.35 | 690.62 | 688.60 | 688.40 |
| IR worst VDD (mV) | 123.77 | 49.13 | 85.83 | 78.68 | 125.04 |
| IR mean VDD (mV) | 13.11 | 8.77 | 10.49 | 12.14 | 12.76 |
| cell density (%) | 49.9 | 51.8 | 49.9 | 49.9 | 49.9 |
| congestion WL/core | 7.12 | 7.16 | 7.62 | 7.60 | 7.22 |
| GRT wirelength | 438851 | 422381 | 470857 | 468115 | 445041 |
| fmax (MHz) | 459.2 | 458.8 | 459.7 | 459.1 | 462.2 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### ibex @ 2.200 ns — reference: ORFS default — sintesi area, util 50, place +0.20 (2/3)

| Metric | `ORFS default — sintesi area, util 50, place +0.20` | `Core più stretto — die più piccolo, fili più corti` | `Place più denso, stesso die` | `Margine di setup sul repair` | `Buffer di clock più fitti` |
|---|---|---|---|---|---|
| WNS (ps) | 22.4 | 42.3 | 39.9 | 63.5 | 26.5 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 30735.2 | 30686.0 | 30711.0 | 30743.7 | 30740.6 |
| total power (mW) | 107.868 | 107.499 | 107.344 | 107.966 | 107.785 |
| leakage (µW) | 688.21 | 688.06 | 687.50 | 688.50 | 688.33 |
| IR worst VDD (mV) | 123.77 | 86.24 | 116.96 | 123.77 | 123.79 |
| IR mean VDD (mV) | 13.11 | 12.65 | 13.41 | 13.12 | 13.09 |
| cell density (%) | 49.9 | 59.6 | 49.8 | 49.9 | 49.9 |
| congestion WL/core | 7.12 | 8.17 | 7.02 | 7.12 | 7.11 |
| GRT wirelength | 438851 | 420930 | 432786 | 438976 | 438255 |
| fmax (MHz) | 459.2 | 463.5 | 462.9 | 468.1 | 460.1 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### ibex @ 2.200 ns — reference: ORFS default — sintesi area, util 50, place +0.20 (3/3)

| Metric | `ORFS default — sintesi area, util 50, place +0.20` | `Core più largo — die più grande, fili più lunghi` | `Repair TNS a metà` | `Sintesi gerarchica` |
|---|---|---|---|---|
| WNS (ps) | 22.4 | 16.1 | 22.4 | 30.9 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 30735.2 | 30776.7 | 30735.2 | 30728.3 |
| total power (mW) | 107.868 | 108.105 | 107.868 | 108.751 |
| leakage (µW) | 688.21 | 688.77 | 688.21 | 685.46 |
| IR worst VDD (mV) | 123.77 | 71.23 | 123.77 | 145.53 |
| IR mean VDD (mV) | 13.11 | 8.81 | 13.11 | 14.34 |
| cell density (%) | 49.9 | 39.9 | 49.9 | 49.7 |
| congestion WL/core | 7.12 | 5.97 | 7.12 | 7.04 |
| GRT wirelength | 438851 | 460215 | 438851 | 434867 |
| fmax (MHz) | 459.2 | 457.9 | 459.2 | 461.0 |
| setup violations | 0 | 0 | 0 | 0 |

#### ibex @ 2.750 ns — reference: ORFS default @ 2.75 ns

| Metric | `ORFS default @ 2.75 ns` | `Sintesi ABC delay @ 2.75 ns` |
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

| Metric | `ORFS default @ 3.52 ns` | `Sintesi ABC delay @ 3.52 ns` |
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

#### spi @ 1.000 ns — reference: ORFS default @ 1 ns (1/3)

| Metric | `ORFS default @ 1 ns` | `Sintesi ABC delay @ 1 ns` | `Floorplan più largo che alto` | `Padding celle +1 site` | `Core più largo` |
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

#### spi @ 1.000 ns — reference: ORFS default @ 1 ns (2/3)

| Metric | `ORFS default @ 1 ns` | `Core più stretto` | `Buffer di clock più fitti` | `Place più denso` | `Place più sparso` |
|---|---|---|---|---|---|
| WNS (ps) | 612.2 | 615.5 | 612.2 | 610.7 | 613.3 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 267.6 | 260.7 | 267.6 | 268.1 | 267.6 |
| total power (mW) | 0.301 | 0.298 | 0.301 | 0.307 | 0.303 |
| leakage (µW) | 5.32 | 5.32 | 5.32 | 5.35 | 5.32 |
| IR worst VDD (mV) | 0.98 | 2.09 | 0.98 | 1.07 | 1.04 |
| IR mean VDD (mV) | 0.53 | 1.10 | 0.53 | 0.56 | 0.50 |
| cell density (%) | 9.4 | 21.0 | 9.4 | 9.4 | 9.4 |
| congestion WL/core | 0.79 | 1.49 | 0.79 | 0.78 | 0.82 |
| GRT wirelength | 2257 | 1855 | 2257 | 2205 | 2317 |
| fmax (MHz) | 2578.9 | 2600.5 | 2578.9 | 2569.0 | 2586.1 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### spi @ 1.000 ns — reference: ORFS default @ 1 ns (3/3)

| Metric | `ORFS default @ 1 ns` | `Repair TNS a metà` | `Margine di setup sul repair` | `Sintesi gerarchica` |
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

**Metodo di sintesi (nuovi challenger):** ABC `area` — Q1–Q4: 4 win §5 sulla netlist ufficiale (ABC area) + knob fisici. ABC delay e i rewrite DSE non hanno mai vinto §5 (H1: il proxy inverte).

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
  "why": "Q1\u2013Q4: 4 win \u00a75 sulla netlist ufficiale (ABC area) + knob fisici. ABC delay e i rewrite DSE non hanno mai vinto \u00a75 (H1: il proxy inverte).",
  "next_synth_axes": [
    "SYNTH_HIERARCHICAL",
    "TNS_END_PERCENT after map"
  ]
}
```

