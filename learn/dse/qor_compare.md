# QoR compare — reference flow vs challengers

Plan sha: `cf02fb91ed5b757ba057354b2f53cb18a75586e7cf7ccf895369767436f76c98`
Experiments: 58 (49 done)
**Verdict:** QoR vs base: 12 reference slots, 29 challengers, 29 with IR, 29 with GRT WL, 4 §5 wins

Absolute numbers for the ORFS `base` (or historical `flowlab`) reference are in the first table and as the first row of each design@clock group. IR is worst VDD drop from `6_report` (mV). WL is GRT wirelength from `5_1_grt.json` — these ORFS logs have no overflow fraction, only WL (congestion_*_s keys are runtimes).

§5 win stays WNS / WNS+area / first-to-close. IR and WL are extra axes.

### Reference flow (absolute, one row per design@clock)

| Design | Clock ns | Reference variant | WNS ps | TNS ns | Area µm² | Power mW | Leak µW | IR mV | GRT WL | fmax MHz | setup viol |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aes | 0.820 | `camp_aes_base` | -8.9 | -0.024 | 19921.3 | 315.081 | 493.36 | 81.28 | 352701 | 1206.4 | 5 |
| dynamic_node | 6.000 | `camp_dynamic_node_base` | 3353.8 | 0.000 | 22540.0 | 8.765 | 429.78 | 1.78 | 259047 | 377.9 | 0 |
| gcd | 0.400 | `camp_gcd_clk040_a` | -85.8 | -2.479 | 908.4 | 4.213 | 23.93 | 10.83 | 7381 | 2058.4 | 46 |
| gcd | 0.460 | `camp_gcd_base` | -37.2 | -0.595 | 940.3 | 3.932 | 25.64 | 6.67 | 7589 | 2011.4 | 38 |
| gcd | 0.550 | `camp_gcd_clk055_a` | 13.4 | 0.000 | 696.7 | 2.210 | 16.52 | 3.44 | 6369 | 1863.4 | 0 |
| gcd | 0.700 | `camp_gcd_clk070_a` | 128.2 | 0.000 | 682.6 | 1.705 | 15.92 | 3.13 | 6346 | 1748.8 | 0 |
| gcd | 0.900 | `camp_gcd_clk090_a` | 289.1 | 0.000 | 683.1 | 1.335 | 15.93 | 2.96 | 6446 | 1636.8 | 0 |
| ibex | 1.980 | `camp_ibex_clk198_a` | -23.1 | -0.033 | 30879.4 | 120.508 | 694.93 | 95.41 | 441009 | 499.2 | 4 |
| ibex | 2.200 | `camp_ibex_base` | 22.4 | 0.000 | 30735.2 | 107.868 | 688.21 | 123.77 | 438851 | 459.2 | 0 |
| ibex | 2.750 | `camp_ibex_clk275_a` | 285.0 | 0.000 | 30707.3 | 86.457 | 685.80 | 76.31 | 440282 | 405.7 | 0 |
| ibex | 3.520 | `camp_ibex_clk352_a` | 806.7 | 0.000 | 30683.1 | 67.642 | 684.74 | 62.18 | 440701 | 368.6 | 0 |
| spi | 1.000 | `camp_spi_base` | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 2257 | 2578.9 | 0 |

### All flows (reference + challengers, absolute values)

| Design | Clock ns | Flow | Role | §5 | WNS ps | TNS ns | Area µm² | Power mW | Leak µW | IR mV | GRT WL | fmax MHz | setup viol |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aes | 0.820 | `camp_aes_base` | reference | — | -8.9 | -0.024 | 19921.3 | 315.081 | 493.36 | 81.28 | 352701 | 1206.4 | 5 |
| dynamic_node | 6.000 | `camp_dynamic_node_base` | reference | — | 3353.8 | 0.000 | 22540.0 | 8.765 | 429.78 | 1.78 | 259047 | 377.9 | 0 |
| gcd | 0.400 | `camp_gcd_clk040_a` | reference | — | -85.8 | -2.479 | 908.4 | 4.213 | 23.93 | 10.83 | 7381 | 2058.4 | 46 |
| gcd | 0.400 | `camp_gcd_clk040_b` | challenger | lose | -389.7 | -15.483 | 631.5 | 2.903 | 15.34 | 5.51 | 4545 | 1266.4 | 47 |
| gcd | 0.400 | `camp_gcd_clk040_c` | challenger | lose | -234.8 | -7.769 | 919.3 | 6.101 | 23.89 | 10.62 | 8088 | 1575.3 | 48 |
| gcd | 0.460 | `camp_gcd_base` | reference | — | -37.2 | -0.595 | 940.3 | 3.932 | 25.64 | 6.67 | 7589 | 2011.4 | 38 |
| gcd | 0.460 | `camp_gcd_q1_d25u35` | challenger | win | -38.4 | -0.354 | 841.6 | 3.434 | 22.03 | 6.15 | 6971 | 2006.4 | 11 |
| gcd | 0.460 | `camp_gcd_dse_fast` | challenger | lose | -186.9 | -5.981 | 963.5 | 5.527 | 25.02 | 8.26 | 7814 | 1545.9 | 46 |
| gcd | 0.460 | `camp_gcd_dse_fixedb` | challenger | lose | -349.5 | -13.025 | 635.5 | 2.539 | 15.15 | 4.70 | 5038 | 1235.3 | 46 |
| gcd | 0.460 | `camp_gcd_dse_small` | challenger | lose | -338.3 | -13.090 | 609.9 | 2.428 | 14.53 | 3.33 | 4465 | 1252.7 | 46 |
| gcd | 0.460 | `camp_gcd_q1_d15u25` | challenger | lose | -44.4 | -0.344 | 874.3 | 3.631 | 22.98 | 4.95 | 7506 | 1982.5 | 12 |
| gcd | 0.460 | `camp_gcd_q1_d15u35` | challenger | lose | -43.7 | -0.744 | 981.3 | 3.995 | 27.29 | 6.76 | 7660 | 1985.3 | 43 |
| gcd | 0.460 | `camp_gcd_q1_d15u45` | challenger | tie | -36.0 | -0.308 | 861.8 | 3.481 | 22.99 | 10.05 | 6631 | 2016.2 | 11 |
| gcd | 0.460 | `camp_gcd_q1_d20u25` | challenger | tie | -36.3 | -0.886 | 952.8 | 3.860 | 25.89 | 4.11 | 7928 | 2015.0 | 45 |
| gcd | 0.460 | `camp_gcd_q1_d20u45` | challenger | tie | -37.7 | -1.040 | 956.5 | 4.016 | 26.05 | 5.72 | 7378 | 2009.3 | 45 |
| gcd | 0.460 | `camp_gcd_q1_d25u25` | challenger | tie | -41.8 | -0.326 | 861.0 | 3.542 | 22.56 | 4.93 | 7216 | 1992.9 | 12 |
| gcd | 0.460 | `camp_gcd_q1_d25u45` | challenger | tie | -38.1 | -0.584 | 860.8 | 3.545 | 22.79 | 6.87 | 6882 | 2007.6 | 42 |
| gcd | 0.550 | `camp_gcd_clk055_a` | reference | — | 13.4 | 0.000 | 696.7 | 2.210 | 16.52 | 3.44 | 6369 | 1863.4 | 0 |
| gcd | 0.550 | `camp_gcd_clk055_b` | challenger | lose | -251.2 | -9.079 | 611.0 | 2.033 | 14.35 | 5.05 | 4594 | 1248.2 | 43 |
| gcd | 0.550 | `camp_gcd_clk055_c` | challenger | lose | -109.3 | -1.409 | 799.6 | 3.783 | 19.40 | 6.86 | 7800 | 1516.9 | 39 |
| gcd | 0.550 | `camp_gcd_q4_d25u35_c055` | challenger | tie | 13.0 | 0.000 | 697.7 | 2.217 | 16.57 | 3.43 | 6309 | 1862.3 | 0 |
| gcd | 0.700 | `camp_gcd_clk070_a` | reference | — | 128.2 | 0.000 | 682.6 | 1.705 | 15.92 | 3.13 | 6346 | 1748.8 | 0 |
| gcd | 0.700 | `camp_gcd_clk070_b` | challenger | lose | -128.3 | -3.498 | 582.8 | 1.534 | 13.62 | 2.45 | 4118 | 1207.3 | 39 |
| gcd | 0.700 | `camp_gcd_clk070_c` | challenger | lose | 3.3 | 0.000 | 702.2 | 2.486 | 16.08 | 3.55 | 7164 | 1435.3 | 0 |
| gcd | 0.900 | `camp_gcd_clk090_a` | reference | — | 289.1 | 0.000 | 683.1 | 1.335 | 15.93 | 2.96 | 6446 | 1636.8 | 0 |
| gcd | 0.900 | `camp_gcd_clk090_b` | challenger | lose | 4.7 | 0.000 | 518.7 | 1.039 | 11.59 | 2.32 | 4004 | 1116.9 | 0 |
| gcd | 0.900 | `camp_gcd_clk090_c` | challenger | lose | 121.6 | 0.000 | 676.7 | 1.820 | 15.12 | 2.61 | 6857 | 1284.7 | 0 |
| ibex | 1.980 | `camp_ibex_clk198_a` | reference | — | -23.1 | -0.033 | 30879.4 | 120.508 | 694.93 | 95.41 | 441009 | 499.2 | 4 |
| ibex | 1.980 | `camp_ibex_clk198_s` | challenger | lose | -61.1 | -7.110 | 33052.1 | 117.855 | 727.21 | 65.97 | 432835 | 489.9 | 301 |
| ibex | 2.200 | `camp_ibex_base` | reference | — | 22.4 | 0.000 | 30735.2 | 107.868 | 688.21 | 123.77 | 438851 | 459.2 | 0 |
| ibex | 2.200 | `camp_ibex_q1_d15u50` | challenger | win | 36.2 | 0.000 | 30748.3 | 107.922 | 688.40 | 125.04 | 445041 | 462.2 | 0 |
| ibex | 2.200 | `camp_ibex_q1_d20u60` | challenger | win | 42.3 | 0.000 | 30686.0 | 107.499 | 688.06 | 86.24 | 420930 | 463.5 | 0 |
| ibex | 2.200 | `camp_ibex_q1_d25u50` | challenger | win | 39.9 | 0.000 | 30711.0 | 107.344 | 687.50 | 116.96 | 432786 | 462.9 | 0 |
| ibex | 2.200 | `camp_ibex_abcspeed` | challenger | tie | 20.4 | 0.000 | 30575.4 | 90.815 | 640.35 | 49.13 | 422381 | 458.8 | 0 |
| ibex | 2.200 | `camp_ibex_q1_d20u40` | challenger | lose | 16.1 | 0.000 | 30776.7 | 108.105 | 688.77 | 71.23 | 460215 | 457.9 | 0 |
| ibex | 2.750 | `camp_ibex_clk275_a` | reference | — | 285.0 | 0.000 | 30707.3 | 86.457 | 685.80 | 76.31 | 440282 | 405.7 | 0 |
| ibex | 2.750 | `camp_ibex_clk275_s` | challenger | lose | 166.3 | 0.000 | 30065.2 | 70.620 | 621.71 | 26.41 | 417747 | 387.0 | 0 |
| ibex | 3.520 | `camp_ibex_clk352_a` | reference | — | 806.7 | 0.000 | 30683.1 | 67.642 | 684.74 | 62.18 | 440701 | 368.6 | 0 |
| ibex | 3.520 | `camp_ibex_clk352_s` | challenger | lose | 597.2 | 0.000 | 30033.5 | 55.188 | 620.45 | 30.35 | 419434 | 342.1 | 0 |
| spi | 1.000 | `camp_spi_base` | reference | — | 612.2 | 0.000 | 267.6 | 0.301 | 5.32 | 0.98 | 2257 | 2578.9 | 0 |
| spi | 1.000 | `camp_spi_abcspeed` | challenger | lose | 600.8 | 0.000 | 265.7 | 0.313 | 5.80 | 1.06 | 1889 | 2505.0 | 0 |

### Challengers vs the reference in the same slot (Δ)

ΔWNS = cand − reference (ps; + better). Percent columns = 100·(cand−reference)/reference (− better for area/power/leak/IR/WL).

| Design | Clock | Variant | §5 | ΔWNS ps | Δarea % | Δpower % | Δleak % | ΔIR % | ΔWL % | P cand | P ref | IR cand | IR ref | WL cand | WL ref |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gcd | 0.460 | `camp_gcd_dse_small` | lose | -301.13 | -35.13 | -38.26 | -43.36 | -50.08 | -41.16 | 2.428 | 3.932 | 3.33 | 6.67 | 4465 | 7589 |
| gcd | 0.460 | `camp_gcd_dse_fast` | lose | -149.72 | 2.46 | 40.56 | -2.42 | 23.84 | 2.96 | 5.527 | 3.932 | 8.26 | 6.67 | 7814 | 7589 |
| gcd | 0.460 | `camp_gcd_dse_fixedb` | lose | -312.32 | -32.42 | -35.43 | -40.94 | -29.48 | -33.61 | 2.539 | 3.932 | 4.70 | 6.67 | 5038 | 7589 |
| gcd | 0.400 | `camp_gcd_clk040_b` | lose | -303.84 | -30.48 | -31.10 | -35.91 | -49.07 | -38.42 | 2.903 | 4.213 | 5.51 | 10.83 | 4545 | 7381 |
| gcd | 0.400 | `camp_gcd_clk040_c` | lose | -149.00 | 1.20 | 44.81 | -0.18 | -1.87 | 9.58 | 6.101 | 4.213 | 10.62 | 10.83 | 8088 | 7381 |
| gcd | 0.550 | `camp_gcd_clk055_b` | lose | -264.54 | -12.29 | -8.00 | -13.14 | 46.66 | -27.87 | 2.033 | 2.210 | 5.05 | 3.44 | 4594 | 6369 |
| gcd | 0.550 | `camp_gcd_clk055_c` | lose | -122.61 | 14.78 | 71.23 | 17.42 | 99.49 | 22.47 | 3.783 | 2.210 | 6.86 | 3.44 | 7800 | 6369 |
| gcd | 0.700 | `camp_gcd_clk070_b` | lose | -256.48 | -14.61 | -10.03 | -14.41 | -21.85 | -35.11 | 1.534 | 1.705 | 2.45 | 3.13 | 4118 | 6346 |
| gcd | 0.700 | `camp_gcd_clk070_c` | lose | -124.89 | 2.88 | 45.86 | 1.01 | 13.24 | 12.89 | 2.486 | 1.705 | 3.55 | 3.13 | 7164 | 6346 |
| gcd | 0.900 | `camp_gcd_clk090_b` | lose | -284.37 | -24.07 | -22.18 | -27.24 | -21.62 | -37.88 | 1.039 | 1.335 | 2.32 | 2.96 | 4004 | 6446 |
| gcd | 0.900 | `camp_gcd_clk090_c` | lose | -167.44 | -0.93 | 36.36 | -5.05 | -12.06 | 6.38 | 1.820 | 1.335 | 2.61 | 2.96 | 6857 | 6446 |
| spi | 1.000 | `camp_spi_abcspeed` | lose | -11.43 | -0.70 | 3.93 | 9.05 | 8.38 | -16.30 | 0.313 | 0.301 | 1.06 | 0.98 | 1889 | 2257 |
| ibex | 2.200 | `camp_ibex_abcspeed` | tie | -2.02 | -0.52 | -15.81 | -6.95 | -60.31 | -3.75 | 90.815 | 107.868 | 49.13 | 123.77 | 422381 | 438851 |
| ibex | 1.980 | `camp_ibex_clk198_s` | lose | -37.97 | 7.04 | -2.20 | 4.65 | -30.86 | -1.85 | 117.855 | 120.508 | 65.97 | 95.41 | 432835 | 441009 |
| ibex | 2.750 | `camp_ibex_clk275_s` | lose | -118.73 | -2.09 | -18.32 | -9.35 | -65.39 | -5.12 | 70.620 | 86.457 | 26.41 | 76.31 | 417747 | 440282 |
| ibex | 3.520 | `camp_ibex_clk352_s` | lose | -209.54 | -2.12 | -18.41 | -9.39 | -51.20 | -4.83 | 55.188 | 67.642 | 30.35 | 62.18 | 419434 | 440701 |
| gcd | 0.460 | `camp_gcd_q1_d15u25` | lose | -7.24 | -7.02 | -7.67 | -10.40 | -25.74 | -1.09 | 3.631 | 3.932 | 4.95 | 6.67 | 7506 | 7589 |
| gcd | 0.460 | `camp_gcd_q1_d15u35` | lose | -6.53 | 4.36 | 1.60 | 6.40 | 1.47 | 0.94 | 3.995 | 3.932 | 6.76 | 6.67 | 7660 | 7589 |
| gcd | 0.460 | `camp_gcd_q1_d15u45` | tie | 1.19 | -8.35 | -11.48 | -10.36 | 50.74 | -12.62 | 3.481 | 3.932 | 10.05 | 6.67 | 6631 | 7589 |
| gcd | 0.460 | `camp_gcd_q1_d20u25` | tie | 0.89 | 1.33 | -1.84 | 0.96 | -38.32 | 4.47 | 3.860 | 3.932 | 4.11 | 6.67 | 7928 | 7589 |
| gcd | 0.460 | `camp_gcd_q1_d20u45` | tie | -0.51 | 1.73 | 2.11 | 1.60 | -14.27 | -2.78 | 4.016 | 3.932 | 5.72 | 6.67 | 7378 | 7589 |
| gcd | 0.460 | `camp_gcd_q1_d25u25` | tie | -4.62 | -8.43 | -9.94 | -12.03 | -26.09 | -4.92 | 3.542 | 3.932 | 4.93 | 6.67 | 7216 | 7589 |
| gcd | 0.460 | `camp_gcd_q1_d25u35` | win | -1.23 | -10.50 | -12.67 | -14.11 | -7.69 | -8.14 | 3.434 | 3.932 | 6.15 | 6.67 | 6971 | 7589 |
| gcd | 0.460 | `camp_gcd_q1_d25u45` | tie | -0.94 | -8.46 | -9.86 | -11.14 | 3.11 | -9.32 | 3.545 | 3.932 | 6.87 | 6.67 | 6882 | 7589 |
| ibex | 2.200 | `camp_ibex_q1_d15u50` | win | 13.81 | 0.04 | 0.05 | 0.03 | 1.02 | 1.41 | 107.922 | 107.868 | 125.04 | 123.77 | 445041 | 438851 |
| ibex | 2.200 | `camp_ibex_q1_d25u50` | win | 17.48 | -0.08 | -0.49 | -0.10 | -5.50 | -1.38 | 107.344 | 107.868 | 116.96 | 123.77 | 432786 | 438851 |
| ibex | 2.200 | `camp_ibex_q1_d20u40` | lose | -6.30 | 0.14 | 0.22 | 0.08 | -42.45 | 4.87 | 108.105 | 107.868 | 71.23 | 123.77 | 460215 | 438851 |
| ibex | 2.200 | `camp_ibex_q1_d20u60` | win | 19.94 | -0.16 | -0.34 | -0.02 | -30.33 | -4.08 | 107.499 | 107.868 | 86.24 | 123.77 | 420930 | 438851 |
| gcd | 0.550 | `camp_gcd_q4_d25u35_c055` | tie | -0.33 | 0.15 | 0.35 | 0.26 | -0.31 | -0.94 | 2.217 | 2.210 | 3.43 | 3.44 | 6309 | 6369 |

### Side-by-side sheets (reference column + each challenger)

#### gcd @ 0.400 ns — reference `camp_gcd_clk040_a`

| Metric | `camp_gcd_clk040_a` | `camp_gcd_clk040_b` | `camp_gcd_clk040_c` |
|---|---|---|---|
| WNS (ps) | -85.8 | -389.7 | -234.8 |
| TNS (ns) | -2.479 | -15.483 | -7.769 |
| stdcell area (µm²) | 908.4 | 631.5 | 919.3 |
| total power (mW) | 4.213 | 2.903 | 6.101 |
| leakage (µW) | 23.93 | 15.34 | 23.89 |
| IR drop VDD (mV) | 10.83 | 5.51 | 10.62 |
| GRT wirelength | 7381 | 4545 | 8088 |
| fmax (MHz) | 2058.4 | 1266.4 | 1575.3 |
| setup violations | 46 | 47 | 48 |

#### gcd @ 0.460 ns — reference `camp_gcd_base` (1/3)

| Metric | `camp_gcd_base` | `camp_gcd_q1_d25u35` | `camp_gcd_dse_fast` | `camp_gcd_dse_fixedb` | `camp_gcd_dse_small` |
|---|---|---|---|---|---|
| WNS (ps) | -37.2 | -38.4 | -186.9 | -349.5 | -338.3 |
| TNS (ns) | -0.595 | -0.354 | -5.981 | -13.025 | -13.090 |
| stdcell area (µm²) | 940.3 | 841.6 | 963.5 | 635.5 | 609.9 |
| total power (mW) | 3.932 | 3.434 | 5.527 | 2.539 | 2.428 |
| leakage (µW) | 25.64 | 22.03 | 25.02 | 15.15 | 14.53 |
| IR drop VDD (mV) | 6.67 | 6.15 | 8.26 | 4.70 | 3.33 |
| GRT wirelength | 7589 | 6971 | 7814 | 5038 | 4465 |
| fmax (MHz) | 2011.4 | 2006.4 | 1545.9 | 1235.3 | 1252.7 |
| setup violations | 38 | 11 | 46 | 46 | 46 |

#### gcd @ 0.460 ns — reference `camp_gcd_base` (2/3)

| Metric | `camp_gcd_base` | `camp_gcd_q1_d15u25` | `camp_gcd_q1_d15u35` | `camp_gcd_q1_d15u45` | `camp_gcd_q1_d20u25` |
|---|---|---|---|---|---|
| WNS (ps) | -37.2 | -44.4 | -43.7 | -36.0 | -36.3 |
| TNS (ns) | -0.595 | -0.344 | -0.744 | -0.308 | -0.886 |
| stdcell area (µm²) | 940.3 | 874.3 | 981.3 | 861.8 | 952.8 |
| total power (mW) | 3.932 | 3.631 | 3.995 | 3.481 | 3.860 |
| leakage (µW) | 25.64 | 22.98 | 27.29 | 22.99 | 25.89 |
| IR drop VDD (mV) | 6.67 | 4.95 | 6.76 | 10.05 | 4.11 |
| GRT wirelength | 7589 | 7506 | 7660 | 6631 | 7928 |
| fmax (MHz) | 2011.4 | 1982.5 | 1985.3 | 2016.2 | 2015.0 |
| setup violations | 38 | 12 | 43 | 11 | 45 |

#### gcd @ 0.460 ns — reference `camp_gcd_base` (3/3)

| Metric | `camp_gcd_base` | `camp_gcd_q1_d20u45` | `camp_gcd_q1_d25u25` | `camp_gcd_q1_d25u45` |
|---|---|---|---|---|
| WNS (ps) | -37.2 | -37.7 | -41.8 | -38.1 |
| TNS (ns) | -0.595 | -1.040 | -0.326 | -0.584 |
| stdcell area (µm²) | 940.3 | 956.5 | 861.0 | 860.8 |
| total power (mW) | 3.932 | 4.016 | 3.542 | 3.545 |
| leakage (µW) | 25.64 | 26.05 | 22.56 | 22.79 |
| IR drop VDD (mV) | 6.67 | 5.72 | 4.93 | 6.87 |
| GRT wirelength | 7589 | 7378 | 7216 | 6882 |
| fmax (MHz) | 2011.4 | 2009.3 | 1992.9 | 2007.6 |
| setup violations | 38 | 45 | 12 | 42 |

#### gcd @ 0.550 ns — reference `camp_gcd_clk055_a`

| Metric | `camp_gcd_clk055_a` | `camp_gcd_clk055_b` | `camp_gcd_clk055_c` | `camp_gcd_q4_d25u35_c055` |
|---|---|---|---|---|
| WNS (ps) | 13.4 | -251.2 | -109.3 | 13.0 |
| TNS (ns) | 0.000 | -9.079 | -1.409 | 0.000 |
| stdcell area (µm²) | 696.7 | 611.0 | 799.6 | 697.7 |
| total power (mW) | 2.210 | 2.033 | 3.783 | 2.217 |
| leakage (µW) | 16.52 | 14.35 | 19.40 | 16.57 |
| IR drop VDD (mV) | 3.44 | 5.05 | 6.86 | 3.43 |
| GRT wirelength | 6369 | 4594 | 7800 | 6309 |
| fmax (MHz) | 1863.4 | 1248.2 | 1516.9 | 1862.3 |
| setup violations | 0 | 43 | 39 | 0 |

#### gcd @ 0.700 ns — reference `camp_gcd_clk070_a`

| Metric | `camp_gcd_clk070_a` | `camp_gcd_clk070_b` | `camp_gcd_clk070_c` |
|---|---|---|---|
| WNS (ps) | 128.2 | -128.3 | 3.3 |
| TNS (ns) | 0.000 | -3.498 | 0.000 |
| stdcell area (µm²) | 682.6 | 582.8 | 702.2 |
| total power (mW) | 1.705 | 1.534 | 2.486 |
| leakage (µW) | 15.92 | 13.62 | 16.08 |
| IR drop VDD (mV) | 3.13 | 2.45 | 3.55 |
| GRT wirelength | 6346 | 4118 | 7164 |
| fmax (MHz) | 1748.8 | 1207.3 | 1435.3 |
| setup violations | 0 | 39 | 0 |

#### gcd @ 0.900 ns — reference `camp_gcd_clk090_a`

| Metric | `camp_gcd_clk090_a` | `camp_gcd_clk090_b` | `camp_gcd_clk090_c` |
|---|---|---|---|
| WNS (ps) | 289.1 | 4.7 | 121.6 |
| TNS (ns) | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 683.1 | 518.7 | 676.7 |
| total power (mW) | 1.335 | 1.039 | 1.820 |
| leakage (µW) | 15.93 | 11.59 | 15.12 |
| IR drop VDD (mV) | 2.96 | 2.32 | 2.61 |
| GRT wirelength | 6446 | 4004 | 6857 |
| fmax (MHz) | 1636.8 | 1116.9 | 1284.7 |
| setup violations | 0 | 0 | 0 |

#### ibex @ 1.980 ns — reference `camp_ibex_clk198_a`

| Metric | `camp_ibex_clk198_a` | `camp_ibex_clk198_s` |
|---|---|---|
| WNS (ps) | -23.1 | -61.1 |
| TNS (ns) | -0.033 | -7.110 |
| stdcell area (µm²) | 30879.4 | 33052.1 |
| total power (mW) | 120.508 | 117.855 |
| leakage (µW) | 694.93 | 727.21 |
| IR drop VDD (mV) | 95.41 | 65.97 |
| GRT wirelength | 441009 | 432835 |
| fmax (MHz) | 499.2 | 489.9 |
| setup violations | 4 | 301 |

#### ibex @ 2.200 ns — reference `camp_ibex_base` (1/2)

| Metric | `camp_ibex_base` | `camp_ibex_q1_d15u50` | `camp_ibex_q1_d20u60` | `camp_ibex_q1_d25u50` | `camp_ibex_abcspeed` |
|---|---|---|---|---|---|
| WNS (ps) | 22.4 | 36.2 | 42.3 | 39.9 | 20.4 |
| TNS (ns) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| stdcell area (µm²) | 30735.2 | 30748.3 | 30686.0 | 30711.0 | 30575.4 |
| total power (mW) | 107.868 | 107.922 | 107.499 | 107.344 | 90.815 |
| leakage (µW) | 688.21 | 688.40 | 688.06 | 687.50 | 640.35 |
| IR drop VDD (mV) | 123.77 | 125.04 | 86.24 | 116.96 | 49.13 |
| GRT wirelength | 438851 | 445041 | 420930 | 432786 | 422381 |
| fmax (MHz) | 459.2 | 462.2 | 463.5 | 462.9 | 458.8 |
| setup violations | 0 | 0 | 0 | 0 | 0 |

#### ibex @ 2.200 ns — reference `camp_ibex_base` (2/2)

| Metric | `camp_ibex_base` | `camp_ibex_q1_d20u40` |
|---|---|---|
| WNS (ps) | 22.4 | 16.1 |
| TNS (ns) | 0.000 | 0.000 |
| stdcell area (µm²) | 30735.2 | 30776.7 |
| total power (mW) | 107.868 | 108.105 |
| leakage (µW) | 688.21 | 688.77 |
| IR drop VDD (mV) | 123.77 | 71.23 |
| GRT wirelength | 438851 | 460215 |
| fmax (MHz) | 459.2 | 457.9 |
| setup violations | 0 | 0 |

#### ibex @ 2.750 ns — reference `camp_ibex_clk275_a`

| Metric | `camp_ibex_clk275_a` | `camp_ibex_clk275_s` |
|---|---|---|
| WNS (ps) | 285.0 | 166.3 |
| TNS (ns) | 0.000 | 0.000 |
| stdcell area (µm²) | 30707.3 | 30065.2 |
| total power (mW) | 86.457 | 70.620 |
| leakage (µW) | 685.80 | 621.71 |
| IR drop VDD (mV) | 76.31 | 26.41 |
| GRT wirelength | 440282 | 417747 |
| fmax (MHz) | 405.7 | 387.0 |
| setup violations | 0 | 0 |

#### ibex @ 3.520 ns — reference `camp_ibex_clk352_a`

| Metric | `camp_ibex_clk352_a` | `camp_ibex_clk352_s` |
|---|---|---|
| WNS (ps) | 806.7 | 597.2 |
| TNS (ns) | 0.000 | 0.000 |
| stdcell area (µm²) | 30683.1 | 30033.5 |
| total power (mW) | 67.642 | 55.188 |
| leakage (µW) | 684.74 | 620.45 |
| IR drop VDD (mV) | 62.18 | 30.35 |
| GRT wirelength | 440701 | 419434 |
| fmax (MHz) | 368.6 | 342.1 |
| setup violations | 0 | 0 |

#### spi @ 1.000 ns — reference `camp_spi_base`

| Metric | `camp_spi_base` | `camp_spi_abcspeed` |
|---|---|---|
| WNS (ps) | 612.2 | 600.8 |
| TNS (ns) | 0.000 | 0.000 |
| stdcell area (µm²) | 267.6 | 265.7 |
| total power (mW) | 0.301 | 0.313 |
| leakage (µW) | 5.32 | 5.80 |
| IR drop VDD (mV) | 0.98 | 1.06 |
| GRT wirelength | 2257 | 1889 |
| fmax (MHz) | 2578.9 | 2505.0 |
| setup violations | 0 | 0 |
