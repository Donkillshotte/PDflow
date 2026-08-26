# OpenROAD Physical Design Studio

Interfaccia web interattiva per il corso in `learn/`.
Non sostituisce gli script: li **orchestra** (check, fasi ORFS, progresso, materiali).

## Avvio

Dalla root del repository:

```bash
./scripts/run_studio.sh
```

Apri [http://127.0.0.1:43217](http://127.0.0.1:43217).

Produzione:

```bash
./scripts/run_studio.sh --build
```

Oppure:

```bash
cd studio
npm install
npm run dev -- -H 127.0.0.1 -p 43217
```

## Cosa fa l’UI

| Area | Contenuto |
|---|---|
| Studio | Hero + progresso lezioni |
| Lezioni | Teoria / LAB / Esegui fase per 00–07 |
| Strumenti | Stato openroad/yosys/sta/klayout + console azioni |
| Materiali | golden-metrics, atlante GUI, glossario, workbook, walkthrough Tcl |

Le azioni lunghe (`route`, `finish`) possono richiedere diversi minuti; l’output
appare nella console della pagina Strumenti / tab Esegui.

## CLI invariato

```bash
./scripts/learn_physical_design.sh --deep --lesson 01
./scripts/test_course.sh
```
