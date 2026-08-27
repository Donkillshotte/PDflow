# SPICE lab · netlist didattiche

Cartella con netlist SPICE per capire **mesh on-die** e **System PDN** ngspice.

## File sempre presenti

| File | Contenuto |
|---|---|
| `system_pdn_tran_demo.sp` | Ladder VRM→die · load-step · ~35 righe |
| `nangate_inverter_demo.sp` | Inverter CMOS transistor-level (didattico) |
| `system_pdn_config.json` | Copia config ladder |

## File generati (post-run)

Dopo `finish` + analisi:

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_power_chain.sh
# oppure solo export:
FLOW_VARIANT=flowlab ./learn/scripts/export_spice_lab.sh
```

| File | Origine |
|---|---|
| `system_pdn_tran_flowlab.sp` | ngspice TRAN ladder |
| `system_pdn_ac_flowlab.sp` | ngspice AC Z(f) |
| `pg_vdd_bumps_flowlab.sp` | OpenROAD write_pg_spice |
| `pg_vdd_header_flowlab.sp` | Prime 120 righe mesh |
| `mesh_stats_flowlab.json` | Conteggio R/I/V |
| `INDEX_flowlab.md` | Indice export |

## Come esplorare

```bash
# System PDN demo
ngspice -b -o /tmp/tran.log learn/sim/spice/system_pdn_tran_demo.sp

# Inverter (corrente da VDD)
ngspice -b learn/sim/spice/nangate_inverter_demo.sp

# Statistiche mesh chip
cat learn/sim/spice/mesh_stats_flowlab.json
head -40 learn/sim/spice/pg_vdd_header_flowlab.sp
```

## Documentazione

- [spice-power-chain.md](../reference/spice-power-chain.md) — collegamento fasi RTL→PKG
- [spice-ngspice-primer.md](../reference/spice-ngspice-primer.md) — ngspice System PDN
- [spice-chip-mesh.md](../reference/spice-chip-mesh.md) — write_pg_spice e celle

## Due mondi SPICE in Studio

1. **Chip mesh** — migliaia di R, correnti I per pin cella (PDNSim export)
2. **System ladder** — ~15 elementi lumped (ngspice PKG)

Non confonderli: il mesh risponde *dove* sul die; il ladder *VRM→board→package*.
