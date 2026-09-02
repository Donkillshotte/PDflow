# SPICE lab · teaching netlists

Folder with SPICE netlists to understand **on-die mesh** and **System PDN** with ngspice.

## Files always present

| File | Content |
|---|---|
| `system_pdn_tran_demo.sp` | VRM→die ladder · load-step · ~35 lines |
| `nangate_inverter_demo.sp` | Transistor-level CMOS inverter (teaching) |
| `system_pdn_config.json` | Ladder config copy |

## Generated files (post-run)

After `finish` + analysis:

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_power_chain.sh
# or export only:
FLOW_VARIANT=flowlab ./learn/scripts/export_spice_lab.sh
```

| File | Origin |
|---|---|
| `system_pdn_tran_flowlab.sp` | ngspice TRAN ladder |
| `system_pdn_ac_flowlab.sp` | ngspice AC Z(f) |
| `pg_vdd_bumps_flowlab.sp` | OpenROAD write_pg_spice |
| `pg_vdd_header_flowlab.sp` | First 120 mesh lines |
| `mesh_stats_flowlab.json` | R/I/V count |
| `INDEX_flowlab.md` | Export index |

## How to explore

```bash
# System PDN demo
ngspice -b -o /tmp/tran.log learn/sim/spice/system_pdn_tran_demo.sp

# Inverter (current from VDD)
ngspice -b learn/sim/spice/nangate_inverter_demo.sp

# Chip mesh statistics
cat learn/sim/spice/mesh_stats_flowlab.json
head -40 learn/sim/spice/pg_vdd_header_flowlab.sp
```

## Documentation

- [spice-power-chain.md](../reference/spice-power-chain.md) — RTL→PKG phase linkage
- [spice-ngspice-primer.md](../reference/spice-ngspice-primer.md) — ngspice System PDN
- [spice-chip-mesh.md](../reference/spice-chip-mesh.md) — write_pg_spice and cells

## Two SPICE worlds in Studio

1. **Chip mesh** — thousands of R, I currents per cell pin (PDNSim export)
2. **System ladder** — ~15 lumped elements (ngspice PKG)

Do not confuse them: the mesh answers *where* on the die; the ladder answers *VRM→board→package*.
