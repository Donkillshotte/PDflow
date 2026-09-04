# Lesson 00 — Introduction to Physical Design

This is the **digital physical design** course on OpenROAD / ORFS
(Nangate45 / FreePDK45).

This lesson is the map for the rest of the course. If you skip it,
lessons 03–07 are harder to debug.

## Objectives

- Understand the **RTL → GDSII** map as a chain of *contracts* (file in, file out)
- Orient yourself in ORFS without getting lost among 2000 files
- Know which **files** and which **GUI commands** you use at each stage
- Distinguish **tools** (OpenROAD, Yosys, OpenSTA, KLayout) from **scripts** (ORFS)
- Run a first toolchain smoke test

## Required reading (before exercises)

1. This README (~15 min)
2. `learn/reference/glossary.md` — sections C, F, P, S, T (~20 min)
3. `learn/reference/file-formats.md` (~20 min)
4. `learn/reference/gui-openroad.md` — Startup section only (~10 min)
5. `learn/reference/golden-metrics.md` — what a reference run is (~10 min)
6. `learn/lessons/00-intro/LAB.md` (~60 min practice)

## What “physical design” means

**Logical design** (RTL) says *what* the chip computes.  
**Physical design** says *where* transistors and wires sit, *how much* they delay, and *whether* the fab can print them.

OpenROAD automates the second part. You must understand enough to:
- give realistic constraints
- read a failure
- not accept a “green” GDS without checking WNS and DRC

## The flow as a contract chain

```
Verilog + SDC
    → Synthesis     contract: gate-level netlist + liberty delay
    → Floorplan     contract: die/core/rows/PDN (still without placed cells)
    → Placement     contract: every cell has legal (x,y)
    → CTS           contract: clock distributed with controlled skew
    → Routing       contract: every net has DRC-clean geometry
    → Finish        contract: GDS + SPEF + signoff reports
```

Each stage **breaks** the previous contract in a controlled way (adds buffers, moves cells) and writes a new one to disk (`.odb`).

## Who does what (tools vs ORFS)

| Component | Role |
|---|---|
| **Yosys** | Logical synthesis (RTL → gates) |
| **OpenROAD** | Floorplan, place, CTS, route, GUI, integrated STA |
| **OpenSTA** | Timing analysis (also standalone `sta`) |
| **KLayout** | GDS merge/view |
| **ORFS** | Makefile + Tcl that *orchestrate* the tools |

Without ORFS you would write 50 Tcl scripts. With ORFS you have targets like `make floorplan`. The course makes you **open** those scripts, not hide them.

## ORFS structure (key folders)

| Folder | Contents |
|---|---|
| `flow/designs/` | Design config (`config.mk`), constraints (`constraint.sdc`), RTL |
| `flow/platforms/nangate45/` | PDK: LEF, LIB, technology rules |
| `flow/scripts/` | Tcl scripts per stage (`floorplan.tcl`, `global_place.tcl`, …) |
| `flow/results/.../learn/` | Course `.odb` snapshots (`learn` variant) |
| `flow/logs/.../learn/` | Detailed logs per step |
| `flow/reports/.../learn/` | Timing, area, DRC reports |

**Golden rule:** if you do not understand a result, open the **log** for that stage before the GUI.

## Tutorial design: GCD

The **GCD** (Greatest Common Divisor) is a small core (~250 cells) on **Nangate45** (open PDK, educational 45 nm).

Why GCD and not a RISC-V:
- a full run takes **minutes**, not hours
- CTS and routing are still real
- you can SDC sweep/utilization in the same afternoon

Limit: you will not learn SRAM macros, hierarchical floorplan, or MCMM. That is fine: flow first, then scale.

## Two learning modes

1. **Files / Makefile** — understand input/output, change parameters, re-read reports
2. **OpenROAD GUI** — visually inspect layout, timing paths, congestion, clock tree

Both are required. Files only = you do not “see” congestion. GUI only = you cannot reproduce.

> For the GUI use the **Desktop** button on [cursor.com/agents](https://cursor.com/agents) (not chat Preview cards). Details: `learn/reference/gui-openroad.md`.

## Artifacts per stage (quick reference)

| Stage | make target | Typical GUI snapshot | Tcl walkthrough |
|---|---|---|---|
| Synth | `synth` | `gui_1_synth.odb` | `reference/walkthrough-synth.tcl.md` |
| Floorplan | `floorplan` | `gui_2_1_floorplan.odb`, `gui_2_4_floorplan_pdn.odb` | `walkthrough-floorplan.tcl.md` |
| Place | `place` | `gui_3_3_place_gp.odb`, `gui_3_5_place_dp.odb` | `walkthrough-global_place.tcl.md` |
| CTS | `cts` | `gui_4_1_cts.odb` | `walkthrough-cts.tcl.md` |
| Route | `route` | `gui_5_1_grt.odb`, `gui_5_2_route.odb` | `walkthrough-route.tcl.md` |
| Finish | `finish` | `gui_final` | `walkthrough-finish.tcl.md` |

## Mistakes you will make (and that is fine)

- Run `make` without `FLOW_VARIANT=learn` and pollute `base`
- Change SDC and utilization together and not know who broke CTS
- Only look at the GUI and ignore `DPL-0038` in the log
- Use Preview instead of Desktop and think OpenROAD crashed
- Believe green `make finish` = 2.17 GHz closed (check `period_min` in `golden-metrics.md`)

Playbook: `learn/reference/debug-playbook.md`.

## Power & SPICE chain

This lesson is the **first link** in the power integrity chain documented in [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-00-intro).

| Link | Where |
|---|---|
| FlowLab | [RTL stage](/flow?phase=rtl) · `rtl_sim` action |
| Output | `learn/sim/gcd/gcd.vcd` (toggles → future activity) |
| Next power lesson | 02 synthesis (liberty) → 07 finish (`report_power`, [`signoff-matrix`](../../reference/signoff-matrix.md)) |

## Estimated duration

- README + glossary: 45–60 min
- LAB 00: 60 min
- **Lesson 00 total: ~2 hours** if done properly
