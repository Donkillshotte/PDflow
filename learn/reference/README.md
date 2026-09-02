# Indice materiali di riferimento

Tempo stimato **solo reference**: 3–4 ore di lettura attiva (non in diagonale).

## Ordine di lettura recommended

1. [glossary.md](./glossary.md) — tieni aperto per tutto the course
2. [file-formats.md](./file-formats.md) — lesson 00–01
3. [gui-atlas.md](./gui-atlas.md) — screenshot Qt reali, anatomia pixel, galleria per fase
4. [gui-openroad.md](./gui-openroad.md) — menu, heatmap, troubleshooting Preview
5. [debug-playbook.md](./debug-playbook.md) — da lesson 03; required before della 05

## Walkthrough script ORFS (leggi *mentre* esegui la fase)

| Fase | Documento |
|---|---|
| Synthesis | [walkthrough-synth.tcl.md](./walkthrough-synth.tcl.md) |
| Floorplan | [walkthrough-floorplan.tcl.md](./walkthrough-floorplan.tcl.md) |
| Placement | [walkthrough-global_place.tcl.md](./walkthrough-global_place.tcl.md) |
| CTS | [walkthrough-cts.tcl.md](./walkthrough-cts.tcl.md) |
| Routing | [walkthrough-route.tcl.md](./walkthrough-route.tcl.md) |
| Finish | [walkthrough-finish.tcl.md](./walkthrough-finish.tcl.md) |

## Workbook e quiz

- [../workbook/README.md](../workbook/README.md) — esercizi
- [../workbook/solutions.md](../workbook/solutions.md) — solutions (after aver provato)
- [../workbook/quiz.md](../workbook/quiz.md) — autovalutazione per lesson
- [../workbook/notes-template.md](../workbook/notes-template.md) — notebook
- [../workbook/progetto-finale-template.md](../workbook/progetto-finale-template.md) — consegna lesson 07

## Metrics del run tutorial

- [golden-metrics.md](./golden-metrics.md) — WNS/`period_min`/area/DRC misurati su `FLOW_VARIANT=learn`

## Power · SPICE · collegamento fasi

After the lessons 00–07, for end-to-end power integrity:

1. [spice-power-chain.md](./spice-power-chain.md) — **catena RTL→PKG** (leggi per primo)
2. [spice-chip-mesh.md](./spice-chip-mesh.md) — mesh on-die `write_pg_spice`
3. [vyges-em-ir.md](./vyges-em-ir.md) — engine IR/EM Apache-2.0 on the mesh GCD
4. [dynamic-ir.md](./dynamic-ir.md) — I(t) per pin + heatmap
5. [dynamic-ir-landscape.md](./dynamic-ir-landscape.md) — PDNSim / vyges / EMSim / ngspice
5b. [dse.md](./dse.md) — multi-fidelity DSE (e-graph + BOiLS SSK-GP + oracle IR)
4. [spice-ngspice-primer.md](./spice-ngspice-primer.md) — System PDN ngspice
5. [system-pdn.md](./system-pdn.md) — landscape tool
6. [pkg-design-package.md](./pkg-design-package.md) — packaging
7. [../sim/spice/README.md](../sim/spice/README.md) — lab netlist locali

## GUI

- [gui-atlas.md](./gui-atlas.md) — guide pixel-level con PNG in `gui-shots/`
- [gui-openroad.md](./gui-openroad.md) — pannelli, menu, sequenza 45 min
