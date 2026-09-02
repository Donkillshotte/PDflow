# Lesson 02 — Synthesis (Yosys → OpenROAD)

La synthesis is l'unico passo in cui il design is ancora **solo logica**. Dopo, every trasformazione is geometric o temporale.

## Objectives

- Distinguish Yosys (mapping) from OpenROAD (ODB import)
- Read gate-level netlist and `synth_stat.txt`
- Understand flatten vs hierarchical
- Aprire `1_synth.odb` e accettare che the cells siano impilate

## Reading

- This README
- `learn/reference/walkthrough-synth.tcl.md` (required)
- LAB 02
- RTL: `flow/designs/src/gcd/gcd.v`

## Real ORFS 26Q2 pipeline

```
gcd.v
  → synth_canonicalize.tcl → 1_1_yosys_canonicalize.rtlil
  → synth.tcl              → 1_2_yosys.v + 1_2_yosys.sdc
  → synth_odb.tcl          → 1_synth.odb + 1_synth.sdc
```

RTLIL is l'Yosys IR. If it exists, ORFS can avoid re-parsing Verilog.

## What Yosys does (intuition)

1. `read_verilog` / checkpoint RTLIL
2. `proc` — always block → netlist
3. `opt` — dead code, const fold
4. `synth -flatten` — coarse + fine, single module
5. `abc` — Boolean mapping onto liberty
6. `dfflegalize` — FF → `DFF_X1` ecc.

GCD is piccolo: flatten is il default corretto. Hierarchical synth you need su design con modules da non esplodere (memories, analog wrappers).

## Produced files

| Files | Description | Open with |
|---|---|---|
| `1_1_yosys_canonicalize.rtlil` | IR | editor (opaque) |
| `1_2_yosys.v` | Gate-level | editor, `sta` |
| `1_synth.odb` | DB OpenROAD | GUI |
| `synth_stat.txt` | Cell count | editor |
| `1_2_yosys.log` | Operational truth | `rg Warning` |

## What to observe in the netlist

```bash
rg -c 'DFF_' results/nangate45/gcd/learn/1_2_yosys.v
rg '^module ' results/nangate45/gcd/learn/1_2_yosys.v
```

Compare con `always @(posedge` nel RTL. Every registro RTL ≈ un DFF (more bits → more DFF).

**Latch:** if Yosys infers `DLATCH`, il RTL ha un incomplete combinational always. Su GCD should not succedere.

## GUI

`gui_1_synth.odb`: zoom out. Cells at one point **or black canvas** (die 0×0). PNG: `gui-shots/win_synth.png`. Display → Instances ON, Nets OFF.  
Seleziona una `DFF_X1` → Inspector → master.

Do not look for a “chip”: floorplan is not ancora esistito. Atlas: `gui-atlas.md` §5.1.

## Timing at this stage

`sta` + liberty + netlist + SDC = delay **without wires**. optimistic WNS or not comparable to finish (−0.04 ns SPEF sul run di riferimento).

## A reference `learn` run (`synth_stat.txt`)

| Voce | Valore |
|---|---|
| Celle | 496 |
| Area | 628.824 |
| `DFF_X1` | 35 (≈25% sequential area) |
| `NAND2_X1` | 128 |
| `CLKBUF_*` already in synth | 2 (is not CTS) |

I tuoi numeri: stessa tabella nel notebook. Se i DFF spariscono, Yosys ha optimizesto via registri: **bug RTL** o `current_design` sbagliato.

## How to read `synth_stat.txt`

Il file is un Yosys statistics dump. Cerca:

| Campo | Why |
|---|---|
| `Number of cells` | 496 sul run d’oro — se is 0, synth does not mappato |
| `DFF_X1` | 35 — must match `rg -c 'DFF_'` sul `.v` except aliases |
| `Chip area` | 628.824 — liberty units, not floorplan µm² |
| `CLKBUF_*` | 2 already in synth: **non** is l’albero CTS |

`ABC_AREA=1` in `config.mk`: ABC minimizes **area**, not delay. You chase timing
dal placement in poi. Do not be surprised se slack liberty-only di `sta` is diverso
dal finish SPEF (−0.04 ns). Tabella: `golden-metrics.md`.

## Power & SPICE chain

Synthesis instantiates **.lib cells** con modelli leakage/switching/internal → basis of `report_power` and SPICE mesh sinks. Deep dive: [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-02-synthesis) · demo [`nangate_inverter_demo.sp`](../../sim/spice/nangate_inverter_demo.sp).

| Link | Where |
|---|---|
| FlowLab | [synth](/flusso?phase=synth) |
| Liberty | `platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib` |

## Estimated duration

README + walkthrough 40 min, LAB 75 min, **total ~2 ore**.
