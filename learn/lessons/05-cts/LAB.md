# LAB 05 — CTS (sessione da 90–120 minuti)

Porta aperti: README 05, `walkthrough-cts.tcl.md`, `gui-atlas.md` §5.7 e §9, playbook CTS.

I numeri tra parentesi sono di un run `learn` di riferimento (util 35, 0.46 ns). I **tuoi** possono differire: annota i tuoi.

## Obiettivi misurabili

- [ ] Skew e latency letti da `4_cts_final.rpt`
- [ ] `CLKBUF*` contato (GUI o `rg`) pre vs post
- [ ] Clock tree spiegato usando `orfs_cts_clock_tree.png` o Viewer
- [ ] DPL-0038 provocato **e** risolto, documentato

---

## Parte 1 — Teoria con il viewer (20 min)

Apri `learn/reference/gui-shots/orfs_cts_clock_tree.png`.

Nel quaderno:

| Elemento nel PNG | Cosa rappresenta | Valore approssimato (ns) |
|---|---|---|
| Triangolo rosso in alto | root clock | ~0 |
| Triangoli blu | livelli `CLKBUF` | |
| Quadratini in basso | sink (CK dei FF) | ~0.07 |
| Spread verticale foglie | **skew** | piccolo se allineate |

Confronta con README: fanout ~4 al secondo livello. Se il tuo albero è diverso, non è un errore: clustering dipende dai sink.

Rileggi `cts.tcl` blocchi `clock_tree_synthesis` e `detailed_placement` (walkthrough).

---

## Parte 2 — Baseline CTS (15 min)

Prerequisito: `3_place.odb`.

```bash
./scripts/learn_physical_design.sh --deep --lesson 05
```

O:

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn cts
```

Se fallisce → Parte 4. Se passa:

```bash
rg -n 'DPL-0006|Inserted|RSZ-0062|worst slack' \
  logs/nangate45/gcd/learn/4_1_cts.log \
  reports/nangate45/gcd/learn/4_cts_final.rpt | head -40
```

Riferimento: util 40.5% → 48.3%, `Inserted 45 buffers`, possibile **RSZ-0062**, WNS −0.04.  
RSZ-0062 **non** è DPL-0038: il placement è legale, il timing no.

---

## Parte 3 — GUI e conteggio buffer (25 min)

```bash
# Pre
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_3_place.odb
# Post
make ... gui_4_cts.odb
```

Tcl:

```tcl
select -name "clkbuf*" -type Inst
select -name "clk" -type Net
```

O da shell sul Verilog/ODB dump:

```bash
rg -c 'CLKBUF' results/nangate45/gcd/learn/3_place.sdc
# meglio: netlist o report cell usage
rg -c 'CLKBUF_' results/nangate45/gcd/learn/6_final.v || true
```

Checklist atlante:

- [ ] `win_cts.png` vs la tua finestra
- [ ] Inspector net `clk` dopo route: `CTS_NDR_0` (lezione 07, ma la regola nasce qui)
- [ ] View → Clock Tree Viewer **oppure** PNG `orfs_cts_clock_tree.png`

Annota: buffer clock in più ≈ ______.

---

## Parte 4 — Debug intenzionale DPL-0038 (35 min)

**Un parametro per volta.** Backup SDC.

```bash
cp learn/designs/nangate45/gcd-tutorial/constraint.sdc \
   learn/workbook/backup-sdc-default.sdc
cp learn/designs/nangate45/gcd-tutorial/constraint_tight.sdc \
   learn/designs/nangate45/gcd-tutorial/constraint.sdc
```

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=55 \
     clean_synth clean_floorplan clean_place clean_cts
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=55 synth floorplan place cts
```

Atteso: **DPL-0038** (o fail affine) in `4_1_cts.log`.

```bash
rg -n 'DPL-0038|DPL-0006|Utilization greater' \
  logs/nangate45/gcd/learn/4_1_cts.log
```

Se esiste `4_1_error.odb`:

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_4_1_error.odb
```

**Fix (scegline UNO, documenta gli altri come ipotesi):**

- A: `CORE_UTILIZATION=30` + SDC tight
- B: SDC default 0.46 + util 55
- C: entrambi rilassati (controllo positivo)

Ripristino:

```bash
cp learn/workbook/backup-sdc-default.sdc \
   learn/designs/nangate45/gcd-tutorial/constraint.sdc
```

Workbook D1/D2. Diario: template in `debug-playbook.md`.

---

## Parte 5 — Report (15 min)

```bash
sed -n '1,40p' tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/4_cts_final.rpt
```

Compila:

| Campo | Valore |
|---|---|
| WNS | |
| setup skew | |
| source/target latency (prime due righe skew) | |
| setup violation count | |

Confronta con finish (`6_finish.rpt`): lo skew resta piccolo, le violazioni restano. Perché? (RC segnale, non solo clock)

---

## Parte 6 — Esame scritto (10 min)

1. Perché CTS richiama `detailed_placement`?
2. Differenza RSZ-0062 vs DPL-0038?
3. Un parametro che riduce DPL-0038 **senza** toccare lo SDC?
4. Cosa misura lo spread Y delle foglie nel clock tree PNG?

---

## Superamento

- [ ] Baseline CTS eseguito
- [ ] Tabella DPL-0006 / WNS
- [ ] DPL-0038 documentato (o spiegato perché *non* è comparso: util già bassa)
- [ ] Albero clock descritto
