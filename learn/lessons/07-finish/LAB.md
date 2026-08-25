# LAB 07 — Finish, signoff e progetto finale (90–120 minuti)

Finish è il **contratto** con STA, LVS e (in un’azienda) la foundry. Un `make finish` verde senza tabella metriche **non** chiude il corso.

## Obiettivi misurabili

- [ ] Elencati i deliverable e a chi servono
- [ ] WNS confrontato su almeno 3 stime (place / CTS / finish)
- [ ] GDS aperto in KLayout (o descritto da file size + layer se KLayout manca)
- [ ] `mio-progetto-finale.md` compilato (non vuoto)

---

## Parte 1 — Inventario file (20 min)

```bash
ls -lh tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.*
```

Compila **prima** di aprire i file:

| File | Destinatario | Cosa succede se manca |
|---|---|---|
| `6_final.gds` | mask / viewer | non hai geometria fab |
| `6_final.def` | ECO / tool terzi | niente coordinate testuali |
| `6_final.v` | LVS / sim | netlist post-fill diversa dalla synth |
| `6_final.spef` | STA signoff | resti sulle stime |
| `6_final.sdc` | STA | constraints non allineati al netlist |
| `6_finish.rpt` | tu | non sai se hai chiuso il timing |

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

Fill **non** cambia la funzione: cambia densità di processo e un po’ i parassiti.

---

## Parte 2 — Esegui finish se manca (15 min)

```bash
./scripts/learn_physical_design.sh --lesson 07
```

Se `save_images.tcl` stampa un errore GUI in log: **ignoralo** se `6_final.gds` esiste. Il corso pinna ORFS 26Q2 proprio per evitare crash `STA-2204` su save_images di master.

---

## Parte 3 — Quattro stime di WNS (25 min)

Estrai e metti in tabella (progetto finale §2):

```bash
rg -n 'WNS|TNS|worst' \
  tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_resizer.rpt \
  tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/4_cts_final.rpt \
  tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/6_finish.rpt \
  | head -50
```

| Stima | File | WNS | TNS |
|---|---|---|---|
| Placement RC | 3_resizer | | |
| CTS | 4_cts_final | | |
| Post-route / SPEF | 6_finish | | |

Domanda: se il finish è **peggio** del place, perché è onesto? (fili reali > modello placement)

SPEF: `head -30 results/.../6_final.spef` — cerca `*D_NET`. Non serve capire ogni riga: serve sapere che **è RC**.

---

## Parte 4 — GUI final + atlante (20 min)

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_final
```

Checklist (`gui-atlas.md` §4 e §5.10):

- [ ] Anatomia A–G riconosciuta
- [ ] `select -name "clk" -type Net` → Inspector: `CLOCK`, `ROUTED`, `CTS_NDR_0`
- [ ] Layer M2/M3 isolati come in lezione 06
- [ ] Find `FILLCELL` se `USE_FILL` è on

PNG: `win_anatomy_labeled.png`, `win_inspector_tab.png`, `09_final.png`.

KLayout:

```bash
klayout tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.gds
```

F = fit. Spegni tutti i layer, riaccendi uno. Confronta i colori con Display Control OpenROAD: **non** coincidono per forza (palette diversa).

---

## Parte 5 — Progetto finale (30–40 min, può sforare)

Copia:

```bash
cp learn/workbook/progetto-finale-template.md learn/workbook/mio-progetto-finale.md
```

Compila **tutte** le sezioni del template. Senza questo file il corso non è finito.

Vincoli:

- Numeri presi dai **tuoi** report, non inventati
- Un errore reale (anche “ho lanciato make senza FLOW_VARIANT”)
- Tre spiegazioni a voce che terresti a un esame

---

## Superamento del corso (non solo della lezione)

- [ ] `--status` : lezioni 00–07
- [ ] Workbook A2 (sweep SDC) e D1 (DPL-0038) almeno abbozzati
- [ ] Progetto finale non vuoto
- [ ] Sai aprire l’atlante e trovare PDN vs route senza cercare nel README
