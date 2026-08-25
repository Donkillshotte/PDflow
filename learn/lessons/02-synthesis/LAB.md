# LAB 02 — Synthesis (75–100 minuti)

Yosys mappa la logica. OpenROAD **non** piazza ancora niente. Se in GUI cerchi un chip, stai nella lezione sbagliata (vedi atlante, canvas nero).

## Obiettivi misurabili

- [ ] Confrontato RTL vs netlist con numeri (moduli, DFF, AND)
- [ ] Letto `synth_stat` / log Yosys e annotato area
- [ ] Spiegato canonicalize → synth → synth_odb
- [ ] Aperto `gui_1_synth.odb` (o studiato `gui-shots/win_synth.png`)
- [ ] Eseguito STA liberty-only e capito perché WNS ≠ signoff

---

## Parte 1 — RTL a mano (20 min)

File: `tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v`

Rispondi nel quaderno:

| Domanda | Tua risposta |
|---|---|
| Nome del modulo top | |
| Porte di clock/reset | |
| Quanti `always @(posedge` | |
| C’è un `always @*` incompleto? (rischio latch) | |
| A cosa servono `req_val` / `resp_rdy` (handshake) | |

Non serve capire l’algoritmo di Euclide in dettaglio. Serve capire: **è sincrono, ha un clock, ha I/O**. L’SDC della lezione 01 parla di quelle porte.

---

## Parte 2 — Walkthrough Tcl (20 min)

Apri **in parallelo**:

- `learn/reference/walkthrough-synth.tcl.md`
- `flow/scripts/synth.tcl`
- `flow/scripts/synth_odb.tcl`

Segna sul walkthrough (o quaderno) tre punti:

1. Perché esiste `1_1_yosys_canonicalize.rtlil`
2. Cosa fa `synth -flatten` al GCD
3. Cosa fa `load_design` in `synth_odb.tcl` (LEF + Verilog + SDC)

**Domanda d’esame:** chi produce `1_2_yosys.v` e chi `1_synth.odb`?

---

## Parte 3 — Esegui synth (10 min)

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn synth
```

Verifica:

```bash
ls -lh results/nangate45/gcd/learn/1_1_yosys_canonicalize.rtlil \
       results/nangate45/gcd/learn/1_2_yosys.v \
       results/nangate45/gcd/learn/1_synth.odb
```

Tutti e tre devono esistere. Se manca RTLIL, canonicalize non è partito (log `1_1`).

---

## Parte 4 — Conteggio celle (20 min)

```bash
# moduli
rg -c '^module ' tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v
rg -c '^module ' tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/1_2_yosys.v

# flip-flop
rg -c 'DFF_' tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/1_2_yosys.v

# family count
rg -oE '[A-Z0-9]+_X[0-9]+' \
  tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/1_2_yosys.v \
  | sort | uniq -c | sort -nr | head -20
```

Compila:

| Famiglia | Conteggio |
|---|---|
| DFF_* | |
| AND/NAND/NOR… (top 5) | |
| BUF/INV | |

Confronta con:

```bash
rg -n 'Chip area|Number of cells|Printing statistics' \
  tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/1_2_yosys.log
```

**Latch:** `rg DLATCH` sul netlist. Se trovi qualcosa, il RTL ha un always combinatorio pieno di buchi.

---

## Parte 5 — GUI synthesis (15 min)

Desktop Cursor →

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_1_synth.odb
```

Checklist atlante (`gui-atlas.md` §5.1):

- [ ] Canvas nero o blob in (0,0) — **non** un die
- [ ] Display Control mostra comunque metal1–metal10 (la tech LEF è caricata)
- [ ] Find `DFF` / Inspect master

Se non puoi aprire la GUI: studia `learn/reference/gui-shots/win_synth.png` e descrivi perché è vuoto.

---

## Parte 6 — OpenSTA pre-layout (15 min)

```bash
cd tools/OpenROAD-flow-scripts/flow
sta -no_init <<'EOF'
read_liberty platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
read_verilog results/nangate45/gcd/learn/1_2_yosys.v
link_design gcd
read_sdc designs/nangate45/gcd-tutorial/constraint.sdc
report_checks -max_paths 5
report_worst_slack -max
exit
EOF
```

Annota worst slack. **Non** confrontarlo col finish come se fosse la stessa metrica: qui i fili valgono ~0 (solo liberty).

---

## Superamento

- [ ] Tabella famiglie celle
- [ ] Differenza Yosys vs `synth_odb` spiegata in 4 righe
- [ ] STA eseguita
- [ ] GUI o PNG synth annotato nel quaderno
