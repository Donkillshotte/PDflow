# Lesson 01 — Constraints e configurazione design

This is the most important lesson in the course. If SDC is wrong, **all** physical design is an optimizer chasing a false objective.

## Objectives

- Leggere e scrivere un file **SDC** capendo every riga
- Capire `config.mk` come interface to ORFS (not magic)
- Vedere l'effect of constraints on **area** and **buffer count**, non solo su WNS
- Collegare constraints → synthesis → placement → CTS (catena, non silos)

## Required reading

1. This README
2. `LAB.md` di this lesson (90–120 min)
3. `learn/workbook/README.md` capitolo A
4. `learn/reference/golden-metrics.md` (tabella maestra)
5. `learn/reference/gui-openroad.md` sezione Charts

## Cos'is l'SDC?

L'SDC is il **timing contract** between RTL author and physical designer.

Static Timing Analysis **does not simulate** vectors. Propagates worst-case delay on paths. Without clock, STA does not know cosa is “in tempo”.

| Comando | Meaning | When you will use it |
|---|---|---|
| `create_clock` | Periodo e pin del clock | Always |
| `set_input_delay` | Arrivo dati dai pin vs clock | Almost always |
| `set_output_delay` | Budget verso il mondo esterno | Almost always |
| `set_false_path` | Path da ignorare | Async resets, CDC |
| `set_multicycle_path` | Path su N cicli | Slow ALUs, rare on GCD |
| `set_clock_uncertainty` | Extra jitter/skew margin | Signoff, not in lesson 01 |
| `set_clock_latency` | Source/network latency | Pre-CTS vs post-CTS |

GCD del course use solo clock + I/O delay. Is intentional: memorize these three commands.

## Anatomy of our SDC

Files: `learn/designs/nangate45/gcd-tutorial/constraint.sdc`

```tcl
set clk_period 0.46          ;# ns → ~2.17 GHz
set clk_io_pct 0.2           ;# 20% del periodo ai pin
create_clock -name core_clock -period $clk_period [get_ports clk]
set_input_delay  [expr $clk_period * $clk_io_pct] -clock core_clock [all_inputs -no_clocks]
set_output_delay [expr $clk_period * $clk_io_pct] -clock core_clock [all_outputs]
```

**Calcolo required:** `0.46 * 0.2 = 0.092 ns` di input e output delay.

Setup interpretation on a register-register path:
- Available time ≈ `clk_period - setup_lib - uncertainty` (simplified)
- If combinational + wire > available → negative WNS

I/O path: input delay **eats** part of the period before ancora della logica interna.

## Files del course

```
learn/designs/nangate45/gcd-tutorial/
├── config.mk              # ORFS flow parameters
├── constraint.sdc         # default (0.46 ns)
├── constraint_relaxed.sdc # exercise facile (2.0 ns)
└── constraint_tight.sdc   # exercise difficile (0.25 ns)
```

Tre SDC = three **product hypotheses**. Non tre “random numbers”.

| Files | Hypothesis | What you expect |
|---|---|---|
| relaxed 2.0 ns | slow, easy chip | few buffers, comfortable WNS |
| default 0.46 ns | realistic GCD ORFS 26Q2 target | some pre-route violation |
| tight 0.25 ns | overclock educational | RSZ explodes, CTS may fail |

## config.mk — parameters that affect physical design

| Variabile | Effetto | Accoppiamento con SDC |
|---|---|---|
| `CORE_UTILIZATION` | % die for core | Tight clock needs more space |
| `SDC_FILE` | Which constraints | Direct |
| `PDN_TCL` | Power grid | IR drop, little direct timing |
| `PLACE_DENSITY_LB_ADDON` | GP density margin | Tight clock + high density = bad |
| `FLOW_VARIANT` | Results folder | Always `learn` nel course |

**Anti-pattern:** change SDC *and* utilization in the same experiment.

## Key concept: timing closure is a problem di area

Causal chain to memorize:

```
tighter clock
  → more negative slack
    → resizer inserts buffer and upsize
      → instance area grows
        → same CORE_UTILIZATION becomes “full”
          → detailed placement CTS: DPL-0038
```

Quindi SDC **is not solo timing**. Is un input to **floorplan**.

## OpenSTA vs OpenROAD

- `sta` reads liberty + verilog + sdc → slack **without** real wires
- OpenROAD after place stima RC da placement
- After route, SPEF is la stima migliore

Do not compare synth slack con slack finish as if they were the same metric.

## Run di riferimento (tabella d’oro)

Files: `learn/reference/golden-metrics.md`.

On course default (util 35, 0.46 ns) a **place** worst slack is **+0.01 ns** e
`period_min` **0.45 ns**; a **finish** WNS **−0.04**, `period_min` **0.50 ns** (~2.01 GHz).
SDC target ~2.17 GHz **non** is chiuso. LAB relaxed/tight sweep measures
quanto l’SDC sposta questi numeri, non “se make is green”.

## Exercises (summary — detail is nel LAB)

- 1-A SDC reading
- 1-B Relaxed clock + table
- 1-C Aggressive clock + debug
- 1-D GUI Endpoint Slack
- 1-E OpenSTA standalone (LAB)

Quiz: `learn/workbook/quiz.md` sezione 01.

## Power & SPICE chain

SDC e `config.mk` define **frequency and margin** → affect switching power at finish. See [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-01-constraints).

| Link | Where |
|---|---|
| FlowLab | [synth](/flusso?phase=synth) (SDC preset) |
| Downstream | `report_power` a lesson 07 |

## Estimated duration

- README: 30–40 min
- LAB: 90–120 min
- Workbook A: 45–60 min
- **Totale: 3–3.5 ore**
