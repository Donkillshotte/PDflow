# System PDN & packaging analysis — tool landscape and contract

See also the **full phase chain**: [spice-power-chain.md](./spice-power-chain.md).

## Two distinct analyses

| Level | Question | What Studio uses |
|---|---|---|
| **Chip PDN** | Does the on-die grid handle static IR / mesh droop? | OpenROAD **PDNSim** + `write_pg_spice` + `pdn_transient.py` + **vyges-em-ir** + **dynamic_ir** |
| **System PDN** | VRM → board → package → die chain: Z(f) and load-step? | **ngspice** hierarchical ladder → `run_system_pdn.sh` / Studio `/pkg` |

They are not the same thing: package R on PDNSim is still a *chip-centric* model.
System PDN simulates the supply chain outside the die.

The System PDN implementation is deliberately a compact, hierarchical lab
model. It keeps the FlowLab chain and report shape stable while making the
boundary explicit: the result is measurement evidence for `/pkg`, not a
product signoff claim.

## System PDN (`/pkg`)

`run_system_pdn.sh` / `system_pdn` action:

1. Reads `learn/system_pdn/default.json` (VRM, board plane/decap, package RLC/bumps, C_die)
2. Uses a live current source in this order: explicit `I_DIE_AVG`, activity power divided by VDD, chip-PDN current report, then a documented fallback.
3. **ngspice TRAN** — a die load-step and voltage measurements on VRM / board / package / die
4. **ngspice AC** — complex `Z(f)` and `|Z(f)|` seen at the die with a 1 A AC test current
5. Writes an isolated `runs/<run_id>/` directory, then publishes legacy filenames for FlowLab compatibility.

The passive topology is intentional: every decap is a shunt branch to the ideal
return node, with optional series ESR and ESL before C. The forward chain is
separate R/L for the VRM output, board plane, package path, vias, and parallel
bumps. This prevents a capacitor ESR from being accidentally modeled as a
series drop in the supply path.

Report: `learn/sim/reports/system_pdn_<variant>.json`  
Work: `results/.../system_pdn/` (netlist + wrdata)

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_system_pdn.sh
# or
I_DIE_AVG=0.002 FLOW_VARIANT=flowlab ./learn/scripts/run_system_pdn.sh
```

The report contract is intentionally two-dimensional:

- `evidence_ok: true` means both live ngspice measurements were decoded.
- `status: PASS|WARN|PARTIAL|FAIL` describes requirements and data quality.
- `ok` remains the FlowLab-compatible “measurement artifact is usable” flag;
  `product_signoff` is always `false` for this compact model.
- `target_impedance` records configured and/or derived target impedance. The
  derived target uses `Ztarget = allowed_ripple / |ΔI|`, and the report retains
  the current step, ripple budget, exceedance ratio, and resonance peaks.
- `comparison_scope` is `same-live-invocation`; reports must not be compared to
  an older run with a different design, activity, mesh, or configuration.

For reproducible automation, set `PD_FLOW_RUN_ID` and optionally
`PD_FLOW_RUN_DIR`. The default runner creates a fresh child under
`results/.../system_pdn/runs/` and never reuses an older run directory.

### Package boundary manifest

The package wrapper also emits
`learn/sim/reports/pkg_manifest_<variant>.json`. This is the canonical,
machine-readable bridge between the FlowLab finish and `/pkg`:

- `interface` records the die envelope and finish pins;
- `bump_array` records the configured array, the six mapped breakouts, and
  observed sidecar components;
- `rdl` records only the configured RDL layers and checks coverage for every
  required net (`VDD`, `VSS`, `clk`, `reset`, `req_val`, `resp_val`);
- `electrical_model` records the compact R/L/C assumptions and estimated
  series resonance; it also distinguishes the sparse mapped breakout from
  the number of parallel supply bumps assumed by the lumped model;
- `provenance` records artifact hashes and an input fingerprint.

The manifest status is `PROXY` only when the current finish, configured map,
all RDL nets, and live System PDN are present. `product_signoff` remains
`false`: the bump/RDL sidecar is an educational OpenROAD model, not a foundry
package stack.

```bash
python3 learn/scripts/pkg_manifest.py --variant flowlab
LAB_ASAP7_VARIANT=lab_asap7_gcd_tc_rvt_nldm_7p5_320ps \
  bash learn/scripts/run_lab_asap7_pkg.sh
```

The leftover-named ASAP7 package lab (`learn/scripts/lab_asap7_pkg.py`) calls
the same engine with its legacy 0.70 V config. Its outer report remains scoped
to an independent ASAP7 package invocation and is never mixed with the
Nangate/FlowLab result.

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

- System PDN = educational *lumped* model (not a real S-parameter board, plane extraction, or VRM control-loop model)
- Package/board parasitics are configuration inputs; package geometry, mounting inductance distributions, and return-path modes are not extracted
- AC resonance peaks are useful diagnostic evidence, not a claim of compliance by themselves
- Chip PDN transient = worst-case simultaneous switching, not VCD-accurate
- No real LEF bump/RDL on nangate45 GCD
- Does not replace Voltus / RedHawk for tapeout

## References used for the implementation

- [ngspice manual](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf): AC/TRAN source syntax, complex AC vectors, `wrdata`, and integration methods.
- [AMD Target Impedance](https://docs.amd.com/r/en-US/ug863-versal-pcb-design/Target-Impedance): ripple/current-step budgeting and the target-impedance criterion.
- [System-level PDN decoupling research](https://link.springer.com/article/10.1007/s42452-025-07224-6): VRM → board → package → die hierarchy, ESR/ESL, resonance, and anti-resonance behavior.
- [OpenROAD PDNSim documentation](https://openroad.readthedocs.io/en/latest/_downloads/86b37e131fb3a938455f51249d86af88/PDNSim-documentation.pdf): the chip-grid analysis boundary that must remain distinct from this system-level ladder.
- [OpenROAD pad/RDL commands](https://github.com/The-OpenROAD-Project/OpenROAD/blob/master/src/pad/README.md): bump arrays, assignments, and `rdl_route`.
