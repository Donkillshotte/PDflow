# System PDN & packaging analysis — tool landscape

See also the **full phase chain**: [spice-power-chain.md](./spice-power-chain.md).

## Two distinct analyses

| Level | Question | What Studio uses |
|---|---|---|
| **Chip PDN** | Does the on-die grid handle static IR / mesh droop? | OpenROAD **PDNSim** + `write_pg_spice` + `pdn_transient.py` + **vyges-em-ir** + **dynamic_ir** |
| **System PDN** | VRM → board → package → die chain: Z(f) and load-step? | **ngspice** hierarchical ladder → `run_system_pdn.sh` / Studio `/pkg` |

They are not the same thing: package R on PDNSim is still a *chip-centric* model.
System PDN simulates the supply chain outside the die.

## System PDN (`/pkg`)

`run_system_pdn.sh` / `system_pdn` action:

1. Reads `learn/system_pdn/default.json` (VRM, board plane/decap, package RLC/bumps, C_die)
2. Estimates `I_die` from `activity_power` / report, or `I_DIE_AVG=`
3. **ngspice TRAN** — load-step at die → droop on VRM / board / pkg / die
4. **ngspice AC** — |Z(f)| seen at die (Iac=1A)

Report: `learn/sim/reports/system_pdn_<variant>.json`  
Work: `results/.../system_pdn/` (netlist + wrdata)

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_system_pdn.sh
# or
I_DIE_AVG=0.002 FLOW_VARIANT=flowlab ./learn/scripts/run_system_pdn.sh
```

## Chip PDN IR (optional)

```bash
FLOW_VARIANT=flowlab PKG_R=0.05 PKG_L=2e-10 PEAK_FACTOR=8 \
  ./learn/scripts/run_chip_pdn_ir.sh
```

Report: `learn/sim/reports/pdn_chip_ir_<variant>.json`  
(also legacy copy `pdn_transient_<variant>.json`)

GCD flowlab validation: static IR engine ≈ **4.56 mV** vs OpenROAD ≈ **4.47 mV**.

## Relevant open / academic tools

1. **OpenROAD PDNSim** — static IR on-die, `write_pg_spice`
2. **ngspice** — System PDN AC/TRAN on ladder (used in PKG)
3. **vyges-em-ir** — Apache-2.0 engine (binary) on the same mesh: `vyges_em_ir` action. `pdn_transient.py` remains the lab solver with global waveform. Details: [vyges-em-ir.md](./vyges-em-ir.md)
4. **dynamic_ir** — I(t) per ITerm + BE + heatmap: `dynamic_ir` action. [dynamic-ir.md](./dynamic-ir.md)
4. Board SI/PI full-wave — typically commercial tools (ADS, SIwave, …)

## Honest limits

- System PDN = educational *lumped* model (not real S-parameter board)
- Chip PDN transient = worst-case simultaneous switching, not VCD-accurate
- No real LEF bump/RDL on nangate45 GCD
- Does not replace Voltus / RedHawk for tapeout
