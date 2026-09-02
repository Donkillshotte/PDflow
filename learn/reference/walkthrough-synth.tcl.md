# Annotated walkthrough — synthesis (Yosys + synth_odb.tcl)

Synthesis in ORFS 26Q2 is **two tools chained**:

```
gcd.v
  -- synth_canonicalize.tcl --> 1_1_yosys_canonicalize.rtlil
  -- synth.tcl              --> 1_2_yosys.v + 1_2_yosys.sdc
  -- synth_odb.tcl          --> 1_synth.odb + 1_synth.sdc
```

Open scripts in `flow/scripts/` while you read. GUI: black canvas, `gui-shots/win_synth.png`.

---

## Statistics of a `learn` run (your `synth_stat.txt`)

Reference:

- **496** cells, area **628.824** (liberty units)
- **35** `DFF_X1` (25% of area is sequential)
- many `NAND2_X1` (128) — ABC mapped aggressively to NAND
- already **2** `CLKBUF_*` in synth (this is not the CTS tree)

If your DFFs are 34 or 36: bit-blast / opt. If you see `DLATCH`, stop: RTL combinational bug.

---

## Why canonicalize then synth

1. **Canonicalize** reads Verilog, normalizes, writes RTLIL.  
2. **Synth** restarts from checkpoint, `synth -flatten`, ABC, `dfflegalize`.

ORFS can skip the Verilog parse if RTLIL is fresh. For you: if `1_1_*.rtlil` exists and `make synth` is “too fast”, it is reusing the checkpoint.

`ABC_AREA=1` in tutorial `config.mk`: ABC optimizes **area**, not delay. This is an educational choice: you chase timing later, not in synth.

`ADDER_MAP_FILE :=` empty: no custom adder techmap.

---

## Hierarchy (`synth.tcl`)

```tcl
read_checkpoint $::env(RESULTS_DIR)/1_1_yosys_canonicalize.rtlil
hierarchy -check -top $::env(DESIGN_NAME)
```

`DESIGN_NAME` (`gcd`) = `current_design` in the SDC. If they differ, STA does not find the clock.

Flatten: a single `module gcd` in `1_2_yosys.v`. Hierarchical (`SYNTH_HIERARCHICAL=1`) would keep islands: on GCD useless; on SoC with SRAM required.

---

## Nangate45 mapping

Liberty: `platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib`.

Drive `X1/X2/X4`: same function, wider transistors, more area, better slew. Synth mostly uses X1; RSZ in place/CTS will upsize.

```bash
rg -oE '[A-Z0-9]+_X[0-9]+' results/nangate45/gcd/learn/1_2_yosys.v \
  | sort | uniq -c | sort -nr | head
```

---

## `synth_odb.tcl` (OpenROAD, ~14 lines)

```tcl
load_design 1_2_yosys.v 1_2_yosys.sdc
orfs_write_db  .../1_synth.odb
orfs_write_sdc .../1_synth.sdc
```

`load_design` on Verilog: LEF tech + cell LEF, `link_design gcd`.  
The written SDC is **canonicalized** (no `source util.tcl`): compare with `constraint.sdc`.

Die 0×0: `save_image` headless often does not write PNG. Normal.

---

## Timing at this stage

`sta` + liberty + netlist + SDC = delay **without wires**. Do not compare that WNS with finish (−0.04 ns SPEF) as if they were the same metric.

---

## Checkpoint

1. RTLIL vs gate-level `.v`?
2. Who maps `always @(posedge clk)` → `DFF_X1`?
3. Why `1_synth.sdc` ≠ `constraint.sdc` byte-per-byte?
4. What does 25% sequential area mean for CTS?
