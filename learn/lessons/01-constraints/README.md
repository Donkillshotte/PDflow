# Lesson 01 — Constraints and design configuration

This is the most important lesson in the course. If SDC is wrong, **all** physical design is an optimizer chasing a false objective.

## Objectives

- Read and write an **SDC** file understanding every line
- Understand `config.mk` as the interface to ORFS (not magic)
- See the effect of constraints on **area** and **buffer count**, not just WNS
- Connect constraints → synthesis → placement → CTS (a chain, not silos)

## Required reading

1. This README
2. `LAB.md` for this lesson (90–120 min)
3. `learn/workbook/README.md` chapter A
4. `learn/reference/golden-metrics.md` (master table)
5. `learn/reference/gui-openroad.md` Charts section

## What is SDC?

SDC is the **timing contract** between RTL author and physical designer.

Static Timing Analysis **does not simulate** vectors. It propagates worst-case delay on paths. Without a clock, STA does not know what is “on time”.

| Command | Meaning | When you will use it |
|---|---|---|
| `create_clock` | Period and clock pin | Always |
| `set_input_delay` | Data arrival from pins vs clock | Almost always |
| `set_output_delay` | Budget toward the external world | Almost always |
| `set_false_path` | Path to ignore | Async resets, CDC |
| `set_multicycle_path` | Path over N cycles | Slow ALUs, rare on GCD |
| `set_clock_uncertainty` | Extra jitter/skew margin | Signoff, not in lesson 01 |
| `set_clock_latency` | Source/network latency | Pre-CTS vs post-CTS |

The course GCD uses only clock + I/O delay. This is intentional: memorize these three commands.

## Anatomy of our SDC

Files: `learn/designs/nangate45/gcd-tutorial/constraint.sdc`

```tcl
set clk_period 0.46          ;# ns → ~2.17 GHz
set clk_io_pct 0.2           ;# 20% of the period at pins
create_clock -name core_clock -period $clk_period [get_ports clk]
set_input_delay  [expr $clk_period * $clk_io_pct] -clock core_clock [all_inputs -no_clocks]
set_output_delay [expr $clk_period * $clk_io_pct] -clock core_clock [all_outputs]
```

**Required calculation:** `0.46 * 0.2 = 0.092 ns` input and output delay.

Setup interpretation on a register-register path:
- Available time ≈ `clk_period - setup_lib - uncertainty` (simplified)
- If combinational + wire > available → negative WNS

I/O path: input delay **eats** part of the period before internal logic even starts.

## Course files

```
learn/designs/nangate45/gcd-tutorial/
├── config.mk              # ORFS flow parameters
├── constraint.sdc         # default (0.46 ns)
├── constraint_relaxed.sdc # easy exercise (2.0 ns)
└── constraint_tight.sdc   # hard exercise (0.25 ns)
```

Three SDC files = three **product hypotheses**. Not three “random numbers”.

| File | Hypothesis | What you expect |
|---|---|---|
| relaxed 2.0 ns | slow, easy chip | few buffers, comfortable WNS |
| default 0.46 ns | realistic GCD ORFS 26Q2 target | some pre-route violation |
| tight 0.25 ns | overclock educational | RSZ explodes, CTS may fail |

## config.mk — parameters that affect physical design

| Variable | Effect | Coupling with SDC |
|---|---|---|
| `CORE_UTILIZATION` | % die for core | Tight clock needs more space |
| `SDC_FILE` | Which constraints | Direct |
| `PDN_TCL` | Power grid | IR drop, little direct timing |
| `PLACE_DENSITY_LB_ADDON` | GP density margin | Tight clock + high density = bad |
| `FLOW_VARIANT` | Results folder | Always `learn` in the course |

**Anti-pattern:** change SDC *and* utilization in the same experiment.

## Key concept: timing closure is an area problem

Causal chain to memorize:

```
tighter clock
  → more negative slack
    → resizer inserts buffer and upsize
      → instance area grows
        → same CORE_UTILIZATION becomes “full”
          → detailed placement CTS: DPL-0038
```

So SDC **is not just timing**. It is an input to **floorplan**.

## OpenSTA vs OpenROAD

- `sta` reads liberty + verilog + sdc → slack **without** real wires
- OpenROAD after place estimates RC from placement
- After route, SPEF is the best estimate

Do not compare synth slack with finish slack as if they were the same metric.

## Reference run (golden table)

File: `learn/reference/golden-metrics.md`.

On course default (util 35, 0.46 ns) at **place** worst slack is **+0.01 ns** and
`period_min` **0.45 ns**; at **finish** WNS **−0.04**, `period_min` **0.50 ns** (~2.01 GHz).
SDC target ~2.17 GHz **is not** closed. LAB relaxed/tight sweep measures
how much SDC shifts these numbers, not “whether make is green”.

## Exercises (summary — detail is in the LAB)

- 1-A SDC reading
- 1-B Relaxed clock + table
- 1-C Aggressive clock + debug
- 1-D GUI Endpoint Slack
- 1-E OpenSTA standalone (LAB)

Quiz: `learn/workbook/quiz.md` section 01.

## Power & SPICE chain

SDC and `config.mk` define **frequency and margin** → affect switching power at finish. See [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-01-constraints).

| Link | Where |
|---|---|
| FlowLab | [synth](/flow?phase=synth) (SDC preset) |
| Downstream | `report_power` at lesson 07 |

## Estimated duration

- README: 30–40 min
- LAB: 90–120 min
- Workbook A: 45–60 min
- **Total: 3–3.5 hours**
