# Plan: TPE on official die (real finish)

Plan only. No TPE trial starts from this commit. Choices below
are pre-registered and are not revised after first data.

Context: product today is OFAT (one recipe = one knob) + deepen
(win pairs). Papers (AutoTuner, AutoDMP, MOTPE) search a continuous
space with TPE/BO, but often stop at place and optimize HPWL or
a PPA mix, and move the die. We want **the same search brain**,
**our oven** (CTS + route + finish + IR/leak), and **fixed die**.

This plan does **not** rewrite I1–I5 or §5 P0–P7. It is not a Bayesian
surrogate of the finish (forbidden in `next_iteration_plan.md` §7 with few
points). Every TPE observation is a real finish, or a STOP at place.

## 0. Non-negotiable constraints

- Official Yosys netlist for the slot. Fixed RTL. ABC area.
- Fixed floorplan: `DIE_AREA` / `CORE_AREA` from official DEF. No
  `CORE_UTILIZATION`, `CORE_ASPECT_RATIO` in search space.
- Unchanged win rule (`win_rule.py`): slack ±5 ps, area/power/leakage/IR
  ±10%, `wrong_die` if die moves.
- One heavy job at a time. `prlimit` stays in the wrapper.
- Never `FLOW_VARIANT` in {flowlab, learn, base}, never krylov, never restamp
  GCD gold 45.298 mV, never row `febe6804241c`.
- Single registry: `learn/sim/dse/campaign_experiments.jsonl`.
- No `if design ==` in tuner. Ranges are offsets on `config.mk` defaults.

## 1. Why not AutoTuner / Ray / white-box

`tools/AutoTuner` is in the ORFS tree. We do not use it as product.

| AutoTuner | This plan |
|---|---|
| Ray + HyperOpt/Ax/Optuna on ORFS JSON | Optuna TPE, single process |
| PPA mix (`coeff_perform/power/area`) | Constraints + **win rule** score |
| Often includes util / die | Die nailed from DEF |
| Full flow or proxy, JSON choice | Place → policy → CTS/route/finish |
| Does not know leakage/IR/`wrong_die` | Uses them |
| Does not reuse official `1_2_yosys.v` | Always, except synth (outside v1) |

White-box (OpenROAD C++ patches) is lab, not product.
A GNN/GP predicting finish instead of cooking is lab.

TPE and not NSGA-II in v1: win rule is already a feasible region + ordering among wins. NSGA-II returns a Pareto we would re-cut with the same rule. Constrained TPE is the direct map.

## 2. Core idea: feasibility, then rank

Win rule is **not** a smooth scalar. Forcing it into a mix like
`0.5·WNS+0.3·area` is like AutoTuner: it chases something else.

Two layers, both derived from `win_rule` (same `SLACK_PS=5`,
`METRIC_FRAC=0.10`, same `_imp`):

**Constraints** (Optuna: `c ≤ 0` is feasible):

- Slack: `c_slack = -5 - ΔWNS_ps` → feasible iff timing not worse than 5 ps.
- Axes: for area, power, leakage, IR, `c = -10 - imp_%` → feasible iff
  none is ≥10% worse. Axis `None` → constraint 0 (does not disqualify) and does not count as “better”.
- Die: `c_die = 0` if `not moves_floorplan`, else `1`.
- Finished: `c_done = 0` if `status=done` and finish WNS present, else `1`.

A STOP at place is **not** an IR lose. It is `c_done=1` and, if policy
predicted dead slack, also `c_slack>0`. TPE learns “this zone is
late”, not “this zone has horrible IR”. A DPL/route fail is `c_done=1`
without dirtying QoR axes.

**Score to minimize**, only among feasible (win or tie):

```
better = max(0, area_imp, power_imp, leak_imp, ir_imp)   # % better
if better >= 10 or ΔWNS_ps > 5:   # would be win
    score = -1 - 0.01*better - 0.001*max(0, ΔWNS_ps)
else:
    score = 0   # tie
```

So: every lose/wrong_die/incomplete is infeasible; every tie is 0; a win
is negative; a wider win (IR −40% vs −10%) is more negative. We do not
reward one axis at 9% if another is at −11% (constraint). We do not change
`verdict()`.

Coordinator and `eval_policy` still use `verdict == "win"`.
Score exists **only** to drive TPE.

## 3. Space v1 (same die, same netlist)

One dimension = one catalog mechanism, continuous or discrete
around config default. Two pads (global/detail) remain **one**
axis: catalog moves them together.

| Optuna dimension | Type | Range | If = config default |
|---|---|---|---|
| `PLACE_DENSITY_LB_ADDON` | continuous | default ±0.10, clamp `[0, 0.99]` | omit env (config stays) |
| `cell_pad` | integer | `{0,1,2}` | omit both `CELL_PAD_*` |
| `TNS_END_PERCENT` | integer | `[0, 100]` | omit |
| `SETUP_SLACK_MARGIN` | continuous | `[0, 0.08]` ns | omit if 0 |
| `HOLD_SLACK_MARGIN` | continuous | `[0, 0.05]` ns | omit if 0 |
| `CTS_BUF_DISTANCE` | continuous | `[80, 200]` µm | omit if equal to config default |
| `GPL_TIMING_DRIVEN` | categorical | `{0,1}` | omit if 1 (ORFS default) |

**Always injected, never sampled:** `DIE_AREA`, `CORE_AREA` from
`official_box(design)`; `ABC_AREA=1`, `ABC_SPEED=0`; official
`1_2_yosys.v` netlist.

**Never in space:** `CORE_UTILIZATION`, `CORE_ASPECT_RATIO`,
`SYNTH_HIERARCHICAL`, `ABC_SPEED`, Verilog rewrite, placer seed,
white-box.

Why omit defaults: `run_design_finish.sh` applies a knob only
if env is non-empty. Passing `HOLD_SLACK_MARGIN=0` **is not** “do not
touch”: it is a value. TPE must distinguish “leave config” from “force 0”
only where 0 is a real knob (TNS=0 = skip repair, which is in catalog).

`cell_pad=0` means both pads at 0, explicit: it is a trial,
not “leave config”, if default is not 0.

## 4. Evaluator = cook, not a second oven

Today `cook_recipe.py` only knows `--recipes`. Path place → `decide()` →
finish → `record_experiment.py` is the right one. Do not duplicate it.

Extract `learn/dse/cook.py` (`cook_one(...)`) used by:

- `cook_recipe.py --recipes …` (unchanged for cover/improve)
- `cook_recipe.py --knobs '{...}'` XOR `--recipes` (TPE)
- `run_tpe.py`

Pin die, refuse floorplan recipes, ABC area, official netlist, policy
STOP, registry: one function.

**Variant name:** `camp_{design}_tpe_{fp}` where `fp` is 12 hex of
sha256 of **canonical** vector (sorted keys, floats rounded to
6 decimals, without `DIE_AREA`/`CORE_AREA`/`ABC_*`). Reason: ORFS writes
under `FLOW_VARIANT`; `ExperimentLog.has(variant, phase)` skips
duplicates; two phases with same variant stomp logs. Hash is
global, not per-phase.

`role=knob`. `extra.tuner="tpe"`, `extra.knobs=…`, `extra.tpe_trial=n`.
`recipe_ids` empty (do not invent catalog id). Human labels
derive from knobs, as `label_for` already does in fallback.

Registry phase: `T1`. Do not reuse J1/C1/L1.

## 5. Warm-start: cover is not thrown away

Cold TPE with 8 trials is worse than deepen combos. Log on **same
die** is the prior.

Rules to import a row into Optuna (`create_trial` completed, zero
re-cooks):

- same slot `design` and clock
- `status=done` and finish WNS present
- `verdict != "wrong_die"`
- official netlist (`fresh_synth` absent/false)
- `extra.knobs` projectable onto space v1 (missing keys = config
  default)
- fingerprint not already in studio

Univariates that won (dense place, padding, setup, CTS fits,
sparse place, …) become completed trials with their score. Same-die loses
become infeasible trials: TPE learns walls.

Deepen combos **not yet cooked** (dense place+padding on gcd, etc.)
are `enqueue`d as first asks, not a parallel queue. Then TPE samples.

## 6. Integrate into coordinator (delicate point)

Today `coordinate()` precomputes **all** deepen combos and
`max-cooks` cooks 4 in a row. Fine for a grid. **Not fine
for TPE:** each finish must update the model before the next trial.

So:

1. **Cover** — unchanged. One recipe, readable names, catalog gaps.
2. **Improve** — unchanged. Only slots with 0 win (spi closed, new knobs).
3. **Tune** — replaces deepen in **default**. `--deepen` stays override.
4. **Stop** — catalog covered, improve exhausted, and (TPE budget finished
   **or** slot not admissible to tune).

Admissible to tune: base exists, die pinnable (`official_box`), and
**not** (very-closed ∧ 0 product win ∧ improve exhausted). spi @ 1 ns
stays stop. Do not burn TPE trials on a die already closed by 600 ps
where OFAT moved nothing.

One `run_recipe_loop.py` invocation in tune mode:

- decides `tune` + `design` (cheap-first among admissible)
- does **not** list 20 vectors
- calls `run_tpe.py --design … --max-cooks N` which runs
  ask → cook_one → tell, one at a time

`run_recipe_loop --dry-run` prints `decision=tune`, slot, number of
trials already in studio, next fingerprint if enqueue, no floorplan
recipes.

Deepen is not deleted: lab/override. Mental-queue combos become TPE enqueue, so we keep “dense+pad” idea without blind batch cooking.

## 7. Budget and TPE stop

- One design at a time, cheap-first (gcd first).
- v1 live: **gcd, ≤8 new finishes** (beyond warm-start). Then read
  whether TPE found a win OFAT/deepen did not. Only then ibex/aes.
- Local stop: `max_trials` **or** 3 feasible finishes in a row without
  new `verdict=win` and without improving best win score.
- Fail/timeout: recorded, infeasible trial, not repeated with same
  fingerprint.
- Disk: `camp_*_tpe_*` variants can be cleaned after jsonl freeze; never `flowlab`, never `camp_*_base`.

## 8. Dependencies and tests

- Optuna **only** in `run_tpe.py` / `learn/requirements-tune.txt`.
  Space and score **do not** import Optuna: `test_dse_next.py` stays
  fast and without extra pip.
- If Optuna missing, `run_tpe.py` exits 2 with install command.
- Tests without ORFS:
  - space contains no floorplan keys
  - `pin(design, sampled)` adds box and removes util/aspect
  - `score(win) < score(tie)`; lose/wrong_die have constraint `> 0`
  - STOP does not invent IR
  - stable fingerprint; collide → skip
  - warm-start skips `wrong_die` and `fresh_synth`
  - omit env at default
  - coordinator: after cover+improve, default `tune` not `deepen`;
    no `if design ==`
- One Optuna test (skip if missing): fake deterministic evaluator, TPE
  proposes second point after fake lose in a corner of space.

No live cooking in tests.

## 9. Planned files (future implementation)

| File | Role |
|---|---|
| `learn/dse/tune_space.py` | dimensions, clamp, omit-default, fingerprint, pin die |
| `learn/dse/tune_score.py` | constraints + score from `win_rule` / `_imp` |
| `learn/dse/cook.py` | shared `cook_one` |
| `learn/scripts/cook_recipe.py` | CLI `--recipes` / `--knobs` |
| `learn/scripts/run_tpe.py` | Optuna ask/tell, warm-start, enqueue |
| `learn/scripts/run_recipe_loop.py` | `tune` decision, `--deepen` flag |
| `learn/requirements-tune.txt` | pinned `optuna` |
| `learn/scripts/test_dse_next.py` | assert space/score/pin/coordinator |

No Ray, no AutoTuner JSON, no second jsonl.

## 10. What can go wrong (and chosen response)

- **Few finishes → TPE ≈ random.** Hence mandatory warm-start and first live is gcd, not aes.
- **Score chasing one axis and burning slack.** Loses are constraints, not soft penalties.
- **STOP counted as IR lose.** Forbidden; see §2.
- **Cooking 4 precomputed TPE trials.** Forbidden; serial ask/tell.
- **Passing `HOLD=0` and changing default.** Omit, §3.
- **Variant `camp_gcd_tpe_17` colliding with phase.** Vector hash, §4.
- **Tune on spi.** Slot not admissible, §6.
- **Die moving anyway (hier, residual util).** Pin box +
  `wrong_die`; if it happens it is a pin bug, stop tuner.
- **Want NSGA/GNN/white-box at first no-win.** Outside v1. Measure
  whether TPE beats OFAT on same oven first.

## 11. Phase success criterion (frozen)

TPE is a **method** success if, same oven and die:

1. Space and score tested without ORFS and cannot sample floorplan.
2. One gcd run (≤8 new finishes) recorded in jsonl with
   `extra.tuner=tpe`.
3. Product verdict stays `win_rule` (not TPE score).
4. Honest statement whether TPE found a **new** win vs already-cooked
   univariate recipes, or not.

If (4) is no, do not “add a GNN”. Declare that on gcd, continuous did not beat OFAT with that budget.

## 12. Implementation slices (not timelines)

1. `tune_space` + `tune_score` + fake tests. Zero cooks.
2. Extract `cook_one`; `cook_recipe --knobs` refuses floorplan and pins
   die. CLI refuse / fingerprint skip tests, still without TPE.
3. `run_tpe.py` + warm-start + ask/tell with fake eval, then gcd live ≤8.
4. `coordinate()`: default `tune` replaces `deepen`; `--deepen`
   stays. Dry-run. Update `product.md` cycle (already pointed from here).

Steps 1–2 do not require Optuna installed in CI if score tests stay in `test_dse_next.py`.
