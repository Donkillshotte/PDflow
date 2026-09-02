# Plan: exhaustive multi-design campaign vs base flow

Plan only. No experiment starts from this commit.

Objective: determine whether DSE has **product value** or remains a lab.
The GCD@0.46ns verdict ("A stays") holds for one ~500-cell design at a single
clock. This campaign tests it on more designs, more clocks, with
**pre-registered** decision criteria (written here, before cooking).

## 0. Non-negotiable constraints (unchanged)

- VM 15 GiB / 4 CPU, **one** heavy job at a time, `prlimit --as=8GiB`.
- Never Krylov/MOR on AES extract ~50–70k-R (`admit_solve` decides, not us).
- Never overwrite `results/.../gcd/flowlab/` nor restamp gold 45.298.
- Never touch row `febe6804241c`. New variants for every cook.
- One `test_dse.py` at a time; F4 live always last.
- Every experiment committed immediately after (durable log, short sessions).

## 1. Falsifiable hypotheses (pre-registered)

| ID | Hypothesis | How it is falsified |
|---|---|---|
| H1 | Proxies (ideal STA, mapped area) **invert true order** on larger designs too, not only GCD | If on ≥2 designs proxy ranking matches finish ranking, H1 is false and the funnel is oversized |
| H2 | The place-DP gate predicts finish ranking (P2 ≈ economical oracle) | Measure on ALL cooks: if gate precision/recall < 80% on ≥15 points, recalibrate or discard the gate |
| H3 | B-type (small netlist) **wins on area** when the clock relaxes: a clock exists where B closes and A does not, or B closes with ≥25% less area | If in the clock sweep B never closes before A or does not keep the area advantage, H3 is false and “smaller” is never a win |
| H4 | DSE value **grows with design size** (more leverage for per-cone ABC / physical knobs) | If best-DSE vs base delta does not improve (in % WNS or area) going from ~500 to ~10k–50k cells, H4 is false: DSE does not scale |
| H5 | The place→finish residual (−50 ps ± σ) transfers across designs | If observed residual falls outside ±2σ on >30% of points, recalibrate per-design |
| H6 | The oven is deterministic on large designs too (A-injected bit-identical) | If an A-injected differs, ALL deltas for that design are suspect until the nondeterminism source is found |

## 2. Design matrix

Sizes to **measure in P0** (estimates here). All nangate45, ORFS config already in repo.

| Design | Cells (est.) | Role | Est. finish runtime (4 CPU) | Notes |
|---|---:|---|---:|---|
| `gcd` (tutorial) | ~500 | anchor + clock sweep | ~1 min | already characterized |
| `spi` / `riscv32i` | ~1–3k | small step | ~2–5 min | missing nangate45 config: create in P0 (only `learn/designs/`, never in ORFS) |
| `dynamic_node` | ~10k | medium, pickle netlist | ~10–20 min | `SWAP_ARITH_OPERATORS=1` by default: disable for honest base? decide in P0 |
| `ibex` | ~15–20k | medium, SystemVerilog (slang) | ~20–40 min | real CPU, sensible ctrl/dpath cones |
| `aes` | ~15–20k | medium, fixed FLOORPLAN_DEF | ~15–30 min | geometry already locked by config → ideal for H6; **no F4 Krylov** |
| `jpeg` | ~40–70k | large | ~30–60 min | util 80: congestion risk, keep as stretch |
| `tinyRocket` / `swerv` | ~30k / ~100k | out of v1 budget | hours | only if P2 finishes under budget |

Design set v1: **gcd, riscv32i (or spi), dynamic_node, ibex, aes**. Jpeg stretch.

## 3. Experimental axes

Only one thing changes per experiment (bake-off style). Axes:

1. **Clock sweep** (gcd + 1 medium design only): SDC ∈ {0.40, 0.46, 0.55, 0.70, 0.90} ns on gcd; {T_base·0.9, T_base, T_base·1.25, T_base·1.6} on the medium design. Answers H3.
2. **Netlist variant** (all designs): `abc_area` (base A), `abc_speed`, and — where DSE already has an equiv-PASS full-chip winner — the DSE netlist. Answers H1/H4.
3. **Geometry**: product (config util) vs fixed (base A die for that design). Only on points where the netlist variant is competitive at place. Already falsified on GCD-B; repeat only if needed. |
4. **Knob robustness** (gcd only, cheap): `PLACE_DENSITY_LB_ADDON` ±0.05 and `CORE_UTILIZATION` ±10 on base, to measure sensitivity of A’s −37 ps. If A swings ±50 ps with knobs, B/C deltas must be re-read.

**Non-axes (excluded):** seed sweep (ORFS here is deterministic, H6 verifies), different PDKs, macro placement, Yosys retiming.

## 4. Controls per design (mandatory before comparisons)

1. **Base**: one `make finish` with the ORFS recipe from config → freeze JSON (WNS/TNS/area/repair/die + sha `6_report`). Variant `<design>_base`.
2. **A-injected**: recook base `1_2_yosys.v` in variant `<design>_ainj`. Must be bit-identical (H6). If not: stop on that design.
3. **Equiv**: every non-base netlist must pass Yosys equiv vs RTL (or declare `unsupported` and be excluded from the funnel — never “trust me”).
4. **Funnel dry-run**: before paying a DSE finish, P2 gate must say promote. Finishes where “gate says no” are paid ONLY in the H2 validation subset (max 1 per design), labeled `control_negative`.

## 5. Metrics and decision criteria (pre-registered)

Single source for verdict: same-variant `6_report.json`. Proxy never in verdict.

- **Product win** (per design, per clock): better WNS, or WNS tied (±5 ps) and stdcell area ≥10% smaller, or first to close (WNS≥0) at the given clock.
- **Search win** (not product): DSE funnel finds in ≤N paid finishes a point the base does not have — state separately, never add to product win.
- **H2 (P2 gate)**: for every paid finish, record (place_wns, finish_wns). Precision = fraction of promoted that finish better than worst promoted base; recall = fraction of real wins the gate would have promoted. Target ≥80/80 on ≥15 points.
- **H5 (residual)**: finish−place distribution per design; report mean±σ per design and global.
- **Tie is a valid answer.** No post-hoc reframing: if A-equivalents win everywhere, the verdict is “DSE on these designs is not a product” and is written that way.

## 6. Phases and budget

Sequential, one job at a time. Each phase commits its freeze/JSON before the next.

| Phase | Content | # finish | Est. wall |
|---|---|---:|---:|
| **P0 pilot** | 1 base finish per design (5 designs) + A-injected (5) + measure real cells/runtime + riscv32i/spi config | 10 | ~2–4 h |
| **P1 clock sweep GCD** | 5 clocks × 3 netlists (A-yosys, B, C) − 0.46 already done | 12 | ~30 min |
| **P2 multi-design base vs abc_speed** | 4 designs × {base already in P0, abc_speed} | 4 | ~2–3 h |
| **P3 DSE proxy campaign per design** | `run_dse.py --campaign` at F1–F3 level on ibex/dynamic_node/aes (budget 10–15 min each, NO finish in loop) | 0 | ~1 h |
| **P4 funnel-selected finishes** | Next Level `--launch-finish`: max 2 finishes per design chosen by P2 gate + 1 `control_negative` for H2 | ≤9 | ~2–4 h |
| **P5 clock sweep medium design** | 4 clocks × 2 netlists on best from P4 (or abc_speed if none) | 8 | ~2–4 h |
| **P6 PDN same-extract** | DirectLU on winner extracts IF `admit_solve` admits (never Krylov AES); otherwise static only | 0 | ~1 h |
| **P7 analysis** | extend `eval_vs_base_flow` to multi-design matrix; H1–H6 verdicts; write-up | 0 | ~1 h |

Total: **~40–45 finishes**, ~10–18 h sequential wall. Split across sessions: every experiment writes freeze+commit; session can die without losing anything (SETUP_LOG + JSON to resume).

## 7. Infrastructure to build (small, before P0)

1. `scripts/run_design_finish.sh` — generalize `run_dse_handoff_finish.sh`: `DESIGN`, `FLOW_VARIANT`, `SDC_NS` (generate SDC in tmp, never in ORFS), optional `SYNTH_NETLIST_FILES`, optional `DIE_AREA/CORE_AREA`. Refuses base/`flowlab`/`learn` writes.
2. `learn/dse/experiments.py` — JSONL experiment registry: id, design, clock, netlist, variant, sha, outcome, runtime. Append-only.
3. `learn/scripts/eval_campaign.py` — extends `eval_vs_base_flow` to matrix: per-design, per-clock, H1–H6 with section 5 criteria.
4. Synthetic tests for 1–3 in `test_dse_next.py` (parse, refusal, registry) — before each cook.

## 8. Stop rules

- An experiment >2× estimated runtime → kill (by PID), mark `timeout`, do not repeat in the same session.
- A-injected not identical on a design → freeze that design (report only, no comparisons).
- Disk <50 GB free → clean `results/` of DSE variants already frozen (never bases).
- RAM: if a design exceeds 8 GiB cap in place/route → excluded, written in registry with reason.
- jpeg/tinyRocket/swerv: start only if P0–P4 close under budget.

## 9. What we will NOT do

- No finish inside the legacy controller loop.
- No Krylov/MOR on AES; F4 dynamic only where `admit_solve` admits.
- No unverified retiming/architecture in the funnel (binary GCD stays out until transactional equiv exists).
- No averaging across designs: verdicts are per-design; aggregate is only H1–H6 counts.
- No tuning of section 5 criteria after seeing the data.
