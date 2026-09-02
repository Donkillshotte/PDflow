# LAB 02 — Synthesis (75–100 minutes)

Yosys maps logic. OpenROAD **does not** place anything yet. If in the GUI you look for a chip, you are in the wrong lesson (see atlas, black canvas).

## Measurable objectives

- [ ] Compared RTL vs netlist with numbers (modules, DFF, AND)
- [ ] Read `synth_stat` / Yosys log and noted area
- [ ] Explained canonicalize → synth → synth_odb
- [ ] Opened `gui_1_synth.odb` (or studied `gui-shots/win_synth.png`)
- [ ] Ran liberty-only STA and understood why WNS ≠ signoff

---

## Part 1 — RTL by hand (20 min)

File: `tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v`

Answer in the notebook:

| Question | Your answer |
|---|---|
| Top module name | |
| Clock/reset ports | |
| How many `always @(posedge` | |
| Is there an incomplete `always @*`? (latch risk) | |
| What `req_val` / `resp_rdy` do (handshake) | |

You do not need to understand Euclid's algorithm in detail. You need to understand: **it is synchronous, has a clock, has I/O**. The lesson 01 SDC talks about those ports.

---

## Part 2 — Walkthrough Tcl (20 min)

Open **in parallel**:

- `learn/reference/walkthrough-synth.tcl.md`
- `flow/scripts/synth.tcl`
- `flow/scripts/synth_odb.tcl`

Mark on the walkthrough (or notebook) three points:

1. Why `1_1_yosys_canonicalize.rtlil` exists
2. What `synth -flatten` does to GCD
3. What `load_design` does in `synth_odb.tcl` (LEF + Verilog + SDC)

**Exam question:** who produces `1_2_yosys.v` and who `1_synth.odb`?

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

All three must exist. If RTLIL is missing, canonicalize did not run (check log `1_1`).

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

Compare with:

```bash
rg -n 'Chip area|Number of cells|Printing statistics' \
  tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/1_2_yosys.log
```

**Latch:** `rg DLATCH` on the netlist. If you find something, the RTL has a combinational always full of holes.

---

## Part 5 — GUI synthesis (15 min)

Desktop Cursor →

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_1_synth.odb
```

Checklist atlas (`gui-atlas.md` §5.1):

- [ ] Black canvas or blob at (0,0) — **not** a die
- [ ] Display Control still shows metal1–metal10 (tech LEF is loaded)
- [ ] Find `DFF` / Inspect master

If you cannot open the GUI: study `learn/reference/gui-shots/win_synth.png` and describe why it is empty.

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

Note worst slack. **Do not** compare it with finish as if it were the same metric: here wires are ~0 (liberty only).

---

## Pass criteria

- [ ] Cell family table
- [ ] Yosys vs `synth_odb` difference explained in 4 lines
- [ ] STA run
- [ ] GUI or synth PNG annotated in the notebook
