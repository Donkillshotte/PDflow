# PKG · Design package (bump, RDL, C4)

**Packaging / design package** module for the Physical Design Studio.

## Why a dedicated section

The GCD nangate45 flow ends in **flat digital block GDSII**.
Real tapeout also requires:

1. **Bump / pad array** — C4, μbump, copper pillar
2. **RDL** — I/O redistribution toward bumps
3. **Package / System PDN** — VRM → board → package → die
4. **Package signoff** — SI, PI, thermal, warpage (external tools)

OpenROAD exposes APIs (`assign_io_bump`, `make_io_bump_array`, `rdl_route`,
`analyze_power_grid -source_type BUMPS`) but **ORFS GCD does not include package
LEF/tech**. This section documents the concepts and links the two PDN demos.

## Typical stack (die → board)

```
┌─────────────────────────────┐
│  Board PDN / VRMs           │  ← System PDN (ngspice ladder · PKG phase)
├─────────────────────────────┤
│  Package planes + balls     │  ← BGA / LGA (lumped in System PDN)
├─────────────────────────────┤
│  Bumps (C4 / μbump)         │  ← chip IR optional: source_type BUMPS
├─────────────────────────────┤
│  RDL / AP layers            │  ← rdl_route (API only here)
├─────────────────────────────┤
│  Chip PDN (M1…Mx) + stdcell │  ← ORFS pdngen + gridcheck  ← READY
└─────────────────────────────┘
```

## What you can do now in Studio

| Action | Where |
|---|---|
| Chip PDN + `check_power_grid` | FlowLab **PDN** phase |
| **System PDN** VRM→board→pkg→die · Z(f) + load-step | FlowLab **PKG** phase · `run_system_pdn.sh` · ngspice |
| Chip IR static+transient (optional) | `run_chip_pdn_ir.sh` · PDNSim + `pdn_transient.py` |
| vyges-em-ir | `run_vyges_em_ir.sh` · engine Apache-2.0 on the same mesh |
| Dynamic IR I(t) | `run_dynamic_ir.sh` · heatmap t_worst |
| IR heatmap at finish | Gallery `orfs_final_ir_drop.png` · L07 |
| Theory + tool landscape | [system-pdn.md](./system-pdn.md) · [spice-power-chain.md](./spice-power-chain.md) |

## Design package (deliverable)

A typical **design package** for review includes:

- Netlist + SDC + liberty corner
- DEF/ODB floorplan and PDN strategy
- WNS/TNS, DRC, LVS, antenna reports
- IR drop / EM summary (chip + system PDN if available)
- GDS/OAS + layer manifest
- Package BOM / bump map (if tapeout)

Course template: [progetto-finale-template.md](../workbook/progetto-finale-template.md).

## Honest limits on Nangate45 GCD

- No bump/RDL LEF in the tutorial platform
- System PDN = educational *lumped* ladder (not board S-parameter)
- `source_type BUMPS` (chip IR) uses a synthetic OpenROAD **pattern** (PSM-0073)
- Thermal / full-wave board SI not installed in VM

For a real packaging lab you need an ORFS design with bump LEF or a
vendor flow — outside the scope of required courses 00–07.
