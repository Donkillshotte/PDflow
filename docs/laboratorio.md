# Laboratorio

Non decide i win di prodotto. Resta nel tree perché è lo stack IR / e-graph /
refine. Indice prodotto: [prodotto.md](prodotto.md).

## Cosa è

Ricerca multi-fedeltà: architecture → logic → synth → place → route → PDN.
Dynamic IR è un oracolo OpenROAD/ODB (`engine/` + `pdn_*.py`), non una mappa
neurale. I proposer GNN / LLM restano qui.

Piano eseguibile (Fase 2 **chiusa**): [`PLAN.md`](../PLAN.md).
Stack F0–F6: [`learn/reference/dse.md`](../learn/reference/dse.md).
Solver nativi: [`engine/README.md`](../engine/README.md).

## Entry

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/run_dse.py --campaign --wall-s 180
python3 learn/scripts/test_dse.py          # un file alla volta; F4 per ultimo
```

Cloud / IR:

```bash
./scripts/run_dse_gcd_cloud.sh
./scripts/run_dynamic_ir_cloud.sh
./scripts/run_gcd_finish_cloud.sh
# AES F4/F5-lite: solo con ALLOW_HEAVY_ANALYSIS=1 e mai Krylov
```

Build solver: `./learn/scripts/build_dpn_engine.sh`.

## Invarianti (non negoziabili)

- Oro GCD Dynamic IR **45.298 mV**: mai restampato
  (`learn/sim/reports/dynamic_ir_flowlab.json`).
- Finish FlowLab corrente **6.075 mV** (`n_r` worker ~5816) = `current_run`,
  non `reference_run`.
- AES `learn/sim/dse/memory_aes.jsonl` riga `febe6804241c` intatta.
- `QoR.area_um2` = area stdcell, non die.
- `Candidate`: `knobs` azione, `artifacts` osservazione, `pred` predizione.
- `admit_solve` è il gate risorse. DirectLU = riferimento numerico.
- Non appiattire architecture + ABC + util + PDN in un vettore.
- `f1_pareto_parents` è F1-only. Non sostituirlo per F2-fast.
- Non `mem.touch` su hit F4 in cache.

## Test lab (split D.1–D.5)

`learn/scripts/test_dse.py` è il runner. Ordine fisso:

| Modulo | Cosa |
|---|---|
| `test_dse_metrics.py` | dominates / gated / HV |
| `test_dse_memory.py` | JSONL / BOiLS / e-graph |
| `test_dse_planner.py` | attribution / `plan_search` / F1 |
| `test_dse_steer.py` | residual / F5 / IR leftover |
| `test_dse_live_f4.py` | live F4, **ultimo**, un job |

Sintetico o GCD-scale. Un `test_dse.py` alla volta. Non lanciare AES finish
«per vedere».

## Moduli lab (package `learn/dse`)

Controller / stage / acquire restano grandi di proposito (`PLAN.md`).
Layer sostituibili: `dse.layers.ADAPTERS`.

Handoff finish vs ORFS: [`flow_vs_orfs_gcd.md`](../learn/dse/flow_vs_orfs_gcd.md),
[`handoff_finish_bakeoff.md`](../learn/dse/handoff_finish_bakeoff.md).
Baseline A (`FLOW_VARIANT=flowlab` su gcd) non si sovrascrive.
