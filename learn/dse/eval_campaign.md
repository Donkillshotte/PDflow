# Campaign eval vs frozen H1–H6

Plan sha: `a9446c2103c5eca2126a50daa9272fe481e5f6bb6a390af6a21e0a5bbae7fbc3`
Experiments: 25 (25 done)

Win criteria are **frozen**. This script does not retune them.

## H1_proxy_inversion

**Verdict:** H1 supported on gcd@0.460

```json
{
  "slots": {
    "aes@0.820": {
      "n": 1,
      "finish_rank": [
        "camp_aes_base"
      ],
      "proxy_rank": null,
      "finish_best": "camp_aes_base",
      "proxy_best": null,
      "inverted": null,
      "finish_wns_ps": {
        "camp_aes_base": -8.92109
      }
    },
    "dynamic_node@6.000": {
      "n": 1,
      "finish_rank": [
        "camp_dynamic_node_base"
      ],
      "proxy_rank": null,
      "finish_best": "camp_dynamic_node_base",
      "proxy_best": null,
      "inverted": null,
      "finish_wns_ps": {
        "camp_dynamic_node_base": 3353.83
      }
    },
    "gcd@0.400": {
      "n": 3,
      "finish_rank": [
        "camp_gcd_clk040_a",
        "camp_gcd_clk040_c",
        "camp_gcd_clk040_b"
      ],
      "proxy_rank": null,
      "finish_best": "camp_gcd_clk040_a",
      "proxy_best": null,
      "inverted": null,
      "finish_wns_ps": {
        "camp_gcd_clk040_a": -85.81410000000001,
        "camp_gcd_clk040_c": -234.81199999999998,
        "camp_gcd_clk040_b": -389.651
      }
    },
    "gcd@0.460": {
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
    },
    "gcd@0.550": {
      "n": 3,
      "finish_rank": [
        "camp_gcd_clk055_a",
        "camp_gcd_clk055_c",
        "camp_gcd_clk055_b"
      ],
      "proxy_rank": null,
      "finish_best": "camp_gcd_clk055_a",
      "proxy_best": null,
      "inverted": null,
      "finish_wns_ps": {
        "camp_gcd_clk055_a": 13.3553,
        "camp_gcd_clk055_c": -109.252,
        "camp_gcd_clk055_b": -251.18099999999998
      }
    },
    "gcd@0.700": {
      "n": 3,
      "finish_rank": [
        "camp_gcd_clk070_a",
        "camp_gcd_clk070_c",
        "camp_gcd_clk070_b"
      ],
      "proxy_rank": null,
      "finish_best": "camp_gcd_clk070_a",
      "proxy_best": null,
      "inverted": null,
      "finish_wns_ps": {
        "camp_gcd_clk070_a": 128.182,
        "camp_gcd_clk070_c": 3.2915900000000002,
        "camp_gcd_clk070_b": -128.302
      }
    },
    "gcd@0.900": {
      "n": 3,
      "finish_rank": [
        "camp_gcd_clk090_a",
        "camp_gcd_clk090_c",
        "camp_gcd_clk090_b"
      ],
      "proxy_rank": null,
      "finish_best": "camp_gcd_clk090_a",
      "proxy_best": null,
      "inverted": null,
      "finish_wns_ps": {
        "camp_gcd_clk090_a": 289.059,
        "camp_gcd_clk090_c": 121.619,
        "camp_gcd_clk090_b": 4.68631
      }
    },
    "ibex@2.200": {
      "n": 1,
      "finish_rank": [
        "camp_ibex_base"
      ],
      "proxy_rank": null,
      "finish_best": "camp_ibex_base",
      "proxy_best": null,
      "inverted": null,
      "finish_wns_ps": {
        "camp_ibex_base": 22.4143
      }
    },
    "spi@1.000": {
      "n": 1,
      "finish_rank": [
        "camp_spi_base"
      ],
      "proxy_rank": null,
      "finish_best": "camp_spi_base",
      "proxy_best": null,
      "inverted": null,
      "finish_wns_ps": {
        "camp_spi_base": 612.2339999999999
      }
    }
  },
  "supported": true,
  "inverted": [
    "gcd@0.460"
  ],
  "inverted_designs": [
    "gcd"
  ],
  "verdict": "H1 supported on gcd@0.460"
}
```

## H2_place_dp_gate

**Verdict:** H2 incomplete (no product-wins vs same-clock base; recall N/A)

```json
{
  "n": 20,
  "n_promoted": 11,
  "n_real_wins": 0,
  "precision": 0.7272727272727273,
  "recall": null,
  "gate_place_wns_ns": 0.0,
  "min_n": 15,
  "bar": {
    "precision": 0.8,
    "recall": 0.8
  },
  "enough_n": true,
  "pass": false,
  "verdict": "H2 incomplete (no product-wins vs same-clock base; recall N/A)"
}
```

## H3_small_when_clock_relaxes

**Verdict:** H3 not supported (A closes first; B area win <25% bar)

```json
{
  "points": [
    {
      "sdc_ns": "0.400",
      "closed": [],
      "winner": null,
      "small_wins_area": null
    },
    {
      "sdc_ns": "0.460",
      "closed": [],
      "winner": null,
      "small_wins_area": null
    },
    {
      "sdc_ns": "0.550",
      "closed": [
        "camp_gcd_clk055_a"
      ],
      "winner": "camp_gcd_clk055_a",
      "winner_role": "base",
      "winner_area": 696.654,
      "small_wins_area": false,
      "b_closed_a_open": false
    },
    {
      "sdc_ns": "0.700",
      "closed": [
        "camp_gcd_clk070_a",
        "camp_gcd_clk070_c"
      ],
      "winner": "camp_gcd_clk070_a",
      "winner_role": "base",
      "winner_area": 682.556,
      "small_wins_area": false,
      "b_closed_a_open": false
    },
    {
      "sdc_ns": "0.900",
      "closed": [
        "camp_gcd_clk090_b",
        "camp_gcd_clk090_c",
        "camp_gcd_clk090_a"
      ],
      "winner": "camp_gcd_clk090_b",
      "winner_role": "dse_small",
      "winner_area": 518.7,
      "small_wins_area": false,
      "b_closed_a_open": false
    }
  ],
  "any_timing_closed": true,
  "h3_hit": false,
  "verdict": "H3 not supported (A closes first; B area win <25% bar)"
}
```

## H4_dse_value_vs_size

**Verdict:** H4 incomplete (need ≥3 designs with P0 base+DSE finish)

```json
{
  "rows": [
    {
      "design": "gcd",
      "n_instances": 680,
      "clock_ns": 0.46,
      "base_wns_ps": -37.167,
      "best_dse_variant": "camp_gcd_dse_fast",
      "best_dse_wns_ps": -186.887,
      "delta_wns_ps": -149.72
    }
  ],
  "monotonic_growing_delta": null,
  "verdict": "H4 incomplete (need \u22653 designs with P0 base+DSE finish)"
}
```

## H5_place_finish_residual

**Verdict:** H5 supported (≤30% residuals outside gcd ±2σ)

```json
{
  "n": 20,
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
    },
    {
      "variant": "camp_spi_base",
      "design": "spi",
      "residual_ns": 0.030112999999999945
    },
    {
      "variant": "camp_dynamic_node_base",
      "design": "dynamic_node",
      "residual_ns": -0.24974000000000007
    },
    {
      "variant": "camp_ibex_base",
      "design": "ibex",
      "residual_ns": -0.2388377
    },
    {
      "variant": "camp_aes_base",
      "design": "aes",
      "residual_ns": -0.012051029999999999
    },
    {
      "variant": "camp_gcd_clk040_a",
      "design": "gcd",
      "residual_ns": -0.0535522
    },
    {
      "variant": "camp_gcd_clk040_b",
      "design": "gcd",
      "residual_ns": -0.01916100000000004
    },
    {
      "variant": "camp_gcd_clk040_c",
      "design": "gcd",
      "residual_ns": -0.07055799999999998
    },
    {
      "variant": "camp_gcd_clk055_a",
      "design": "gcd",
      "residual_ns": -0.0715522
    },
    {
      "variant": "camp_gcd_clk055_b",
      "design": "gcd",
      "residual_ns": -0.026402999999999982
    },
    {
      "variant": "camp_gcd_clk055_c",
      "design": "gcd",
      "residual_ns": -0.0706287
    },
    {
      "variant": "camp_gcd_clk070_a",
      "design": "gcd",
      "residual_ns": -0.07749800000000001
    },
    {
      "variant": "camp_gcd_clk070_b",
      "design": "gcd",
      "residual_ns": -0.038449899999999995
    },
    {
      "variant": "camp_gcd_clk070_c",
      "design": "gcd",
      "residual_ns": -0.037078410000000006
    },
    {
      "variant": "camp_gcd_clk090_a",
      "design": "gcd",
      "residual_ns": -0.07726499999999997
    },
    {
      "variant": "camp_gcd_clk090_b",
      "design": "gcd",
      "residual_ns": -0.01142209
    },
    {
      "variant": "camp_gcd_clk090_c",
      "design": "gcd",
      "residual_ns": -0.079047
    }
  ],
  "gcd_mean_residual_ns": -0.05056025,
  "gcd_std_residual_ns": 0.023567516623135037,
  "other_means_ns": {
    "spi": 0.030112999999999945,
    "dynamic_node": -0.24974000000000007,
    "ibex": -0.2388377,
    "aes": -0.012051029999999999
  },
  "outlier_frac": 0.15,
  "transfer_ok": true,
  "verdict": "H5 supported (\u226430% residuals outside gcd \u00b12\u03c3)"
}
```

## H6_oven_deterministic

**Verdict:** H6 supported (A-injected bit-identical on all pairs)

```json
{
  "pairs": [
    {
      "design": "aes",
      "clock_ns": "0.820",
      "base_variant": "camp_aes_base",
      "ainj_variant": "camp_aes_ainj",
      "report_sha_match": true,
      "wns_match": true,
      "match": true,
      "base_report_sha": "4e2c65002b05830490eacd444b44f45e3d9744292344876cfe858ab7be7f4927",
      "ainj_report_sha": "4e2c65002b05830490eacd444b44f45e3d9744292344876cfe858ab7be7f4927"
    },
    {
      "design": "dynamic_node",
      "clock_ns": "6.000",
      "base_variant": "camp_dynamic_node_base",
      "ainj_variant": "camp_dynamic_node_ainj",
      "report_sha_match": true,
      "wns_match": true,
      "match": true,
      "base_report_sha": "fe663d2db2de75f40263642d079f4451cfc9769c5531f56973479c8e92e66d32",
      "ainj_report_sha": "fe663d2db2de75f40263642d079f4451cfc9769c5531f56973479c8e92e66d32"
    },
    {
      "design": "gcd",
      "clock_ns": "0.460",
      "base_variant": "camp_gcd_base",
      "ainj_variant": "camp_gcd_ainj",
      "report_sha_match": true,
      "wns_match": true,
      "match": true,
      "base_report_sha": "5cba9a7a882a0420cfd6f3b121dc078244f86e79893963d3726ab53fb26bd543",
      "ainj_report_sha": "5cba9a7a882a0420cfd6f3b121dc078244f86e79893963d3726ab53fb26bd543"
    },
    {
      "design": "ibex",
      "clock_ns": "2.200",
      "base_variant": "camp_ibex_base",
      "ainj_variant": "camp_ibex_ainj",
      "report_sha_match": true,
      "wns_match": true,
      "match": true,
      "base_report_sha": "dc42f9418f2dd0a1f0d6d481e25bac26a48c546a1cb0cc370f427fff41462bfc",
      "ainj_report_sha": "dc42f9418f2dd0a1f0d6d481e25bac26a48c546a1cb0cc370f427fff41462bfc"
    },
    {
      "design": "spi",
      "clock_ns": "1.000",
      "base_variant": "camp_spi_base",
      "ainj_variant": "camp_spi_ainj",
      "report_sha_match": true,
      "wns_match": true,
      "match": true,
      "base_report_sha": "b8826a8ee5356ac02056939f64d45349f4f138644f6583ee0c552ac37f2c5656",
      "ainj_report_sha": "b8826a8ee5356ac02056939f64d45349f4f138644f6583ee0c552ac37f2c5656"
    }
  ],
  "all_match": true,
  "verdict": "H6 supported (A-injected bit-identical on all pairs)"
}
```

