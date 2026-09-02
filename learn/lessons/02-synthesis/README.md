# Lesson 02 — Synthesis (Yosys → OpenROAD)

Synthesis is the only step where the design is still **pure logic**. After that, every transformation is geometric or temporal.

## Objectives

- Distinguish Yosys (mapping) from OpenROAD (ODB import)
- Read gate-level netlist and `synth_stat.txt`
- Understand flatten vs hierarchical
- Open `1_synth.odb` and accept that cells are stacked

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

RTLIL is the Yosys IR. If it exists, ORFS can avoid re-parsing Verilog.

## What Yosys does (intuition)

1. `read_verilog` / checkpoint RTLIL
2. `proc` — always block → netlist
3. `opt` — dead code, const fold
4. `synth -flatten` — coarse + fine, single module
5. `abc` — Boolean mapping onto liberty
6. `dfflegalize` — FF → `DFF_X1` etc.

GCD is small: flatten is the correct default. Hierarchical synth is needed on designs with modules you must not explode (memories, analog wrappers).

## Produced files

| File | Description | Open with |
|---|---|---|
| `1_1_yosys_canonicalize.rtlil` | IR | editor (opaque) |
| `1_2_yosys.v` | Gate-level | editor, `sta` |
| `1_synth.odb` | OpenROAD DB | GUI |
| `synth_stat.txt` | Cell count | editor |
| `1_2_yosys.log` | Operational truth | `rg Warning` |

## What to observe in the netlist

```bash
rg -c 'DFF_' results/nangate45/gcd/learn/1_2_yosys.v
rg '^module ' results/nangate45/gcd/learn/1_2_yosys.v
```

Compare with `always @(posedge` in the RTL. Every RTL register ≈ one DFF (more bits → more DFF).

**Latch:** if Yosys infers `DLATCH`, the RTL has an incomplete combinational always. On GCD that should not happen.

## GUI

`gui_1_synth.odb`: zoom out. Cells at one point **or black canvas** (die 0×0). PNG: `gui-shots/win_synth.png`. Display → Instances ON, Nets OFF.  
Select a `DFF_X1` → Inspector → master.

Do not look for a “chip”: floorplan does not exist yet. Atlas: `gui-atlas.md` §5.1.

## Timing at this stage

`sta` + liberty + netlist + SDC = delay **without wires**. Optimistic WNS or not comparable to finish (−0.04 ns SPEF on the reference run).

## A reference `learn` run (`synth_stat.txt`)

| Item | Value |
|---|---|
| Cells | 496 |
| Area | 628.824 |
| `DFF_X1` | 35 (≈25% sequential area) |
| `NAND2_X1` | 128 |
| `CLKBUF_*` already in synth | 2 (this is not CTS) |

Your numbers: same table in the notebook. If DFFs disappear, Yosys optimized away registers: **RTL bug** or wrong `current_design`.

## How to read `synth_stat.txt`

The file is a Yosys statistics dump. Look for:

| Field | Why |
|---|---|
| `Number of cells` | 496 on golden run — if 0, synth did not map |
| `DFF_X1` | 35 — must match `rg -c 'DFF_'` on `.v` except aliases |
| `Chip area` | 628.824 — liberty units, not floorplan µm² |
| `CLKBUF_*` | 2 already in synth: **not** the CTS tree |

`ABC_AREA=1` in `config.mk`: ABC minimizes **area**, not delay. You chase timing
from placement onward. Do not be surprised if liberty-only `sta` slack differs
from finish SPEF (−0.04 ns). Table: `golden-metrics.md`.

## Power & SPICE chain

Synthesis instantiates **.lib cells** with leakage/switching/internal models → basis of `report_power` and SPICE mesh sinks. Deep dive: [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-02-synthesis) · demo [`nangate_inverter_demo.sp`](../../sim/spice/nangate_inverter_demo.sp).

| Link | Where |
|---|---|
| FlowLab | [synth](/flusso?phase=synth) |
| Liberty | `platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib` |

## Estimated duration

README + walkthrough 40 min, LAB 75 min, **total ~2 hours**.
