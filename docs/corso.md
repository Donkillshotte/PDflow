# Corso / Studio

Didattica RTL→GDS. Non decide i win di prodotto. Varianti ORFS `learn` e
`flowlab` sono **locked**: il wrapper prodotto le rifiuta.

## Corso (`learn/`)

Percorso 20–28 ore: 8 lezioni (00–07), LAB, walkthrough Tcl, workbook, GUI.

```bash
./scripts/learn_physical_design.sh --check
./scripts/learn_physical_design.sh --list
./scripts/learn_physical_design.sh --deep --lesson 01-constraints
./scripts/test_course.sh
```

| File | Ruolo |
|---|---|
| [`learn/README.md`](../learn/README.md) | Avvio |
| [`learn/CURRICULUM.md`](../learn/CURRICULUM.md) | Syllabus |
| [`learn/EVIDENCE.md`](../learn/EVIDENCE.md) | Pipeline eseguita |
| [`learn/AUDIT.md`](../learn/AUDIT.md) | Requirement-by-requirement |
| [`learn/reference/README.md`](../learn/reference/README.md) | Glossario, Tcl, IR, OSS |

Tutorial GCD: `FLOW_VARIANT=learn`. Finish verde ≠ timing chiuso
(vedi `golden-metrics.md`). SDC tutorial 0.46 ns è aggressivo.

## Studio (`studio/`)

UI Next.js. Orchestra gli script con lock, dipendenze fase, storico job.

```bash
./scripts/run_studio.sh          # http://127.0.0.1:43217
./scripts/test_studio_api.sh
./scripts/test_all_phases.sh     # esaustivo
```

Dettagli: [`studio/README.md`](../studio/README.md).
Un job ORFS alla volta (`learn/.studio-run.lock`).
FlowLab vive su `/flusso`, variante `flowlab` isolata dal corso.

GUI Qt OpenROAD: pulsante Desktop su Cursor, non le card Preview HTTP.

## Signoff didattico

Dopo `make finish` sulla variante del corso:

```bash
export FLOW_VARIANT=learn   # locked per il prodotto; ok qui
./learn/scripts/run_signoff_all.sh
```

Catena power/IR di studio: [`learn/reference/spice-power-chain.md`](../learn/reference/spice-power-chain.md).
Non ristampa il gold 45.298 mV.
