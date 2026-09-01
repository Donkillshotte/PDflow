# Next-iteration eval vs frozen I1–I5

Plan sha: `cf02fb91ed5b757ba057354b2f53cb18a75586e7cf7ccf895369767436f76c98`
Experiments: 45 (36 done)

Win criteria and I1–I5 bars are **frozen**. This script does not retune them.

## I1_physical_knobs

**Verdict:** I1 incomplete (no Q1 knob finishes yet)

```json
{
  "wins": [],
  "ranges": {
    "gcd": {
      "n_q1": 0,
      "range_ps": null,
      "n_wns": 1
    },
    "ibex": {
      "n_q1": 0,
      "range_ps": null,
      "n_wns": 1
    }
  },
  "gcd_bar_ps": 25.0,
  "ibex_bar_ps": 50.0,
  "supported": null,
  "verdict": "I1 incomplete (no Q1 knob finishes yet)"
}
```

## I2_per_design_residual

**Verdict:** I2 incomplete (need Q* holdout after ≥3 calib finishes/design)

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
      "n": 16,
      "mean_ns": -0.05056025,
      "std_ns": 0.023567516623135037
    },
    "ibex": {
      "n": 8,
      "mean_ns": -0.15308242500000002,
      "std_ns": 0.1260051596869946
    },
    "spi": {
      "n": 2,
      "mean_ns": 0.02352949999999998,
      "std_ns": 0.00931047498788322
    }
  },
  "n_holdout": 0,
  "n_inside": 0,
  "coverage": null,
  "bar": 0.8,
  "holdout": [],
  "supported": null,
  "verdict": "I2 incomplete (need Q* holdout after \u22653 calib finishes/design)"
}
```

## I3_stop_precision

**Verdict:** I3 incomplete (no verified Q2 control_negative finishes)

```json
{
  "n_verified": 0,
  "n_lose": 0,
  "precision": null,
  "bar": 0.8,
  "rows": [],
  "supported": null,
  "verdict": "I3 incomplete (no verified Q2 control_negative finishes)"
}
```

## I4_area_regime

**Verdict:** I4 incomplete (no Q1/Q2/Q4 area-regime candidates)

```json
{
  "n_candidates": 0,
  "hits": [],
  "area_frac": 0.1,
  "supported": null,
  "verdict": "I4 incomplete (no Q1/Q2/Q4 area-regime candidates)"
}
```

## I5_proxy_correlation

**Verdict:** I5 supported (place Spearman 0.978 ≥ 0.6; F1 Spearman 0.866)

```json
{
  "n_place_pairs": 28,
  "n_f1_pairs": 3,
  "place_spearman": 0.9781061850027368,
  "f1_spearman": 0.8660254037844387,
  "bar": 0.6,
  "min_n": 8,
  "supported": true,
  "verdict": "I5 supported (place Spearman 0.978 \u2265 0.6; F1 Spearman 0.866)"
}
```

## gate_diagnostics

**Verdict:** gate FP=7 FN=0 precision=0.000 (0 product-wins among 16 challengers)

```json
{
  "n_challengers": 16,
  "n_promoted": 7,
  "n_real_wins": 0,
  "tp": 0,
  "fp": 7,
  "fn": 0,
  "tn": 9,
  "precision": 0.0,
  "recall": null,
  "verdict": "gate FP=7 FN=0 precision=0.000 (0 product-wins among 16 challengers)"
}
```

