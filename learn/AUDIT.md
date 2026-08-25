# Audit di completezza — corso OpenROAD (goal)

Verifica **requirement-by-requirement** sullo stato del tree `learn/`.  
Eseguire `./scripts/test_course.sh` dopo ogni modifica strutturale.

| # | Requisito | Evidenza nel repo | Stato |
|---|---|---|---|
| 1 | Teoria IT + LAB 60–120 min + `run.sh` per lezioni 00–07 | `learn/lessons/NN-*/{README.md,LAB.md,run.sh}` (8×3). LAB con parti cronometrate. Wrapper `--deep` legge LAB. | Verificare con smoke + `wc` |
| 2 | Walkthrough Tcl: synth, floorplan, placement, CTS, routing, finish | `learn/reference/walkthrough-{synth,floorplan,global_place,cts,route,finish}.tcl.md` allineati a ORFS 26Q2 | File presenti |
| 3 | Guide GUI pixel-level | `gui-atlas.md` + PNG in `gui-shots/` (finestra Qt + canvas + overlay). Non solo ASCII. | File + test size PNG |
| 4 | Workbook: esercizi, quiz, progetto finale | `workbook/README.md`, `quiz.md`, `progetto-finale-template.md`, `notes-template.md` | File presenti |
| 5 | Debug playbook, glossario, formati file | `debug-playbook.md`, `glossary.md`, `file-formats.md` | File presenti |
| 6 | Smoke test wrapper + toolchain | `scripts/test_course.sh` → `SMOKE PASSED` | Comando |
| 7 | README/curriculum allineati ai materiali | `learn/README.md`, `CURRICULUM.md` citano atlante, LAB, variant `learn` | Lettura |

## Comandi di verifica

```bash
./scripts/test_course.sh
test -s learn/reference/gui-atlas.md
test -s learn/reference/gui-shots/win_anatomy_labeled.png
ls learn/lessons/*/LAB.md learn/lessons/*/run.sh
```

Questo file **non** sostituisce lo smoke test: lo smoke è l’evidenza automatica.
