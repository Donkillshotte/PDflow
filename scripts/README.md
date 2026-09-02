# scripts/

Root launchers. Surface catalog: [`docs/script.md`](../docs/script.md).
Repo index: [`docs/README.md`](../docs/README.md).

## Local install (order)

```bash
./scripts/01_install_openroad.sh
./scripts/02_install_opensta.sh
./scripts/03_install_klayout.sh
./scripts/04_setup_orfs.sh
```

Cloud Agent: `PD_FLOW_PROFILE=core bash scripts/cloud_agent_install.sh`.

## Product

`run_design_finish.sh` is the only campaign `make finish`.
Refuses `FLOW_VARIANT` in `{flowlab, learn, base}` and `*krylov*` names.
Called by `learn/dse/cook.py`, not by hand.

## Course

`learn_physical_design.sh`, `run_studio.sh`, `test_course.sh`.
`run_gcd_flow.sh` is the RTL→GDS demo, not the product oven.
