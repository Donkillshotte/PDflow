# Walkthrough annotato — synthesis (Yosys + synth_odb.tcl)

La sintesi in ORFS 26Q2 è **due tool concatenati**:

```
gcd.v
  -- synth_canonicalize.tcl --> 1_1_yosys_canonicalize.rtlil
  -- synth.tcl              --> 1_2_yosys.v + 1_2_yosys.sdc
  -- synth_odb.tcl          --> 1_synth.odb + 1_synth.sdc
```

Apri gli script in `flow/scripts/` mentre leggi. GUI: canvas nero, `gui-shots/win_synth.png`.

---

## Statistiche di un run `learn` (tuo `synth_stat.txt`)

Riferimento:

- **496** celle, area **628.824** (unità liberty)
- **35** `DFF_X1` (25% dell’area è sequenziale)
- tante `NAND2_X1` (128) — ABC ha mappato aggressivo su NAND
- già **2** `CLKBUF_*` in synth (non è l’albero CTS)

Se i tuoi DFF sono 34 o 36: bit-blast / opt. Se vedi `DLATCH`, stop: RTL combinatorio buggato.

---

## Perché canonicalize poi synth

1. **Canonicalize** legge Verilog, normalizza, scrive RTLIL.  
2. **Synth** riparte dal checkpoint, `synth -flatten`, ABC, `dfflegalize`.

ORFS può saltare il parse Verilog se RTLIL è fresco. Per te: se `1_1_*.rtlil` esiste e `make synth` è “troppo veloce”, sta riusando il checkpoint.

`ABC_AREA=1` nel `config.mk` tutorial: ABC ottimizza **area**, non delay. È una scelta didattica: il timing lo insegui dopo, non in synth.

`ADDER_MAP_FILE :=` vuoto: niente techmap adder custom.

---

## Gerarchia (`synth.tcl`)

```tcl
read_checkpoint $::env(RESULTS_DIR)/1_1_yosys_canonicalize.rtlil
hierarchy -check -top $::env(DESIGN_NAME)
```

`DESIGN_NAME` (`gcd`) = `current_design` nell’SDC. Se divergono, STA non trova il clock.

Flatten: un solo `module gcd` in `1_2_yosys.v`. Hierarchical (`SYNTH_HIERARCHICAL=1`) terrebbe isole: sul GCD è inutile; su un SoC con SRAM è obbligatorio.

---

## Mapping Nangate45

Liberty: `platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib`.

Drive `X1/X2/X4`: stessa funzione, transistor più larghi, più area, migliore slew. Synth mette soprattutto X1; RSZ in place/CTS farà upsize.

```bash
rg -oE '[A-Z0-9]+_X[0-9]+' results/nangate45/gcd/learn/1_2_yosys.v \
  | sort | uniq -c | sort -nr | head
```

---

## `synth_odb.tcl` (OpenROAD, ~14 righe)

```tcl
load_design 1_2_yosys.v 1_2_yosys.sdc
orfs_write_db  .../1_synth.odb
orfs_write_sdc .../1_synth.sdc
```

`load_design` su Verilog: LEF tech + LEF celle, `link_design gcd`.  
L’SDC scritto è **canonicalizzato** (niente `source util.tcl`): confronta con `constraint.sdc`.

Die 0×0: `save_image` headless spesso non scrive PNG. Normale.

---

## Timing a questo stadio

`sta` + liberty + netlist + SDC = delay **senza wire**. Non confrontare quel WNS col finish (−0.04 ns SPEF) come se fossero la stessa metrica.

---

## Checkpoint

1. RTLIL vs gate-level `.v`?
2. Chi mappa `always @(posedge clk)` → `DFF_X1`?
3. Perché `1_synth.sdc` ≠ `constraint.sdc` byte-per-byte?
4. Cosa significa 25% area sequenziale per il CTS?
