# Evidenza di verifica (corso)

Aggiornato durante il work goal autonomo. Non sostituisce lo studio: certifica che i **materiali e la pipeline** esistono e girano.

## Struttura (test automatico)

```bash
./scripts/test_course.sh
```

Esito atteso: `SMOKE PASSED`.

Copre: 8 lezioni × (README, LAB, run.sh) con profondità minima, 6 walkthrough Tcl, atlante GUI + PNG Qt/canvas, workbook, design tutorial, `--list`, `--check`, `--auto --lesson 00`, versioni tool.

## Pipeline ORFS variante `learn`

Eseguito sul design tutorial (`FLOW_VARIANT=learn`, `CORE_UTILIZATION=35`, SDC 0.46 ns):

- `make synth floorplan place cts route finish` → exit 0
- Artefatto: `flow/results/nangate45/gcd/learn/6_final.gds`

## GUI pixel-level

Screenshot reali in `learn/reference/gui-shots/` (OpenROAD Qt 26Q2, GCD learn):

- Finestra anatomia: `win_anatomy_labeled.png`
- Fasi Qt: `win_synth.png` … `win_final.png`
- Canvas `save_image`: `03_pdn.png` … `09_final.png` (synth/floorplan headless spesso vuoti: die 0 / GUI-0078)
- Guida: `learn/reference/gui-atlas.md`

## Audit requisiti goal

Vedi [AUDIT.md](./AUDIT.md).

## Cosa resta allo studente (non è un gap del repo)

- Compilare `mio-quaderno.md` e `mio-progetto-finale.md`
- Track sky130: estensione post-corso in CURRICULUM
