# Plan: next iteration — generator first, policy second, schema last

Plan only. No experiment starts from this commit. Decision criteria are
pre-registered here, before cooking, and are not revised after the data.

Context: the P0–P7 campaign (`experiment_campaign_plan.md`, verdicts in
`eval_campaign.md` and `campaign_writeup.md`) established that **the ORFS base
wins** on gcd/spi/dynamic_node/ibex/aes at the clocks tried. H1 supported (proxies
invert ranking), H6 supported (deterministic oven 5/5), H2 incomplete, H3/H4/H5
not supported. The funnel correctly rejected losing candidates: the evaluator
works; **the generator** never produced a promotable candidate.

This plan consolidates the strategic feedback received (fidelity policy,
Candidate as single state, EvaluationResult, Pareto as a primitive,
CurrentScenario adapter) with an ordering correction: first widen the search
space with the physical levers already available and measure policy on
existing data; contract refactoring enters only where it is consumed.

## 0. Non-negotiable constraints (unchanged)

- VM 15 GiB / 4 CPU, **one** heavy job at a time, `prlimit --as=8GiB`.
- Never Krylov/MOR on AES extract ~50–70k-R (`admit_solve` decides, not us).
- Never overwrite `results/.../gcd/flowlab/` nor restamp gold 45.298.
- Never touch row `febe6804241c`. New variants for every cook
  (`camp_*` remains the schema; rows already registered are locked).
- DirectLU remains the PDN `numerical_reference`. It is not replaced.
- One `test_dse.py` at a time; F4 live always last.
- Every experiment committed immediately after (durable log, short sessions).
- Campaign §5 criteria remain frozen and identical: win = better WNS,
  or WNS tied (±5 ps) and stdcell area ≥10% smaller, or first to
  close. Proxy never enters the verdict.

## 1. Guiding principle (adopted from feedback, with the correct order)

Spend compute only when an evaluation can realistically change the
decision, and learn from cases where an economical fidelity predicted the
expensive one poorly. The controller question is not “what is the next stage?”
but “which evaluation most reduces uncertainty or increases the probability of
beating the baseline, per unit of cost?”.

Ordering correction vs the feedback: a perfect fidelity policy
applied to candidates that all lose only produces cheaper STOPs.
Therefore: **Q1 physical knobs (generator) → Q2 policy (evaluator) → Q3 schema
(contracts)**. No new AI proposers (LLM/RL/GNN/e-graphs) in this
iteration.

## 2. Falsifiable hypotheses (pre-registered)

| ID | Hypothesis | How it is falsified |
|---|---|---|
| I1 | Physical knobs (`PLACE_DENSITY_LB_ADDON`, `CORE_UTILIZATION`) have more leverage than ABC scripts: a config exists that beats base §5 on ≥1 design, or measured sensitivity exceeds ±25 ps on gcd | If Q1 sweep produces no §5 win **and** observed WNS range on knobs is < 25 ps on gcd and < 50 ps on ibex, I1 is false: the base recipe is robust on physical knobs too |
| I2 | The place→finish residual is stable **per-design**: calibrated on ≥3 finishes of the same design, it predicts finish WNS of subsequent cooks within ±2σ on ≥80% of new points | If <80% of new points fall within ±2σ per-design, I2 is false and place-DP is not a reliable surrogate even locally |
| I3 | Policy can say STOP: ≥80% of candidates the policy refuses to bring to finish really lose (verified by paying control finish) | If <80% of verified rejects lose, the policy throws away good candidates and must be recalibrated before any extension |
| I4 | In the “area at closed clock” regime a §5 win exists: at a clock where base closes, a candidate closes with stdcell area ≥10% smaller | If no Q1/Q2 candidate closes with ≥10% less area where base closes, I4 is false on this set. `camp_gcd_clk090_b` (−24.1%) is **not** retroactively a win: it counted against the H3 bar at 25%, and criteria are not rewritten after the fact |
| I5 | Proxy→finish correlation is measurable and useful: place-DP ranking correlates with finish ranking (Spearman ≥ 0.6 on labeled points), while F1 ranking does not | If even place-DP has correlation < 0.6, the current gate is noise and Q2 policy cannot rely on any economical signal |

## 3. Metrics and decision criteria (frozen)

Single source for QoR verdict: variant `6_report.json`. As in
campaign.

- **Product win**: §5 unchanged (above).
- **Policy (I3)**: STOP precision ≥80% on verified rejects;
  verification budget ≤2 control finishes per design, labeled
  `control_negative`. Control finishes do not count as product win/loss:
  they only pay for the measurement.
- **Residual (I2)**: per-design, mean±σ on labeled finishes; prediction
  = place WNS + design mean residual; ±2σ bar on ≥80% of new points.
- **Diagnostics to always report** (never in the verdict): correlation
  proxy→F5, gate FP/FN rate, time-to-best, number of expensive evaluations,
  compute spent per decision.
- **Phase objective**: maximize `best feasible F5 QoR / compute
  spent` vs ORFS base. Tie remains a valid answer.

## 4. Phases and budget

Sequential, one job at a time, freeze+commit after every experiment.
Registry: `learn/sim/dse/campaign_experiments.jsonl`, phases `Q0..Q4`.

| Phase | Content | # finish | Est. wall |
|---|---|---:|---:|
| **Q0 zero-cost measurement** | Query on existing JSONL (45 rows): F1→finish and place→finish correlation, gate FP/FN, per-design residual with σ. Script `learn/scripts/eval_policy.py` + synthetic tests. Preliminary I5 verdict | 0 | ~1 h |
| **Q1 physical knobs** | gcd: 3×3 grid `PLACE_DENSITY_LB_ADDON` {−0.05, 0, +0.05} × `CORE_UTILIZATION` {25, 35, 45}, center already known → 8 finishes. ibex: 4 points (`LB_ADDON` ±0.05 at config util; util ±10 at LB 0). Netlist = design base yosys (H6 guarantees reproducibility) | 12 | ~1.5 h |
| **Q2 fidelity policy v1** | Next Level: action choice with cost, expected gain, per-design residual from Q0/Q1 and explicit STOPs. `delta` field (vs parent/baseline) on Candidate — field only, no DesignState. Verify I3 with ≤2 control finishes/design on rejects | ≤4 | ~1 h |
| **Q3 incremental schema** | Only where consumed: `pred` (value+uncertainty) when a model produces it; `EvaluationResult`/`SolveResult` contract (status, fidelity, provenance, runtime, RSS, backend_requested/actual, fallback_reason, residual) on next PDN touch; provenance tag `REAL/PARTIAL/SYNTHETIC/ABSENT` on CurrentScenario; explicit Pareto states (dominated/non-dominated/feasible/infeasible/uncertain) in the report | 0 | ~2 h |
| **Q4 area-regime win (conditional)** | Only if Q1/Q2 produce a candidate near the frontier: ≤2 targeted finishes for I4 win. Otherwise honest skip recorded | ≤2 | ~30 min |

Total: ≤18 finishes, ~6 h wall. gcd ~1 min/finish, ibex ~7.5 min/finish.

## 5. Minimal infrastructure (before Q1)

1. `scripts/run_design_finish.sh`: passthrough `PLACE_DENSITY_LB_ADDON`
   (today it already passes `CORE_UTILIZATION`, `DIE_AREA/CORE_AREA`, `ABC_SPEED`,
   `SYNTH_NETLIST_FILES`). Locked refusals unchanged.
2. `learn/scripts/eval_policy.py`: correlations, FP/FN, per-design residuals,
   I1–I5 verdicts with section 3 bars. Output `eval_policy.md/json`.
3. Reused registry (`experiments.py`), `Q*` phases, no second registry.
4. Synthetic tests in `test_dse_next.py` for 1–2 before each cook.

## 6. Stop rules

- An experiment >2× estimated runtime → kill by PID, `timeout`, do not
  repeat in the same session.
- Knob config that fails the flow (e.g. DPL-0038, PDN-0185) → recorded
  `failed` with the error, not retried with the same values.
- Disk <50 GB → clean `results/` of Q* variants already frozen (never base,
  never flowlab).
- RAM >8 GiB in place/route → point excluded, recorded with reason.
- If Q0 falsifies I5 (not even place-DP correlates), Q2 stops at measurement:
  no policy built on noisy signal.

## 7. What we will NOT do in this iteration

- No new proposer: no LLM, RL, GNN, e-graphs/equality saturation,
  architecture-level search. They exist as prototypes: stay frozen until
  policy can choose fidelity, solver, and budget.
- No multi-fidelity Bayesian surrogate: with ~36+18 labeled finishes it would be
  underdetermined. Per-design residual (I2) first — a two-parameter
  model.
- No parallel `DesignState`: Candidate evolves (delta → pred), not
  duplicated.
- No premature compression into a single score: the Pareto frontier
  reports separate axes (area, WNS, power, congestion, IR, EM, cost).
- No retune of §5 criteria or section 3 bars after the data.
- Jpeg / tinyRocket / swerv: only if Q0–Q2 close under budget **and**
  a candidate exists that justifies the cost.

## 8. Phase success criterion (frozen)

The deliverable is **one of two**, stated without reframing:

1. At least one real §5 win at finish against ORFS base (from Q1 or Q4), or
2. Quantitative demonstration that the controller recognizes hopeless
   candidates: I3 ≥80% precision on verified STOPs, plus I2/I5
   measured and reported.

If both fail, the verdict is “neither win nor reliable policy” and is
written that way. Tie is a valid answer; also “the base recipe is robust on
physical knobs too” (I1 false) is a publishable result, not a failure
to hide.
