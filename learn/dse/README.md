# DSE

Due pile nello stesso package. **Il prodotto decide. Il laboratorio resta.**

| Pila | Ingresso | Win |
|---|---|---|
| **Prodotto** | [`product.md`](product.md) · `run_recipe_loop.py` | `win_rule.py` |
| **Laboratorio** | `run_dse.py` / controller | non decide |

Indice repo: [`docs/README.md`](../../docs/README.md).
Lab: [`docs/laboratorio.md`](../../docs/laboratorio.md).
Corso: [`docs/corso.md`](../../docs/corso.md).
Tree: [`docs/architettura.md`](../../docs/architettura.md).

## Prodotto

Netlist ufficiale, die pinnato, forno CTS/route/finish.

```
run_recipe_loop.py          coordinatore (cover → improve → tune)
cook_recipe.py / cook.py    cook_one (ricette XOR knobs)
run_tpe.py                  Optuna TPE (solo qui)
record_experiment.py        registro jsonl
test_dse_next.py            suite veloce
```

| Modulo | Ruolo |
|---|---|
| `knob_catalog.py` | Ricette, titoli, resolve offset |
| `recipe_select.py` | Cover / improve / deepen, niente design name |
| `recipe_labels.py` | Titolo e payoff umani |
| `win_rule.py` | win / tie / lose / wrong_die |
| `floorplan.py` | Box DEF, `FLOORPLAN_DEF`, `wrong_die` |
| `experiments.py` | Registro, refuse locked variant |
| `cook.py` | Pin die, policy STOP, record |
| `fidelity_policy.py` | Gate place → finish |
| `tune_space.py` | 7 assi, omit-default, fingerprint, pin |
| `tune_score.py` | Vincoli + score da `win_rule` |
| `tune_warm.py` | Warm-start stesso die, enqueue |
| `tune_transfer.py` | Muri globali, prior cross-design |
| `f6_finish.py` | Parse `6_report` / GRT / place |

Piani: [`tpe_plan.md`](tpe_plan.md) (congelato), [`arch_review.md`](arch_review.md)
(muri + transfer). Operazioni: [`docs/operazioni.md`](../../docs/operazioni.md).
Risultati: [`docs/risultati.md`](../../docs/risultati.md).

```bash
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dse_next.py
PYTHONPATH=learn:learn/scripts python3 learn/scripts/run_recipe_loop.py --dry-run
```

Registro: `learn/sim/dse/campaign_experiments.jsonl`.
Variant: `camp_{design}_{recipe}` o `camp_{design}_tpe_{12hex}`.

## Laboratorio (non prodotto)

Budget-aware, multi-fidelity: architecture → logic → synth → place →
route → PDN. Dynamic IR è un oracolo OpenROAD/ODB, non una mappa neurale.

Design e F1 (lab):

| id | top | note |
|----|-----|------|
| `gcd` | `gcd` | e-graph solo qui |
| `aes` | `aes_cipher_top` | no Krylov; mesh ~70k-R |
| `ibex` | `ibex_core` | slang missing |

```bash
python3 learn/scripts/run_dse.py --campaign --wall-s 180
python3 learn/scripts/test_dse.py          # un file alla volta
```

### Invarianti lab (restano)

- Oro GCD Dynamic IR **45.298 mV**: mai restampato.
- `QoR.area_um2` = area stdcell, non die.
- `Candidate`: `knobs` azione, `artifacts` osservazione, `pred` predizione.
- `admit_solve` è il gate risorse. DirectLU è il riferimento numerico.
- Non appiattire architecture + ABC + util + PDN in un vettore.

Layer sostituibili: `dse.layers.ADAPTERS` (extraction, activity, current,
solver, surrogate, proposer). I proposer GNN/LLM restano lab.

GCD vs ORFS finish: [`flow_vs_orfs_gcd.md`](flow_vs_orfs_gcd.md).
Handoff finish (A resta): [`handoff_finish_bakeoff.md`](handoff_finish_bakeoff.md).

## Campagna storica P0–P7

Criteri §5 congelati in [`experiment_campaign_plan.md`](experiment_campaign_plan.md).
Non si reinterpretano. I1–I5: [`next_iteration_plan.md`](next_iteration_plan.md).
