# scripts/

Launcher di root. Catalogo per superficie: [`docs/script.md`](../docs/script.md).
Indice repo: [`docs/README.md`](../docs/README.md).

## Install locale (ordine)

```bash
./scripts/01_install_openroad.sh
./scripts/02_install_opensta.sh
./scripts/03_install_klayout.sh
./scripts/04_setup_orfs.sh
```

Cloud Agent: `PD_FLOW_PROFILE=core bash scripts/cloud_agent_install.sh`.

## Prodotto

`run_design_finish.sh` è l’unico `make finish` della campagna.
Rifiuta `FLOW_VARIANT` in `{flowlab, learn, base}` e i nomi `*krylov*`.
Lo chiama `learn/dse/cook.py`, non a mano.

## Corso

`learn_physical_design.sh`, `run_studio.sh`, `test_course.sh`.
`run_gcd_flow.sh` è il demo RTL→GDS, non il forno prodotto.
