# Audit di completezza — corso OpenROAD (goal)

Verifica **requirement-by-requirement** sullo stato del tree `learn/`.
Eseguire `./scripts/test_course.sh` dopo ogni modifica strutturale.
Questo file elenca **dove** sta l’evidenza; lo smoke test è l’evidenza automatica.

| # | Requisito | Evidenza nel repo | Come verificare |
|---|---|---|---|
| 1 | Teoria IT + LAB 60–120 min + `run.sh` per lezioni 00–07 | `learn/lessons/NN-*/{README.md,LAB.md,run.sh}` (8×3). LAB con parti cronometrate e `make` **completo** (`DESIGN_CONFIG` + `FLOW_VARIANT=learn` + `CORE_UTILIZATION`). Wrapper `--deep` legge LAB. | smoke: file + `min_lines`; `rg` non deve trovare `make ...` come comando |
| 2 | Walkthrough Tcl: synth, floorplan, placement, CTS, routing, finish | `learn/reference/walkthrough-{synth,floorplan,global_place,cts,route,finish}.tcl.md` allineati a ORFS 26Q2 | smoke: 6 file; `min_lines` su place/CTS |
| 3 | Guide GUI pixel-level | `gui-atlas.md` + PNG in `gui-shots/` (finestra Qt + canvas + overlay + heatmap ORFS). Non solo ASCII. | smoke: size PNG + atlas embed |
| 4 | Workbook: esercizi, quiz, progetto finale | `workbook/{README,quiz,progetto-finale-template,notes-template,solutions}.md` | smoke: file + quiz GUI + progetto cita golden-metrics |
| 5 | Debug playbook, glossario, formati file | `debug-playbook.md`, `glossary.md` (RSZ-0062, DPL-0038, period_min, NDR, gcell, OpenRCX, IFP-0028), `file-formats.md` (header SPEF) | smoke: `rg` termini + `*SPEF` |
| 6 | Smoke test wrapper + toolchain | `scripts/test_course.sh` → `SMOKE PASSED` (`--list`, `--check`, `--auto --lesson 00`, versioni tool) | questo comando |
| 7 | README/curriculum allineati ai materiali | `learn/README.md`, `CURRICULUM.md`, `README.md` root citano atlante, LAB, variant `learn`, `golden-metrics.md`, finish verde ≠ 2.17 GHz | smoke: `rg golden-metrics` + `gui-atlas` |

## Comandi di verifica

```bash
./scripts/test_course.sh
test -s learn/reference/gui-atlas.md
test -s learn/reference/gui-shots/win_anatomy_labeled.png
test -s learn/reference/golden-metrics.md
test -s learn/workbook/solutions.md
ls learn/lessons/*/LAB.md learn/lessons/*/run.sh
```

## Cosa lo smoke **non** sostituisce

- Aver **eseguito** un RTL→GDS `learn` (pipeline in [EVIDENCE.md](./EVIDENCE.md), numeri in [golden-metrics.md](./reference/golden-metrics.md)).
- Aver aperto la GUI sul **Desktop** Cursor (Preview HTTP non conta).
- Aver compilato `mio-quaderno.md` / `mio-progetto-finale.md` (lavoro dello studente).
