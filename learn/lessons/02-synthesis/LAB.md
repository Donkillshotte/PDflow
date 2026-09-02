# LAB 02 — Synthesis (75–100 minuti)

Yosys maps logic. OpenROAD **does not** place anything yet. Se in GUI cerchi un chip, stai in the lesson sbagliata (see atlas, black canvas).

## Measurable objectives

- [ ] Compared RTL vs netlist with numbers (modules, DFF, AND)
- [ ] Read `synth_stat` / Yosys log and noted area
- [ ] Explained canonicalize → synth → synth_odb
- [ ] Opened `gui_1_synth.odb` (o studiato `gui-shots/win_synth.png`)
- [ ] Eseguito STA liberty-only e capito because WNS ≠ signoff

---

## Part 1 — RTL by hand (20 min)

Files: `tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v`

Rispondi nel notebook:

| Domanda | Your answer |
|---|---|
| Nome del modulo top | |
| Clock/reset ports | |
| How many `always @(posedge` | |
| C’is un `always @*` incompleto? (rischio latch) | |
| What `req_val` / `resp_rdy` do (handshake) | |

You do not need capire l’algoritmo di Euclide in dettaglio. You need to understand: **is synchronous, has a clock, has I/O**. L’SDC of the lesson 01 parla di that ports.

---

## Part 2 — Walkthrough Tcl (20 min)

Open **in parallel**:

- `learn/reference/walkthrough-synth.tcl.md`
- `flow/scripts/synth.tcl`
- `flow/scripts/synth_odb.tcl`

Mark on walkthrough (o notebook) tre punti:

1. Why esiste `1_1_yosys_canonicalize.rtlil`
2. What `synth -flatten` does to GCD
3. What `load_design` does in `synth_odb.tcl` (LEF + Verilog + SDC)

**Domanda d’esame:** who produces `1_2_yosys.v` e chi `1_synth.odb`?

---

## Part 3 — Run synth (10 min)

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 synth
```

Verify:

```bash
ls -lh results/nangate45/gcd/learn/1_1_yosys_canonicalize.rtlil \
       results/nangate45/gcd/learn/1_2_yosys.v \
       results/nangate45/gcd/learn/1_synth.odb
```

All e tre devono esistere. If missing RTLIL, canonicalize is not partito (log `1_1`).

---

## Part 4 — Cell count (20 min)

```bash
# modules
rg -c '^module ' tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v
rg -c '^module ' tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/1_2_yosys.v

# flip-flop
rg -c 'DFF_' tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/1_2_yosys.v

# family count
rg -oE '[A-Z0-9]+_X[0-9]+' \
  tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/1_2_yosys.v \
  | sort | uniq -c | sort -nr | head -20
```

Fill in:

| Family | Count |
|---|---|
| DFF_* | |
| AND/NAND/NOR… (top 5) | |
| BUF/INV | |

Compare con:

```bash
rg -n 'Chip area|Number of cells|Printing statistics' \
  tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/1_2_yosys.log
```

**Latch:** `rg DLATCH` sul netlist. If you find something, il RTL ha un always combinatorio pieno di holes.

---

## Part 5 — GUI synthesis (15 min)

Desktop Cursor →

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_1_synth.odb
```

Checklist atlas (`gui-atlas.md` §5.1):

- [ ] Black canvas or blob at (0,0) — **not** a die
- [ ] Display Control still shows metal1–metal10 (la tech LEF is caricata)
- [ ] Find `DFF` / Inspect master

Se non you can aprire the GUI: studia `learn/reference/gui-shots/win_synth.png` e describe because is vuoto.

---

## Part 6 — OpenSTA pre-layout (15 min)

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

Note worst slack. **Non** confrontarlo col finish come se fosse la stessa metric: here wires are ~0 (liberty only).

---

## Pass criteria

- [ ] Table famiglie celle
- [ ] Yosys vs `synth_odb` differencand explained in 4 lines
- [ ] STA run
- [ ] GUI or PNG synth annotato nel notebook
