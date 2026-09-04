# Lab

Does not decide product wins. Stays in the tree as the IR / e-graph /
refine stack. Product index: [product.md](product.md).

## What it is

Multi-fidelity search: architecture → logic → synth → place → route → PDN.
Dynamic IR is an OpenROAD/ODB oracle (`engine/` + `pdn_*.py`), not a neural
voltage map. GNN / LLM proposers stay here.

Executable plan (Phase 2 **closed**): [`PLAN.md`](../PLAN.md).
F0–F6 stack: [`learn/reference/dse.md`](../learn/reference/dse.md).
Native solvers: [`engine/README.md`](../engine/README.md).

## Entry

Studio Lab bench: `/lab` (`GET /api/lab`). Physics ledger and DSE launch
compare live there. Product wins are `/product` (`GET /api/product`).
FlowLab finish `#ir` is the GCD mesh ledger, not this bench.

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/run_dse.py --campaign --wall-s=180
python3 learn/scripts/test_dse.py          # one file at a time; F4 last
python3 learn/scripts/validate_lab_physics.py
```

Cloud / IR:

```bash
./scripts/run_dse_gcd_cloud.sh
./scripts/run_dynamic_ir_cloud.sh
./scripts/run_gcd_finish_cloud.sh
# AES F4/F5-lite: only with ALLOW_HEAVY_ANALYSIS=1 and never Krylov
```

Build solver: `./learn/scripts/build_dpn_engine.sh`.

## Invariants (non-negotiable)

- Gold GCD Dynamic IR **45.298 mV**: never restamped
  (`learn/sim/reports/dynamic_ir_flowlab.json`).
- Current FlowLab finish **5.173 mV** (worker `n_r` ~5816, finish SPEF t50) = `current_run`,
  not `reference_run`.
- AES `learn/sim/dse/memory_aes.jsonl` row `febe6804241c` stays intact.
- `QoR.area_um2` = stdcell area, not die.
- `Candidate`: `knobs` = action, `artifacts` = observation, `pred` = prediction.
- `admit_solve` is the resource gate. DirectLU = numerical reference.
- Do not flatten architecture + ABC + util + PDN into one vector.
- `f1_pareto_parents` is F1-only. Do not replace it for F2-fast.
- Do not `mem.touch` on cached F4 hits.

## Lab tests (split D.1–D.5)

`learn/scripts/test_dse.py` is the runner. Fixed order:

| Module | What |
|---|---|
| `test_dse_metrics.py` | dominates / gated / HV |
| `test_dse_memory.py` | JSONL / BOiLS / e-graph |
| `test_dse_planner.py` | attribution / `plan_search` / F1 |
| `test_dse_steer.py` | residual / F5 / IR leftover |
| `test_dse_live_f4.py` | live F4, **last**, one job |

Synthetic or gcd-scale. One `test_dse.py` at a time. Do not launch AES finish
“just to see”.

## Lab modules (`learn/dse` package)

Controller / stage / acquire stay large on purpose (`PLAN.md`).
Replaceable layers: `dse.layers.ADAPTERS`.

Finish handoff vs ORFS: [`flow_vs_orfs_gcd.md`](../learn/dse/flow_vs_orfs_gcd.md),
[`handoff_finish_bakeoff.md`](../learn/dse/handoff_finish_bakeoff.md).
Baseline A (`FLOW_VARIANT=flowlab` on gcd) is not overwritten.
