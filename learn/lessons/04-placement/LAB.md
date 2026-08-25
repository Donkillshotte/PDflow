# LAB 04 — Placement (90–120 minuti)

Qui il design **occupa spazio**. Porta aperti: atlante GUI §5.5–5.6 e `walkthrough-global_place.tcl.md`.

## Obiettivi misurabili

- [ ] Distinguere GP e DP su screenshot o GUI (non a parole vaghe)
- [ ] Estratto WNS/TNS/buffer da `3_resizer.rpt`
- [ ] Trovato almeno un prefisso resizer (`rebuffer*`, `fanout*`, …)
- [ ] Collegato clock stretto → più buffer → più area → rischio CTS

---

## Parte 1 — Teoria operativa (15 min)

Rileggi `lessons/04-placement/README.md` tabelle sottofasi.

In una frase ciascuna:

1. Cosa ottimizza **global placement**?
2. Cosa vieta **detailed placement**?
3. Perché ORFS fa GP, **poi** resizer, **poi** DP (e non DP prima del resizer)?

Hint: i buffer del resizer devono essere legalizzati.

---

## Parte 2 — Walkthrough Tcl (20 min)

Apri `flow/scripts/global_place.tcl` e il walkthrough.

Segna:

| Riga / blocco | Cosa fa | Se lo togli… |
|---|---|---|
| `buffer_ports` | | slew sui pin I/O |
| `GPL_TIMING_DRIVEN` | | GP ignora slack |
| `-density` | | overflow / buchi |
| `estimate_parasitics -placement` | | STA cieca sui fili |

Poi `flow/scripts/detail_place.tcl`: `detailed_placement`, `improve_placement`, `optimize_mirroring`, `check_placement`.

**Domanda:** perché esiste `3_5_place_dp-failed.odb`?

---

## Parte 3 — Esegui place (15 min)

```bash
./scripts/learn_physical_design.sh --deep --lesson 04
```

O:

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 place
ls results/nangate45/gcd/learn/3_3_place_gp.odb \
   results/nangate45/gcd/learn/3_4_place_resized.odb \
   results/nangate45/gcd/learn/3_5_place_dp.odb
```

---

## Parte 4 — Report (25 min)

Leggi **per intero** (sono corti sul GCD):

```bash
less tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_global_place.rpt
less tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_resizer.rpt
```

Estrai nel quaderno:

| Metrica | Valore | File |
|---|---|---|
| Overflow GP | | 3_global_place / log 3_3 |
| WNS | | 3_resizer |
| TNS | | 3_resizer |
| Buffer inseriti | | log `3_4_place_resized` (`Inserted`) |
| Resize / upsize | | stesso log |

```bash
rg -n 'Inserted|Resize|WNS|TNS|overflow' \
  tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/3_4_place_resized.log \
  tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_resizer.rpt \
  | head -40
```

Workbook **C2**: stesso numero nel quaderno.

---

## Parte 5 — GUI confronto GP vs DP (30 min)

Desktop. Due carichi (o due terminali):

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_3_3_place_gp.odb
# altra shell, stesso cwd:
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_3_5_place_dp.odb
```

Usa `learn/reference/gui-atlas.md`:

- GP: `win_place_gp.png` / `04_place_gp_labeled.png` — blob, possibile overlap visivo
- DP: `win_place_dp.png` / `05_place_dp.png` — allineamento rows

Checklist:

- [ ] Fit (`F`) su entrambi
- [ ] Triangoli I/O sul bordo (GP dopo IOP)
- [ ] Strap PDN visibili
- [ ] Heatmap Placement Density se c’è in View (rosso = pieno)

Find: `rebuffer`, `clkbuf` (pre-CTS i clkbuf sono pochi).

Se non hai Desktop: annota le differenze **sui PNG del repo** — è accettato, ma prova la GUI almeno una volta nel corso.

---

## Parte 6 — Ponte verso CTS (10 min)

Scrivi la catena (lezione 01+03+04):

```
SDC stretto → WNS negativo → RSZ buffer → area ↑ → stesso core (util 35%)
  → al CTS detailed_placement può fare DPL-0038
```

Predici: con `constraint_tight.sdc` i buffer in `3_4` salgono o scendono?

---

## Superamento

- [ ] Tabella metriche resizer
- [ ] Una differenza GP/DP documentata (screenshot o riferimento atlante)
- [ ] Prefisso resizer spiegato
