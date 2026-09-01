# Campaign write-up (P7) — pre-registered H1–H6

Plan: `learn/dse/experiment_campaign_plan.md` (sha in `eval_campaign.json`).
Win criteria §5 are **frozen**. Source of truth: `6_report.json` per variant.
Proxy STA is never the verdict.

## Product table (P0, default clocks)

| Design | Clock | Base WNS | Cells | Closed? | A-injected |
|---|---:|---:|---:|---|---|
| gcd | 0.46 ns | **−37.2 ps** | 680 | no | bit-identical |
| spi | 1.00 ns | **+612 ps** | 238 | yes | bit-identical |
| dynamic_node | 6.00 ns | **+3.354 ns** | 11146 | yes | bit-identical |
| ibex | 2.20 ns | **+22.4 ps** | 23434 | yes (barely) | bit-identical |
| aes | 0.82 ns | **−8.9 ps** | 15960 | no | bit-identical |

Nobody in the DSE/abc_speed column beats the same-clock base on frozen §5
(better WNS, or ±5 ps and ≥10% smaller, or first to close).

## H1 — proxies invert ranking

**Supported on gcd@0.46 ns.** Finish ranking A ≫ C ≫ B. F1 proxy ranking
C ≫ B (A has no F1 row). On ≥1 design the proxy winner is not the finish
winner. Other designs have no competing DSE proxy at P0 (P3 spi equiv failed;
ibex F1 not ready).

## H2 — place-DP gate as cheap oracle

Live P2 gate is place WNS ≥ 0. After P1, n≥15 labeled finishes, but **no
product-win vs the same-clock base**, so recall is N/A. Precision of
“promoted ⇒ beats base” is not 80/80 in the §5 sense. **Incomplete / not a
pass.** GCD B/C remain true negatives (place late, finish late).

## H3 — small netlist wins when the clock relaxes

GCD sweep {0.40, 0.46, 0.55, 0.70, 0.90} × {A,B,C}:

- 0.40 / 0.46: all open. A is least late.
- **0.55: A closes first (+13 ps).** B −251, C −109.
- 0.70: A +128, C +3.3 (closed), B −128.
- 0.90: all closed. B area 519 vs A 683 = **−24.1%** (frozen bar is 25%).

**H3 not supported.** A closes first. B’s area win misses the 25% bar.

## H4 — DSE value grows with design size

P0/P2 deltas (best DSE or abc_speed − base) at the product clock:

| Design | Cells | ΔWNS |
|---|---:|---:|
| spi | 238 | −11 ps (abc_speed) |
| gcd | 680 | −150 ps (C) |
| ibex | 23434 | −2 ps (abc_speed) |

Not monotonic in size. All deltas are **negative** (base wins). **H4 not
supported.**

## H5 — place→finish residual transfers

GCD mean residual ≈ −51 ps (σ ≈ 24 ps). SPI +30 ps, AES −12 ps, ibex −239 ps,
dynamic_node −250 ps. Outlier fraction vs gcd ±2σ is ≤30% in the current
eval (**supported** on that frozen bar) but the mid-size residuals are ~5×
the gcd mean — the model should be recalibrated per-design before use as a
finish substitute. It is not one.

## H6 — oven deterministic

**Supported on 5/5 designs.** A-injected `6_report` sha and WNS match the
base at the same clock (gcd, spi, dynamic_node, ibex, aes). Eval pairs by
`(design, clock)` so clock-sweep bases are not compared to the 0.46 ns ainj.

## P3 / P4 (proxy + funnel)

- GCD: existing `memory_flowlab.jsonl` (equiv PASS). Funnel already skipped B/C.
- SPI: F1 mapped but **equiv=FAIL** on every ABC script tried → not funnel-eligible.
- ibex: `f1_ready=False` (no slang).
- dynamic_node: not in `dse.designs`.
- AES: F1–F3 controller would ingest the F4 extract path; **not launched** (no Krylov).

P4: no new F6-eligible DSE netlist to pay. control_negative already paid on GCD B/C.

## P6 PDN

GCD finish extract DirectLU **6.075 mV** (`n_r=5816`) already on disk;
gold **45.298 mV** unrestamped. AES Krylov remains REFUSED. No new AES
extract. Other designs: no same-extract PDN paid this campaign.

## Product verdict

On this design set and these clocks, **the ORFS base recipe is the product
winner.** DSE/abc_speed never took a frozen §5 win. Pareggio is a valid
answer (ibex abc_speed is a ±2 ps tie without a 10% area cut). The Next
Level funnel is not a product: it correctly refused the GCD DSE netlists
that lose at finish.

Jpeg / tinyRocket / swerv were stretch and were not started (P0–P4 closed
without a DSE finish worth promoting).
