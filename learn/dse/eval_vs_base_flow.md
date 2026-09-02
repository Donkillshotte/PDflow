# Evaluation vs ORFS base flow (GCD `flowlab`)

Same exam: ORFS `make finish`, SDC 0.46 ns, tutorial nangate45.
A = baseline **not relaunched**. Ainj / B / Bfix / C are isolated variants.
DSE proxies (F3, mapped area) are **not** finishes. No overwrite of `flowlab`.

## Verdict

A stays. No DSE cook beats ORFS finish WNS. A-injected is bit-identical. B on A's die is still late. Nobody is timing-closed at 0.46 ns.

- A stays: **True**
- A-injected reproduces A (WNS + sha): **True**
- Anyone timing-closed (WNS≥0 at finish): **False**
- Anyone feasible Next Level: **False**
- Funnel would have skipped B/C/Bfix: **True**
- Freeze A intact: **True**
- A constraint-dominates B: **True**; C: **True**
- Pareto feasibility-first: `['A', 'Ainj']`

## Finish vs A

| Cook | Variant | WNS | ΔWNS vs A | TNS | Area | ΔArea | Repair | Die | Place WNS | Funnel | Closed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| A | `flowlab` | -37.2 ps | 0 | -0.595 | 940.3 | 0 | 132 | 1970.0 | +12.3 ps | F6 | False |
| Ainj | `flowlab_dse_ainj` | -37.2 ps | +0.0 ps | -0.595 | 940.3 | +0.0 | 132 | 1970.0 | +12.3 ps | F6 | False |
| B | `flowlab_dse_small` | -338.3 ps | -301.1 ps | -13.090 | 609.9 | -330.4 | 126 | 1304.7 | -313.6 ps | place_wns_-0.3136_below_0.0 | False |
| Bfix | `flowlab_dse_fixedb` | -349.5 ps | -312.3 ps | -13.025 | 635.5 | -304.8 | 129 | 1970.0 | -317.5 ps | place_wns_-0.3175_below_0.0 | False |
| C | `flowlab_dse_fast` | -186.9 ps | -149.7 ps | -5.981 | 963.5 | +23.1 | 198 | 1940.8 | -116.7 ps | place_wns_-0.1167_below_0.0 | False |

## Progressione WNS (floorplan → place → CTS → GRT → finish)

| Cook | FP | Place | CTS | GRT | Finish | Place→finish |
|---|---:|---:|---:|---:|---:|---:|
| A | +43.4 ps | +12.3 ps | -39.6 ps | -48.7 ps | -37.2 ps | -49.5 ps |
| Ainj | +43.4 ps | +12.3 ps | -39.6 ps | -48.7 ps | -37.2 ps | -49.5 ps |
| B | -365.2 ps | -313.6 ps | -348.9 ps | -355.6 ps | -338.3 ps | -24.7 ps |
| Bfix | -365.2 ps | -317.5 ps | -356.4 ps | -367.9 ps | -349.5 ps | -32.0 ps |
| C | -90.3 ps | -116.7 ps | -186.0 ps | -197.5 ps | -186.9 ps | -70.2 ps |

## What DSE *believed* (proxy, not finish)

Memory `memory_flowlab.jsonl`: 140 rows, 137 ok.

- `B_arch` `54142494d890` architecture/F1: area mapped 407.512 µm², wns_cost 0.5215.
- `C_synth` `52e0ecacb19b` synthesis/F1: area mapped 618.982 µm², wns_cost 0.1142.
- Best logic `wns_cost`: `5c3846870699` 0.2088 @ 553.28 µm² (None).

Those numbers **do not** beat A. Mapped 407 µm² ≠ finish 610/940. Ideal STA ≠ 6_report.

## Honest read

1. **The base flow wins the chip.** WNS −37 ps. No DSE netlist is more on time.
2. **A-injected is the oven control.** Same Yosys netlist as A, isolated cook, identical WNS and sha → B/C comparison is not tool noise.
3. **B is smaller and slower**, even on A's die (−349 ps). The small die was not the cause.
4. **C “fast” is slower and fatter** (−187 ps, 963 µm², 198 repair vs 132).
5. **Place predicts finish.** A was meeting at DP (+12 ps). B/C/Bfix were not. The Next Level funnel would have avoided paying finish on B and C.
6. **Nobody is timing-closed** at 0.46 ns (2.17 GHz). A is the best among the open ones, not a green chip.
7. **PSM IR is not DirectLU** and is not comparable across different dies. The honest PDN win remains 6.075 → 4.156 mV on the same extract as A.
8. **Gold 45.298 unrestamped.** AES Krylov refused. `flowlab/` not touched.

