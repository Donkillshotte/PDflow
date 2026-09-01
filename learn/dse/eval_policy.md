# Next-iteration eval vs frozen I1–I5

Plan sha: `cf02fb91ed5b757ba057354b2f53cb18a75586e7cf7ccf895369767436f76c98`
Experiments: 58 (49 done)

Win criteria and I1–I5 bars are **frozen**. This script does not retune them.
§5 win stays WNS / area-tie / first-to-close. Power and leakage are extra axes.

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
      "n": 1,
      "mean_ns": -0.012051029999999999,
      "std_ns": 0.0
    },
    "dynamic_node": {
      "n": 1,
      "mean_ns": -0.24974000000000007,
      "std_ns": 0.0
    },
    "gcd": {
      "n": 25,
      "mean_ns": -0.0515376128,
      "std_ns": 0.018825573814637207
    },
    "ibex": {
      "n": 12,
      "mean_ns": -0.17557045000000002,
      "std_ns": 0.10630476012937778
    },
    "spi": {
      "n": 2,
      "mean_ns": 0.02352949999999998,
      "std_ns": 0.00931047498788322
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
      "pred_ns": -0.040468950000000004,
      "actual_ns": -0.0444042,
      "err_ns": -0.003935249999999994,
      "band_ns": 0.047135033246270074,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d15u35",
      "design": "gcd",
      "pred_ns": -0.03848845,
      "actual_ns": -0.0436955,
      "err_ns": -0.005207049999999998,
      "band_ns": 0.047135033246270074,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d15u45",
      "design": "gcd",
      "pred_ns": -0.03546665,
      "actual_ns": -0.0359792,
      "err_ns": -0.0005125500000000005,
      "band_ns": 0.047135033246270074,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d20u25",
      "design": "gcd",
      "pred_ns": -0.04067763,
      "actual_ns": -0.0362789,
      "err_ns": 0.0043987299999999965,
      "band_ns": 0.047135033246270074,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d20u45",
      "design": "gcd",
      "pred_ns": -0.03596875,
      "actual_ns": -0.0376739,
      "err_ns": -0.0017051500000000025,
      "band_ns": 0.047135033246270074,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d25u25",
      "design": "gcd",
      "pred_ns": -0.03866095,
      "actual_ns": -0.0417844,
      "err_ns": -0.00312345,
      "band_ns": 0.047135033246270074,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d25u35",
      "design": "gcd",
      "pred_ns": -0.036978250000000004,
      "actual_ns": -0.0384003,
      "err_ns": -0.0014220499999999942,
      "band_ns": 0.047135033246270074,
      "inside": true
    },
    {
      "variant": "camp_gcd_q1_d25u45",
      "design": "gcd",
      "pred_ns": -0.03598545,
      "actual_ns": -0.0381096,
      "err_ns": -0.0021241499999999983,
      "band_ns": 0.047135033246270074,
      "inside": true
    },
    {
      "variant": "camp_ibex_q1_d15u50",
      "design": "ibex",
      "pred_ns": 0.07775857499999997,
      "actual_ns": 0.0362255,
      "err_ns": -0.04153307499999997,
      "band_ns": 0.2520103193739892,
      "inside": true
    },
    {
      "variant": "camp_ibex_q1_d25u50",
      "design": "ibex",
      "pred_ns": 0.106705575,
      "actual_ns": 0.039892,
      "err_ns": -0.066813575,
      "band_ns": 0.2520103193739892,
      "inside": true
    },
    {
      "variant": "camp_ibex_q1_d20u40",
      "design": "ibex",
      "pred_ns": 0.09817357499999996,
      "actual_ns": 0.0161107,
      "err_ns": -0.08206287499999995,
      "band_ns": 0.2520103193739892,
      "inside": true
    },
    {
      "variant": "camp_ibex_q1_d20u60",
      "design": "ibex",
      "pred_ns": 0.12179657499999996,
      "actual_ns": 0.0423498,
      "err_ns": -0.07944677499999997,
      "band_ns": 0.2520103193739892,
      "inside": true
    },
    {
      "variant": "camp_gcd_q4_d25u35_c055",
      "design": "gcd",
      "pred_ns": 0.023823449999999996,
      "actual_ns": 0.0130203,
      "err_ns": -0.010803149999999996,
      "band_ns": 0.047135033246270074,
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

**Verdict:** I5 supported (place Spearman 0.968 ≥ 0.6; F1 Spearman 0.866)

```json
{
  "n_place_pairs": 41,
  "n_f1_pairs": 3,
  "place_spearman": 0.9679442508710799,
  "f1_spearman": 0.8660254037844387,
  "bar": 0.6,
  "min_n": 8,
  "supported": true,
  "verdict": "I5 supported (place Spearman 0.968 \u2265 0.6; F1 Spearman 0.866)"
}
```

## gate_diagnostics

**Verdict:** gate FP=16 FN=0 precision=0.200 (4 product-wins among 29 challengers)

```json
{
  "n_challengers": 29,
  "n_promoted": 20,
  "n_real_wins": 4,
  "tp": 4,
  "fp": 16,
  "fn": 0,
  "tn": 9,
  "precision": 0.2,
  "recall": 1.0,
  "verdict": "gate FP=16 FN=0 precision=0.200 (4 product-wins among 29 challengers)"
}
```

## QoR_vs_base

**Verdict:** QoR vs base: 29 challengers, 29 with finish power, 4 §5 wins (WNS/area bars unchanged)

| Variant | §5 | ΔWNS ps | Δarea % | Δpower % | Δleak % | P cand mW | P base mW |
|---|---|---:|---:|---:|---:|---:|---:|
| `camp_gcd_dse_small` | lose | -301.13 | -35.13 | -38.26 | -43.36 | 2.428 | 3.932 |
| `camp_gcd_dse_fast` | lose | -149.72 | 2.46 | 40.56 | -2.42 | 5.527 | 3.932 |
| `camp_gcd_dse_fixedb` | lose | -312.32 | -32.42 | -35.43 | -40.94 | 2.539 | 3.932 |
| `camp_gcd_clk040_b` | lose | -303.84 | -30.48 | -31.10 | -35.91 | 2.903 | 4.213 |
| `camp_gcd_clk040_c` | lose | -149.00 | 1.20 | 44.81 | -0.18 | 6.101 | 4.213 |
| `camp_gcd_clk055_b` | lose | -264.54 | -12.29 | -8.00 | -13.14 | 2.033 | 2.210 |
| `camp_gcd_clk055_c` | lose | -122.61 | 14.78 | 71.23 | 17.42 | 3.783 | 2.210 |
| `camp_gcd_clk070_b` | lose | -256.48 | -14.61 | -10.03 | -14.41 | 1.534 | 1.705 |
| `camp_gcd_clk070_c` | lose | -124.89 | 2.88 | 45.86 | 1.01 | 2.486 | 1.705 |
| `camp_gcd_clk090_b` | lose | -284.37 | -24.07 | -22.18 | -27.24 | 1.039 | 1.335 |
| `camp_gcd_clk090_c` | lose | -167.44 | -0.93 | 36.36 | -5.05 | 1.820 | 1.335 |
| `camp_spi_abcspeed` | lose | -11.43 | -0.70 | 3.93 | 9.05 | 0.313 | 0.301 |
| `camp_ibex_abcspeed` | tie | -2.02 | -0.52 | -15.81 | -6.95 | 90.815 | 107.868 |
| `camp_ibex_clk198_s` | lose | -37.97 | 7.04 | -2.20 | 4.65 | 117.855 | 120.508 |
| `camp_ibex_clk275_s` | lose | -118.73 | -2.09 | -18.32 | -9.35 | 70.620 | 86.457 |
| `camp_ibex_clk352_s` | lose | -209.54 | -2.12 | -18.41 | -9.39 | 55.188 | 67.642 |
| `camp_gcd_q1_d15u25` | lose | -7.24 | -7.02 | -7.67 | -10.40 | 3.631 | 3.932 |
| `camp_gcd_q1_d15u35` | lose | -6.53 | 4.36 | 1.60 | 6.40 | 3.995 | 3.932 |
| `camp_gcd_q1_d15u45` | tie | 1.19 | -8.35 | -11.48 | -10.36 | 3.481 | 3.932 |
| `camp_gcd_q1_d20u25` | tie | 0.89 | 1.33 | -1.84 | 0.96 | 3.860 | 3.932 |
| `camp_gcd_q1_d20u45` | tie | -0.51 | 1.73 | 2.11 | 1.60 | 4.016 | 3.932 |
| `camp_gcd_q1_d25u25` | tie | -4.62 | -8.43 | -9.94 | -12.03 | 3.542 | 3.932 |
| `camp_gcd_q1_d25u35` | win | -1.23 | -10.50 | -12.67 | -14.11 | 3.434 | 3.932 |
| `camp_gcd_q1_d25u45` | tie | -0.94 | -8.46 | -9.86 | -11.14 | 3.545 | 3.932 |
| `camp_ibex_q1_d15u50` | win | 13.81 | 0.04 | 0.05 | 0.03 | 107.922 | 107.868 |
| `camp_ibex_q1_d25u50` | win | 17.48 | -0.08 | -0.49 | -0.10 | 107.344 | 107.868 |
| `camp_ibex_q1_d20u40` | lose | -6.30 | 0.14 | 0.22 | 0.08 | 108.105 | 107.868 |
| `camp_ibex_q1_d20u60` | win | 19.94 | -0.16 | -0.34 | -0.02 | 107.499 | 107.868 |
| `camp_gcd_q4_d25u35_c055` | tie | -0.34 | 0.15 | 0.35 | 0.26 | 2.217 | 2.210 |

