# Evidenza di verifica (corso)

Aggiornato durante il work goal autonomo. Non sostituisce lo studio: certifica che i **materiali e la pipeline** esistono e girano.

## Struttura (test automatico)

```bash
./scripts/test_course.sh
```

Esito atteso: `SMOKE PASSED`.

Copre: 8 lezioni × (README, LAB, run.sh), 6 walkthrough Tcl + GUI guide,
workbook, design tutorial, `--list`, `--check`, `--auto --lesson 00`, versioni tool.

## Pipeline ORFS variante `learn`

Eseguito sul design tutorial (`FLOW_VARIANT=learn`, `CORE_UTILIZATION=35`, SDC 0.46 ns):

- `make synth floorplan place cts route finish` → exit 0
- Artefatto: `flow/results/nangate45/gcd/learn/6_final.gds`

## Gap residui (non bloccanti, lavoro futuro)

- Guide GUI testuali (pannelli/menu), non screenshot annotati pixel-per-pixel
- Nessun track sky130 nel wrapper (estensione post-corso in CURRICULUM)
- Workbook: lo studente deve ancora compilare il quaderno a mano
