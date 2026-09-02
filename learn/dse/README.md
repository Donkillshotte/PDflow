# DSE

Two stacks in the same package. **Product decides. Lab remains.**

| Stack | Entry | Win |
|---|---|---|
| **Product** | [`product.md`](product.md) · `run_recipe_loop.py` | `win_rule.py` |
| **Lab** | `run_dse.py` / controller | does not decide |

Repo index: [`docs/README.md`](../../docs/README.md).
Lab: [`docs/lab.md`](../../docs/lab.md).
Course: [`docs/course.md`](../../docs/course.md).
Tree: [`docs/architecture.md`](../../docs/architecture.md).

## Product

Official netlist, pinned die, CTS/route/finish oven.

```
run_recipe_loop.py          coordinator (cover → improve → tune)
cook_recipe.py / cook.py    cook_one (recipes XOR knobs)
run_tpe.py                  Optuna TPE (only here)
record_experiment.py        jsonl registry
test_dse_next.py            fast suite
```

| Module | Role |
|---|---|
| `knob_catalog.py` | Recipes, titles, resolve offset |
| `recipe_select.py` | Cover / improve / deepen, no design name |
| `recipe_labels.py` | Human title and payoff |
| `win_rule.py` | win / tie / lose / wrong_die |
| `floorplan.py` | DEF box, `FLOORPLAN_DEF`, `wrong_die` |
| `experiments.py` | Registry, refuse locked variant |
| `cook.py` | Pin die, policy STOP, record |
| `fidelity_policy.py` | Gate place → finish |
| `tune_space.py` | 7 axes, omit-default, fingerprint, pin |
| `tune_score.py` | Constraints + score from `win_rule` |
| `tune_warm.py` | Warm-start same die, enqueue |
| `tune_transfer.py` | Global walls, cross-design prior |
| `f6_finish.py` | Parse `6_report` / GRT / place |

Plans: [`tpe_plan.md`](tpe_plan.md) (frozen), [`arch_review.md`](arch_review.md)
(walls + transfer). Operations: [`docs/operations.md`](../../docs/operations.md).
Results: [`docs/results.md`](../../docs/results.md).

```bash
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dse_next.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/run_recipe_loop.py --dry-run
```

Registry: `learn/sim/dse/campaign_experiments.jsonl`.
Variant: `camp_{design}_{recipe}` or `camp_{design}_tpe_{12hex}`.

## Lab (not product)

Budget-aware, multi-fidelity: architecture → logic → synth → place →
route → PDN. Dynamic IR is an OpenROAD/ODB oracle, not a neural map.

Designs and F1 (lab):

| id | top | note |
|----|-----|------|
| `gcd` | `gcd` | e-graph only here |
| `aes` | `aes_cipher_top` | no Krylov; mesh ~70k-R |
| `ibex` | `ibex_core` | slang missing |

```bash
python3 learn/scripts/run_dse.py --campaign --wall-s 180
python3 learn/scripts/test_dse.py          # one file at a time
```

### Lab invariants (remain)

- GCD Dynamic IR gold **45.298 mV**: never restamped.
- `QoR.area_um2` = stdcell area, not die.
- `Candidate`: `knobs` action, `artifacts` observation, `pred` prediction.
- `admit_solve` is the resource gate. DirectLU is the numeric reference.
- Do not flatten architecture + ABC + util + PDN into one vector.

Replaceable layers: `dse.layers.ADAPTERS` (extraction, activity, current,
solver, surrogate, proposer). GNN/LLM proposers remain lab.

GCD vs ORFS finish: [`flow_vs_orfs_gcd.md`](flow_vs_orfs_gcd.md).
Finish handoff (A stays): [`handoff_finish_bakeoff.md`](handoff_finish_bakeoff.md).

## Historical P0–P7 campaign

§5 criteria frozen in [`experiment_campaign_plan.md`](experiment_campaign_plan.md).
Not reinterpreted. I1–I5: [`next_iteration_plan.md`](next_iteration_plan.md).
