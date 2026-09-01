# Campaign eval vs frozen H1–H6

Plan sha: `a9446c2103c5eca2126a50daa9272fe481e5f6bb6a390af6a21e0a5bbae7fbc3`
Experiments: 5 (5 done)

Win criteria are **frozen**. This script does not retune them.

## H1_proxy_inversion

**Verdict:** H1 supported on gcd

```json
{
  "designs": {
    "gcd": {
      "n": 4,
      "finish_rank": [
        "camp_gcd_base",
        "camp_gcd_dse_fast",
        "camp_gcd_dse_small",
        "camp_gcd_dse_fixedb"
      ],
      "proxy_rank": [
        "camp_gcd_dse_fast",
        "camp_gcd_dse_small",
        "camp_gcd_dse_fixedb"
      ],
      "finish_best": "camp_gcd_base",
      "proxy_best": "camp_gcd_dse_fast",
      "inverted": true,
      "finish_wns_ps": {
        "camp_gcd_base": -37.167,
        "camp_gcd_dse_fast": -186.887,
        "camp_gcd_dse_small": -338.30100000000004,
        "camp_gcd_dse_fixedb": -349.488
      }
    }
  },
  "supported": true,
  "inverted": [
    "gcd"
  ],
  "verdict": "H1 supported on gcd"
}
```

## H2_place_dp_gate

**Verdict:** H2 incomplete (n=4 < 15)

```json
{
  "n": 4,
  "n_promoted": 1,
  "n_real_wins": 0,
  "precision": 1.0,
  "recall": null,
  "gate_place_wns_ns": 0.0,
  "worst_promoted_base_wns_ns": -0.037167,
  "min_n": 15,
  "bar": {
    "precision": 0.8,
    "recall": 0.8
  },
  "enough_n": false,
  "pass": false,
  "verdict": "H2 incomplete (n=4 < 15)"
}
```

## H3_small_when_clock_relaxes

**Verdict:** H3 incomplete (nobody timing-closed yet)

```json
{
  "points": [
    {
      "sdc_ns": "0.460",
      "closed": [],
      "winner": null,
      "small_wins_area": null
    }
  ],
  "any_timing_closed": false,
  "verdict": "H3 incomplete (nobody timing-closed yet)"
}
```

## H4_dse_value_vs_size

**Verdict:** H4 incomplete (need ≥3 designs with base+DSE finish)

```json
{
  "rows": [
    {
      "design": "gcd",
      "n_instances": 680,
      "base_wns_ps": -37.167,
      "best_dse_variant": "camp_gcd_dse_fast",
      "best_dse_wns_ps": -186.887,
      "delta_wns_ps": -149.72
    }
  ],
  "monotonic_growing_delta": null,
  "verdict": "H4 incomplete (need \u22653 designs with base+DSE finish)"
}
```

## H5_place_finish_residual

**Verdict:** H5 incomplete (need gcd + ≥1 other design with place+finish)

```json
{
  "n": 4,
  "residuals": [
    {
      "variant": "camp_gcd_base",
      "design": "gcd",
      "residual_ns": -0.0494805
    },
    {
      "variant": "camp_gcd_dse_small",
      "design": "gcd",
      "residual_ns": -0.02473700000000001
    },
    {
      "variant": "camp_gcd_dse_fast",
      "design": "gcd",
      "residual_ns": -0.07017899999999999
    },
    {
      "variant": "camp_gcd_dse_fixedb",
      "design": "gcd",
      "residual_ns": -0.031952000000000036
    }
  ],
  "gcd_mean_residual_ns": -0.044087125000000005,
  "gcd_std_residual_ns": 0.0202613180814041,
  "other_means_ns": {},
  "outlier_frac": 0.0,
  "transfer_ok": null,
  "verdict": "H5 incomplete (need gcd + \u22651 other design with place+finish)"
}
```

## H6_oven_deterministic

**Verdict:** H6 supported (A-injected bit-identical on all pairs)

```json
{
  "pairs": [
    {
      "design": "gcd",
      "base_variant": "camp_gcd_base",
      "ainj_variant": "camp_gcd_ainj",
      "report_sha_match": true,
      "wns_match": true,
      "match": true,
      "base_report_sha": "5cba9a7a882a0420cfd6f3b121dc078244f86e79893963d3726ab53fb26bd543",
      "ainj_report_sha": "5cba9a7a882a0420cfd6f3b121dc078244f86e79893963d3726ab53fb26bd543"
    }
  ],
  "all_match": true,
  "verdict": "H6 supported (A-injected bit-identical on all pairs)"
}
```

