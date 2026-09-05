# Scripts

Root wrappers. Catalog by surface: [`docs/script.md`](script.md).
Repo index: [`docs/README.md`](README.md).

## `scripts/` — install and launchers

| Script | Surface | What |
|---|---|---|
| `01_install_openroad.sh` | infra | OpenROAD binaries |
| `02_install_opensta.sh` | infra | OpenSTA from source |
| `03_install_klayout.sh` | infra | KLayout |
| `04_setup_orfs.sh` | infra | clone ORFS + yosys |
| `cloud_agent_install.sh` | infra | `core` / `analysis` / `full` profile |
| `cloud_agent_smoke.sh` | infra | versions |
| `test_cloud_bootstrap.sh` | infra | static checks |
| `run_design_finish.sh` | **product** | isolated `make finish`; refuses `flowlab`/`learn`/`base` |
| `run_lab_asap7.sh` | **lab** | ASAP7 RTL→GDS (`lab_asap7_*`); corners / VT / CCS; not a product win |
| `campaign_cook.sh` | product | campaign helper |
| `p1_gcd_clock_sweep.sh` | product (historic P) | gcd clock sweep |
| `p2_abc_speed.sh` | product (historic P) | ABC speed |
| `p5_ibex_clock_sweep.sh` | product (historic P) | ibex sweep |
| `q1_knob_sweep.sh` | product (historic Q) | knob sweep |
| `q4_area_regime.sh` | product (historic Q) | area regime |
| `learn_physical_design.sh` | course | lesson wrapper |
| `run_studio.sh` | course | Studio Next.js |
| `test_course.sh` | course | structure smoke |
| `test_studio_api.sh` | course | Studio API |
| `test_all_phases.sh` | course | exhaustive phases |
| `run_gcd_flow.sh` | course / demo | RTL→GDS gcd |
| `run_opensta_example.sh` | course | STA smoke |
| `run_dse_gcd_cloud.sh` | lab | GCD DSE |
| `run_dse_handoff_finish.sh` | lab | finish handoff |
| `run_dynamic_ir_cloud.sh` | lab | Dynamic IR |
| `run_gcd_finish_cloud.sh` | lab | GCD lab finish |
| `run_gcd_e2e_relaxed.sh` | lab | relaxed e2e |
| `run_aes_f4_cloud.sh` | lab | AES F4 (no Krylov) |
| `run_aes_f5_lite_cloud.sh` | lab | AES F5-lite |

## `learn/scripts/` — product

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/run_recipe_loop.py --dry-run
python3 learn/scripts/cook_recipe.py --design gcd --recipes place_sparse_setup
python3 learn/scripts/run_tpe.py --design ibex --max-cooks 8
python3 learn/scripts/record_experiment.py --help
python3 learn/scripts/test_dse_next.py
```

Tuner: `pip install -r learn/requirements-tune.txt` (optuna≥3.4,<4).
Optuna **only** in `run_tpe.py`.

## `learn/scripts/` — lab / signoff

| Group | Examples |
|---|---|
| Lab DSE | `run_dse.py`, `test_dse.py`, `dse_f4_worker.py` |
| PDN / IR | `pdn_dynamic.py`, `pdn_extract.py`, `pdn_solvers.py`, `run_dynamic_ir.sh` |
| Signoff | `run_signoff_all.sh`, `run_sta_signoff.sh`, `run_sta_ir_aware.sh`, `run_drc_signoff.sh` |
| Engine | `build_dpn_engine.sh` |
| Lab PEX / CCS / LVS | `run_analytical_pex.py`, `char_nangate_ccs.py`, `run_lvs_deep.py`, `install_fastercap.sh` |

One heavy job. `pkill -f` forbidden: kill by PID.
