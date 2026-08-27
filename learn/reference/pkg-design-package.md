# PKG · Design package (bump, RDL, C4)

Modulo **Packaging / design package** per il Physical Design Studio.

## Perché una sezione dedicata

Il flusso GCD nangate45 termina in **GDSII di blocco digitale flat**.
Tapeout reale richiede anche:

1. **Bump / pad array** — C4, μbump, copper pillar
2. **RDL** — redistribuzione I/O verso i bump
3. **Package PDN** — planes, vias, decoupling dal die al board
4. **Signoff package** — SI, PI, thermal, warpage (tool esterni)

OpenROAD espone API (`assign_io_bump`, `make_io_bump_array`, `rdl_route`,
`analyze_power_grid -source_type BUMPS`) ma **ORFS GCD non ha LEF/tech di
package**. Questa sezione documenta i concetti e collega la demo System PDN.

## Stack tipico (die → board)

```
┌─────────────────────────────┐
│  Board PDN / VRMs           │  ← system PDN (SI/PI tools)
├─────────────────────────────┤
│  Package planes + balls     │  ← BGA / LGA
├─────────────────────────────┤
│  Bumps (C4 / μbump)         │  ← analyze_power_grid -source_type BUMPS
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
| IR STRAPS / FULL / BUMPS | FlowLab fase **PKG** · azione `system_pdn` |
| Heatmap IR finish | Galleria `orfs_final_ir_drop.png` · L07 |
| Teoria bump/RDL | questo documento + [extended-flow.md](./extended-flow.md) §8 |

## Design package (consegna)

Un **design package** tipico per review include:

- Netlist + SDC + liberty corner
- DEF/ODB floorplan e PDN strategy
- Report WNS/TNS, DRC, LVS, antenna
- IR drop / EM summary (chip + package se disponibile)
- GDS/OAS + manifest layer
- BOM package / bump map (se tapeout)

Template corso: [progetto-finale-template.md](../workbook/progetto-finale-template.md).

## Limiti onesti su Nangate45 GCD

- Nessun LEF bump/RDL nella platform tutorial
- `source_type BUMPS` usa un **pattern sintetico** OpenROAD (PSM-0073)
- Thermal / board SI non installati in VM

Per un lab packaging reale serve un design ORFS con bump LEF oppure un
flusso vendor — fuori scope del percorso 00–07 obbligatorio.
