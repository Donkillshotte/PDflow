# Walkthrough annotato — synthesis (Yosys + synth_odb.tcl)

La sintesi in ORFS è **due tool concatenati**:

```
gcd.v  --Yosys Tcl-->  1_2_yosys.v  --OpenROAD synth_odb.tcl-->  1_synth.odb
```

File Yosys: `flow/scripts/synth.tcl` (+ `synth_canonicalize.tcl`, `synth_preamble.tcl`)  
File OpenROAD: `flow/scripts/synth_odb.tcl`

---

## Perché due passi (canonicalize poi synth)

ORFS 26Q2 divide:

1. **Canonicalize** (`synth_canonicalize.tcl`) → `1_1_yosys_canonicalize.rtlil`  
   Legge Verilog, normalizza, scrive RTLIL checkpoint.
2. **Synth** (`synth.tcl`) → `1_2_yosys.v`  
   Riparte dal checkpoint, ottimizza, mappa alla libreria.

**Perché:** Bazel/ORFS può rieseguire synth senza rileggere Verilog se RTLIL è già valido. Per te: se `1_1_*.rtlil` esiste, `make synth` può saltare parse RTL.

---

## Blocco 1 — gerarchia (synth.tcl ~35–51)

```tcl
read_checkpoint $::env(RESULTS_DIR)/1_1_yosys_canonicalize.rtlil
hierarchy -check -top $::env(DESIGN_NAME)
```

- `hierarchy -check` verifica che `gcd` esista e che i moduli siano collegati
- `DESIGN_NAME` deve coincidere con `current_design` nell'SDC

**Errore tipico:** SDC `current_design foo` ma Verilog `module gcd` → STA non trova clock.

---

## Blocco 2 — synth -flatten (righe 68–74)

```tcl
if { !$::env(SYNTH_HIERARCHICAL) } {
  synth -flatten -run :fine {*}$synth_full_args
}
```

Per GCD: **flatten**. Tutti i moduli interni spariscono: un unico netlist gate-level.

`synth` di Yosys internamente:
1. elaborazione RTL (`proc`, `opt`)
2. mapping tecnologia (`techmap`, `abc`/`abc9`)
3. `dfflegalize` — flip-flop mappati a celle `DFF_X*` della libreria

**Domanda:** se tenessi gerarchia (`SYNTH_HIERARCHICAL=1`), cosa cambierebbe nel placement? (macro/moduli come isole)

---

## Blocco 3 — mapping libreria Nangate45

Yosys usa `LIB_FILES` del platform (`NangateOpenCellLibrary_typical.lib`).  
Output: istanze `AND2_X1`, `NAND2_X1`, `DFF_X1`, `BUF_X1`, …

**Esercizio:** `rg -o ' [A-Z0-9_]+_X[0-9]+ ' 1_2_yosys.v | sort | uniq -c | sort -nr | head`

---

## Blocco 4 — synth_odb.tcl (OpenROAD, 14 righe)

```tcl
load_design 1_2_yosys.v 1_2_yosys.sdc
orfs_write_db $::env(RESULTS_DIR)/1_synth.odb
orfs_write_sdc $::env(RESULTS_DIR)/1_synth.sdc
```

`load_design` su Verilog:
- legge LEF tech + LEF celle
- `read_verilog` + `link_design gcd`
- SDC canonicalizzato (niente `source util.tcl` residui)

**GUI:** `gui_1_synth.odb` — celle **non piazzate** (stack in 0,0). Se vedi un blob nel corner, è normale.

---

## Cosa NON fa la synthesis

- Non piazza celle
- Non crea clock tree
- Non stima wire delay reali (STA ideale / zero wire o liberty delay only)

Quindi WNS post-synth **non** è il WNS di signoff.

---

## Checkpoint comprensione

1. Differenza RTLIL vs Verilog gate-level?
2. Chi mappa `always @(posedge clk)` a `DFF_X1`?
3. Perché `1_synth.sdc` può differire dal tuo `constraint.sdc`? (canonicalizzazione OpenSTA)
