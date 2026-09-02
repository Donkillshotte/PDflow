# Vectorless and dynamic power/IR (GCD Nangate45)

OpenSTA/OpenROAD do not have a commercial “vectorless IR signoff” (PrimeTime PX vectorless, RedHawk-static). Here the course **implements** the two pieces papers define, and runs them on the routed GCD.

## Literature (method, not copied code)

1. **F. Najm**, *A survey of power estimation techniques in VLSI circuits*, Proc. IEEE 1994.  
   Transition probability \(P_{01} = p(1-p)\) with \(p=0.5\) combinational and \(p=0.1\) sequential.
2. **D. Kouroussis & F. Najm**, *A static pattern-independent technique for power grid voltage integrity verification*, DAC 2003.  
   Instance currents in \([0, I_{\max}]\), chip budget (not all ports switch to \(I_{\max}\) together), IR estimate **without vectors**.

## Two modes in the same ODB

| Mode | Activity | Script / TCL |
|---|---|---|
| **Vectorless** | `set_power_activity -global -activity 0.5` | `POWER_MODE=vectorless` |
| **Dynamic** | `read_vcd -scope tb_gcd/dut learn/sim/gcd/gcd.vcd` | `POWER_MODE=dynamic` (default `auto` if VCD exists) |

OpenSTA 26Q2: `read_power_activities` is deprecated and calls `read_vcd` with the wrong arity. The helper is `learn/lib/power_vcd.sh`.

Icarus VCD notes **names that match** the gate netlist (in practice the ports). Unannotated pins stay on OpenSTA defaults. **Do not** run `set_power_activity -global` after VCD: would overwrite annotation.

**Note — STA-1452**: testbench uses 10 ns period, SDC 0.46 ns. Dynamic watts are not 1:1 with vectorless — educational data, not foundry sign-off.

## Envelope IR

`learn/scripts/vectorless_analysis.py`:

- \(I_\mathrm{avg} = P_\mathrm{vectorless} / V_{DD}\)
- budget chip \(I_\mathrm{avg} \times 3\) (crest)
- area weights \(\times P_{01}\) \(\times\) distance (proxy strap)
- local cap \(8\times\) area share
- fill/tap **excluded** (do not switch)
- if `pg_vdd_bumps.sp` exists, DC on mesh (`pdn_transient.py`) with currents scaled to budget

The same mesh feeds **vyges-em-ir** (`run_vyges_em_ir.sh`): static IR CG comparable to `pdn_transient`, dynamic droop simultaneous-switch. See [vyges-em-ir.md](./vyges-em-ir.md).

The **I(t) per pin** path (stagger clock, waveform, heatmap) is `dynamic_ir` — [dynamic-ir.md](./dynamic-ir.md). PDNSim remains static.

PDNSim (`analyze_power_grid -source_type STRAPS`) runs in both modes: IR straps on report.

## How to run

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_rtl_sim.sh   # VCD
FLOW_VARIANT=flowlab ./learn/scripts/run_vectorless.sh
# report: learn/sim/reports/vectorless_flowlab.json
```

Studio / FlowLab: action **`vectorless`**. Orchestrator: **`tool_matrix`**.

## What it is not

This is not RedHawk, VoltSpot commercial, nor PrimeTime PX. It is a static envelope + liberty `report_power` + mesh DC, traceable to the two papers, runnable on this repo's GCD.
