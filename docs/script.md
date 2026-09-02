# Script

Wrapper in `scripts/` (root) e `learn/scripts/` (Python / signoff).
Install: [`scripts/README.md`](../scripts/README.md).

## `scripts/` — install e launchers

| Script | Superficie | Cosa |
|---|---|---|
| `01_install_openroad.sh` | infra | OpenROAD binari |
| `02_install_opensta.sh` | infra | OpenSTA da sorgenti |
| `03_install_klayout.sh` | infra | KLayout |
| `04_setup_orfs.sh` | infra | clone ORFS + yosys |
| `cloud_agent_install.sh` | infra | profilo `core` / `analysis` / `full` |
| `cloud_agent_smoke.sh` | infra | versioni |
| `test_cloud_bootstrap.sh` | infra | check statici |
| `run_design_finish.sh` | **prodotto** | `make finish` isolato; refuse `flowlab`/`learn`/`base` |
| `campaign_cook.sh` | prodotto | helper campagna |
| `p1_gcd_clock_sweep.sh` | prodotto (storico P) | sweep clock gcd |
| `p2_abc_speed.sh` | prodotto (storico P) | ABC speed |
| `p5_ibex_clock_sweep.sh` | prodotto (storico P) | sweep ibex |
| `q1_knob_sweep.sh` | prodotto (storico Q) | knob |
| `q4_area_regime.sh` | prodotto (storico Q) | regime area |
| `learn_physical_design.sh` | corso | wrapper lezioni |
| `run_studio.sh` | corso | Studio Next.js |
| `test_course.sh` | corso | smoke struttura |
| `test_studio_api.sh` | corso | API Studio |
| `test_all_phases.sh` | corso | fasi esaustive |
| `run_gcd_flow.sh` | corso / demo | RTL→GDS gcd |
| `run_opensta_example.sh` | corso | smoke STA |
| `run_dse_gcd_cloud.sh` | lab | DSE GCD |
| `run_dse_handoff_finish.sh` | lab | handoff finish |
| `run_dynamic_ir_cloud.sh` | lab | Dynamic IR |
| `run_gcd_finish_cloud.sh` | lab | finish GCD lab |
| `run_gcd_e2e_relaxed.sh` | lab | e2e relaxed |
| `run_aes_f4_cloud.sh` | lab | AES F4 (no Krylov) |
| `run_aes_f5_lite_cloud.sh` | lab | AES F5-lite |

## `learn/scripts/` — prodotto

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/run_recipe_loop.py --dry-run
python3 learn/scripts/cook_recipe.py --design gcd --recipes place_sparse_setup
python3 learn/scripts/run_tpe.py --design ibex --max-cooks 8
python3 learn/scripts/record_experiment.py --help
python3 learn/scripts/test_dse_next.py
```

Tuner: `pip install -r learn/requirements-tune.txt` (optuna≥3.4,<4).
Optuna **solo** in `run_tpe.py`.

## `learn/scripts/` — laboratorio / signoff

| Gruppo | Esempi |
|---|---|
| Lab DSE | `run_dse.py`, `test_dse.py`, `dse_f4_worker.py` |
| PDN / IR | `pdn_dynamic.py`, `pdn_extract.py`, `pdn_solvers.py`, `run_dynamic_ir.sh` |
| Signoff | `run_signoff_all.sh`, `run_sta_signoff.sh`, `run_drc_signoff.sh` |
| Engine | `build_dpn_engine.sh` |

Un job pesante. `pkill -f` vietato: kill per PID.
