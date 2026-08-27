# PKG · Design package (bump, RDL, C4)

Modulo **Packaging / design package** per il Physical Design Studio.

## Perché una sezione dedicata

Il flusso GCD nangate45 termina in **GDSII di blocco digitale flat**.
Tapeout reale richiede anche:

1. **Bump / pad array** — C4, μbump, copper pillar
2. **RDL** — redistribuzione I/O verso i bump
3. **Package / System PDN** — VRM → board → package → die
4. **Signoff package** — SI, PI, thermal, warpage (tool esterni)

OpenROAD espone API (`assign_io_bump`, `make_io_bump_array`, `rdl_route`,
`analyze_power_grid -source_type BUMPS`) ma **ORFS GCD non ha LEF/tech di
package**. Questa sezione documenta i concetti e collega le due demo PDN.

## Stack tipico (die → board)

```
┌─────────────────────────────┐
│  Board PDN / VRMs           │  ← System PDN (ngspice ladder · fase PKG)
├─────────────────────────────┤
│  Package planes + balls     │  ← BGA / LGA (lumped in System PDN)
├─────────────────────────────┤
│  Bumps (C4 / μbump)         │  ← chip IR opzionale: source_type BUMPS
├─────────────────────────────┤
│  RDL / AP layers            │  ← rdl_route (API only qui)
├─────────────────────────────┤
│  Chip PDN (M1…Mx) + stdcell │  ← ORFS pdngen + gridcheck  ← READY
└─────────────────────────────┘
```

## Cosa puoi fare ora in Studio

| Azione | Dove |
|---|---|
| Chip PDN + `check_power_grid` | FlowLab fase **PDN** |
| **System PDN** VRM→board→pkg→die · Z(f) + load-step | FlowLab fase **PKG** · `run_system_pdn.sh` · ngspice |
| Chip IR static+transient (opzionale) | `run_chip_pdn_ir.sh` · PDNSim + `pdn_transient.py` |
| Heatmap IR finish | Galleria `orfs_final_ir_drop.png` · L07 |
| Teoria + landscape tool | [system-pdn.md](./system-pdn.md) · [spice-power-chain.md](./spice-power-chain.md) |

## Design package (consegna)

Un **design package** tipico per review include:

- Netlist + SDC + liberty corner
- DEF/ODB floorplan e PDN strategy
- Report WNS/TNS, DRC, LVS, antenna
- IR drop / EM summary (chip + system PDN se disponibile)
- GDS/OAS + manifest layer
- BOM package / bump map (se tapeout)

Template corso: [progetto-finale-template.md](../workbook/progetto-finale-template.md).

## Limiti onesti su Nangate45 GCD

- Nessun LEF bump/RDL nella platform tutorial
- System PDN = ladder *lumped* educativo (non board S-parameter)
- `source_type BUMPS` (chip IR) usa un **pattern sintetico** OpenROAD (PSM-0073)
- Thermal / full-wave board SI non installati in VM

Per un lab packaging reale serve un design ORFS con bump LEF oppure un
flusso vendor — fuori scope del percorso 00–07 obbligatorio.
