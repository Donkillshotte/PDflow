# SPICE chip mesh · write_pg_spice and cell analysis

OpenROAD exports the on-die power grid as a **resistive network** with current sources for every cell power pin. This document explains the netlist and how it ties to Place/Finish.

## Where the netlist comes from

After **finish**, with ODB and liberty:

```tcl
set_power_activity -global -activity 0.2 -duty 0.5
report_power
set_pdnsim_source_settings -bump_dx 140 -bump_dy 140 \
  -external_resistance 0.05
analyze_power_grid -net VDD -source_type BUMPS
write_pg_spice -net VDD -source_type BUMPS pdn/pg_vdd_bumps.sp
```

Studio script: `learn/scripts/run_chip_pdn_ir.sh`

Typical output (flowlab): **~6700 resistors**, file ~430 KB.

---

## Anatomy of pg_vdd_bumps.sp

```spice
* Netlist for VDD on default

* Resistive network
R0 Node_metal1_2400_5600 ITermNode_metal1_2470_5345 R=1.000000e-03
R42 Node_metal1_2540_5600 Node_metal1_8740_5600 R=6.929448e+00
...

* Current sources (per cell instance pin)
I0 ITermNode_metal1_2470_5345 0 DC 1.234567e-05
...

* Voltage sources (bumps / straps)
V0 Node_bump_0 0 DC 1.100000e+00
```

| Node prefix | Origin |
|---|---|
| `Node_metal*` | Strap/via grid (DBU coordinates) |
| `ITermNode_*` | VDD pin of a placed **cell instance** |
| `Node_bump_*` | Package source (BUMPS pattern) |

**Resistance R:** extracted from real metal shape (width, length, sheet R).

**Current I:** from `report_power` split across pins (activity × capacitance/leakage/switching liberty).

---

## Placement → currents link

1. **Synth** instantiates cells (`DFF_X1`, `NAND2_X1`, …)
2. **Place** fixes coordinates → every ITerm has position `(x,y)` in the node name
3. **Finish** `report_power` → total mA per cell type
4. PDNSim → DC current per ITerm proportional to power

You do not see the cell name in the SPICE node, but `ir_bumps.csv` + DEF map position → instance.

---

## Studio transient engine

`pdn_transient.py`:

1. Parse R, I, V from `.sp`
2. Sparse matrix G·V = I (static)
3. Backward-Euler: C_decap · dV/dt + G·V = I(t) with load-step

GCD validation: static ≈ OpenROAD ±2%.

Report: `pdn_chip_ir_<variant>.json`

Real **vyges-em-ir** engine (same `.sp`): [vyges-em-ir.md](./vyges-em-ir.md). Static IR matches (~0.4%); dynamic droop does not (different waveform).

**I(t) per pin** engine (waveform + heatmap): [dynamic-ir.md](./dynamic-ir.md).

---

## Comparison with System PDN

| | Chip mesh | System ladder |
|---|---|---|
| Files | `pg_vdd_bumps.sp` | `system_pdn/tran.sp` |
| Nodes | ~1000+ | ~12 |
| Package | `external_resistance` + bump pattern | Explicit lumped RLC |
| Board/VRM | Absent | VRM + plane + decap |

The mesh answers: *where* on the die there is droop. The ladder answers: whether the *external supply chain* holds the load-step.

---

## Lab: explore the netlist

```bash
FLOW_VARIANT=flowlab ./learn/scripts/export_spice_lab.sh
```

Creates in `learn/sim/spice/`:

- `pg_vdd_header.sp` — first ~120 annotated lines
- symlink/copy of full mesh (if present)
- `mesh_stats.json` — R/I/V counts

Count resistors:

```bash
rg -c '^R' learn/sim/spice/pg_vdd_bumps.sp
rg -c '^I' learn/sim/spice/pg_vdd_bumps.sp
```

---

## Limits

- **Static resistive** model (no on-die power-grid L in base export)
- DC currents, not per-pin waveforms from VCD
- Synthetic BUMPS on GCD (no real package LEF)

See [spice-power-chain.md](./spice-power-chain.md) for phase order.
