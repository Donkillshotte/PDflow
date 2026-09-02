# LAB 07 — Finish, signoff e final project (90–120 minuti)

Finish is il **contract** with STA, LVS e (in un’azienda) la foundry. Un `make finish` green senza tabella metrics **non** chiude the course.

## Measurable objectives

- [ ] Elencati i deliverable e a chi servono
- [ ] WNS confrontato su almeno 3 stime (place / CTS / finish)
- [ ] GDS aperto in KLayout (o descritto da file size + layer se KLayout manca)
- [ ] `mio-progetto-finale.md` compilato (non vuoto)

---

## Part 1 — Inventario file (20 min)

```bash
ls -lh tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.*
```

Fill in **prima** di aprire i file:

| Files | Recipient | Cosa succede se manca |
|---|---|---|
| `6_final.gds` | mask / viewer | you have not geometria fab |
| `6_final.def` | ECO / tool terzi | niente coordinate testuali |
| `6_final.v` | LVS / sim | netlist post-fill diversa dalla synth |
| `6_final.spef` | STA signoff | stay on estimates |
| `6_final.sdc` | STA | constraints non allineati al netlist |
| `6_finish.rpt` | tu | you do not know if timing is closed |

Apri `learn/reference/walkthrough-finish.tcl.md` e `file-formats.md` sezioni SPEF/GDS/DEF.

Conta componenti nel DEF:

```bash
rg -c '^- ' tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.def | head
rg -n '^COMPONENTS' -A2 tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.def | head
```

Diff netlist synth vs final (nomi buffer/fill):

```bash
wc -l tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/1_2_yosys.v \
      tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.v
rg -c 'FILLCELL|clkbuf|rebuffer' \
  tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.v
```

Fill **non** cambia the function: cambia density di processo e un po’ i parasitics.

---

## Part 2 — Run finish se manca (15 min)

```bash
./scripts/learn_physical_design.sh --lesson 07
```

Se `save_images.tcl` stampa un errore GUI in log: **ignoralo** se `6_final.gds` esiste. Il course pinna ORFS 26Q2 proprio per evitare crash `STA-2204` su save_images di master.

---

## Part 3 — Quattro stime di WNS (25 min)

Estrai e metti in tabella (final project §2):

```bash
rg -n 'WNS|TNS|worst' \
  tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_resizer.rpt \
  tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/4_cts_final.rpt \
  tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/6_finish.rpt \
  | head -50
```

| Stima | Files | WNS | TNS |
|---|---|---|---|
| Placement RC | 3_resizer | | |
| CTS | 4_cts_final | | |
| Post-route / SPEF | 6_finish | | |

Question: se finish is **peggio** del place, because is onesto? (fili reali > modello placement)

`period_min` a finish: compare with golden-metrics (**0.50 ns** ~2011 MHz vs SDC 0.46 ns).
Nel final project you must scrivere **esplicitamente** se hai chiuso 2.17 GHz (sul run d’oro: no).

SPEF: `head -30 results/.../6_final.spef` — search for `*SPEF` e `*D_NET`. You do not need capire every riga: you need sapere che **is RC**. See `file-formats.md`.

---

## Part 4 — GUI final + atlas (20 min)

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_final
```

Checklist (`gui-atlas.md` §4 e §5.10):

- [ ] Anatomia A–G riconosciuta
- [ ] `select -name "clk" -type Net` → Inspector: `CLOCK`, `ROUTED`, `CTS_NDR_0`
- [ ] Layer M2/M3 isolati come in lesson 06
- [ ] Find `FILLCELL` se `USE_FILL` is on

PNG: `win_anatomy_labeled.png`, `win_inspector_tab.png`, `09_final.png`.

KLayout:

```bash
klayout tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.gds
```

F = fit. Spegni all i layer, riaccendi uno. Compare i colors con Display Control OpenROAD: **non** coincidono per forza (different palette).

---

## Part 5 — Final project (30–40 min, may overrun)

Copia:

```bash
cp learn/workbook/progetto-finale-template.md learn/workbook/mio-progetto-finale.md
```

Fill in **tutte** le sezioni del template. Senza this file the course is not finito.

Vincoli:

- Numeri presi dai **tuoi** report, non inventati
- Un errore reale (anche “ho lanciato make senza FLOW_VARIANT”)
- Tre spiegazioni aloud che terresti a un esame

---

## Part 6 — Catena SPICE (optional, 45–60 min)

After green `make finish`, connect end-to-end power integrity:

- [ ] Leggi [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-07-finish)
- [ ] In Studio: signoff post-finish → **Catena SPICE** (o CLI):

```bash
FLOW_VARIANT=learn ./learn/scripts/run_power_chain.sh
```

- [ ] Compare heatmap `orfs_final_ir_drop.png` con `pdn_chip_ir_*.json` (chip mesh)
- [ ] Apri `learn/sim/spice/` e conta R/I in `mesh_stats_*.json`
- [ ] FlowLab fase [PKG](/flusso?phase=pkg): droop e Zmax System PDN

Checklist optional — non blocca il completamento lesson se saltata.

---

## Part 7 — Signoff 4 pilastri (30–45 min)

After `finish`, esegui il signoff enterprise (matrice in Studio fase **finish** o [`/pkg`](/pkg)):

- [ ] Leggi [`signoff-matrix.md`](../../reference/signoff-matrix.md) e [`golden-gcd.json`](../../signoff/golden-gcd.json)
- [ ] **STA:** `FLOW_VARIANT=learn ./learn/scripts/run_sta_signoff.sh` — confronta WNS/TNS con golden-metrics
- [ ] **DRC:** `./learn/scripts/run_drc_signoff.sh` — route DRC lines + GDS violations separate nel JSON
- [ ] **LVS:** `./learn/scripts/run_klayout_lvs.sh` — interpret `.lvsdb` anche se FAIL (FreePDK45 educativo)
- [ ] **Power:** `./learn/scripts/run_power_signoff.sh` — catena activity → chip IR → system → export + gate IR/droop
- [ ] **Orchestrator:** `./learn/scripts/run_signoff_all.sh` — report aggregato `signoff_all_{v}.json`
- [ ] In Studio: badge PASS/FAIL su matrice vs golden; API `GET /api/signoff?variant=learn`

Checklist signoff — recommended per chiudere il discourse “contratto foundry”, not required per `--status` se salti LVS lungo.

---

## Pass criteria del course (non solo of the lesson)

- [ ] `--status` : lezioni 00–07
- [ ] Workbook A2 (SDC sweep) e D1 (DPL-0038) almeno abbozzati
- [ ] Final project non vuoto
- [ ] Sai aprire l’atlas e trovare PDN vs route senza cercare nel README
