# System PDN — analisi IR con modelli di alimentazione package/board

Stato: **PARTIAL → READY (demo Studio)** su GCD nangate45 tramite
`analyze_power_grid -source_type STRAPS|FULL|BUMPS`.

## Cosa misura

| Mode | Significato OpenROAD | Uso didattico |
|---|---|---|
| **STRAPS** | Sorgenti come strap su metal alto | Proxy alimentazione da board/package strap |
| **FULL** | Tutti i nodi metal come sorgenti | Limite inferiore IR (griglia “ideale”) |
| **BUMPS** | Pattern bump C4 sintetico (pitch/size) | Proxy package bump — **non** LEF bump reale |

Sul GCD tutorial i tre mode danno IR drop tipicamente **~10 mV** (~1% su 1.1 V):
la PDN M1–M4–M7 basta. Su die mm² i numeri divergono e i bump contano.

## Come eseguirlo

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_system_pdn.sh
# oppure da Studio: azione system_pdn / fase PKG
```

Artefatti:

- Log: `learn/sim/reports/system_pdn_<variant>.log`
- Stamp: `results/nangate45/gcd/<variant>/.system_pdn.ok`
- Richiede: `6_final.odb` (finish)

## Cosa non è

- Non è un modello board SI/PI (S-parameter / IBIS).
- Non usa LEF di packaging reale (RDL, C4, μbump).
- Heatmap IR del finish (`orfs_final_ir_drop.png`) resta il riferimento GUI.

## Collegamenti

- Chip PDN + gridcheck: fase **PDN** in FlowLab / `run_gridcheck.sh`
- Packaging teorico: [pkg-design-package.md](./pkg-design-package.md)
- Mappa flusso: [extended-flow.md](./extended-flow.md)
