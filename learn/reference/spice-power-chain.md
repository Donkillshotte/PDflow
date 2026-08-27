# Catena power RTL → PKG · collegamento fasi

Questa guida collega **tutte le fasi FlowLab** al flusso di integrità di alimentazione (PI) e alle due famiglie SPICE usate in Studio.

## Panoramica

```
RTL (VCD) ──► Synth (celle .lib) ──► Floorplan (straps)
      │                                    │
      │                                    ▼
      │                              PDN gridcheck
      │                                    │
      ▼                                    ▼
 Place/CTS/Route ──► Finish (report_power, ODB)
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
   activity_power    chip IR mesh    System PDN
   (I_avg)           (write_pg_spice) (ngspice ladder)
```

| Livello | Domanda | Fase FlowLab | Engine |
|---|---|---|---|
| Logica | Toggle corretti? | RTL | Icarus → VCD |
| Celle | Quanto consuma ogni tipo? | Synth → Finish | Liberty + `report_power` |
| Griglia on-die | VDD/VSS connessi? | PDN | `check_power_grid` |
| IR mesh | Droop locale sul chip? | post-finish | PDNSim + `write_pg_spice` |
| System | VRM→board→pkg regge il load-step? | PKG | ngspice |

---

## 1. RTL → attività

**Fase:** RTL · azione `rtl_sim`

- Input: `learn/flowlab/gcd.v`
- Output: `learn/sim/gcd/gcd.vcd`

Il VCD registra toggle sui segnali. In un flusso tapeout reale:

```tcl
read_power_activities -vcd gcd.vcd
report_power
```

Studio usa oggi **attività globale sintetica** (`activity 0.2`, `duty 0.5`) finché il VCD non è collegato automaticamente — ma il VCD da RTL è il **primo anello** della catena: senza toggle reali, `report_power` e `I_die` restano proxy.

**Collegamento:** RTL → (futuro VCD) → `activity_power` → `I_die` in System PDN.

---

## 2. Liberty → celle

**Fase:** Synth

Yosys mappa RTL su celle Nangate45 (`NangateOpenCellLibrary_typical.lib`).

Ogni cella liberty espone (non SPICE transistor-level, ma equivalente per power):

| Sezione | Significato |
|---|---|
| `cell_leakage_power` | Corrente statica |
| `internal_power` / `switching_power` | Energia per transizione (dipende da slew/load) |
| `pin` capacitance | Carico sul net |

OpenROAD `report_power` aggrega per gruppo (Sequential, Combinational, Clock):

```
Total  1.27e-03 W  (flowlab tipico post-finish)
```

**I_avg ≈ P_total / Vdd** → alimenta il load-step System PDN (~2 mA su GCD).

Per SPICE **transistor-level** delle celle servirebbe un modello SPICE foundry (non incluso in nangate45 tutorial). Studio documenta il percorso **liberty → correnti equivalenti** sui nodi mesh.

Vedi anche: [spice-ngspice-primer.md](./spice-ngspice-primer.md) § celle vs mesh.

---

## 3. Floorplan → PDN

**Fase:** Floorplan · tool `pdngen`

Genera:

- Straps VDD/VSS su metal alti (M5/M8 su nangate45)
- `2_4_floorplan_pdn.odb`

**Fase PDN** (`gridcheck`) verifica connettività PSM-0040 — *prima* di placement/route, per intercettare griglia rotta.

Non produce ancora netlist SPICE: la mesh resistiva nasce **dopo** finish con `write_pg_spice`.

---

## 4. Placement → correnti

**Fase:** Place

Le istanze piazzate definiscono **dove** i sink di corrente attaccano la mesh (`ITermNode_*` in `pg_vdd_bumps.sp`).

PDNSim associa ogni cella a pin di alimentazione con corrente da `report_power` / activity.

---

## 5. Finish → report_power

**Fase:** Finish · azione `finish`

Artefatti chiave:

| File | Uso downstream |
|---|---|
| `6_final.odb` | PDNSim, activity, chip IR |
| `6_final.gds` | DRC, visual |
| `report_power` (log) | `I_die` System PDN |

**Signoff post-finish** (FlowLab):

1. `activity_power` — stima corrente media
2. `chip_pdn_ir` — mesh SPICE on-die + transient
3. `system_pdn` — ladder ngspice VRM→die
4. `power_chain` — esegue 1→2→3 + export lab

---

## 6. Chip IR (mesh SPICE)

Script: `learn/scripts/run_chip_pdn_ir.sh`

1. OpenROAD `analyze_power_grid` STRAPS/FULL/BUMPS
2. `write_pg_spice -source_type BUMPS` → `pdn/pg_vdd_bumps.sp`
3. `pdn_transient.py` — solve sparse (static + backward-Euler)

Report: `learn/sim/reports/pdn_chip_ir_<variant>.json`

Approfondimento netlist: [spice-chip-mesh.md](./spice-chip-mesh.md)

---

## 7. System PDN (ngspice)

Script: `learn/scripts/run_system_pdn.sh`

Ladder lumped in `learn/system_pdn/default.json`:

VRM → board plane/decap → package RLC/bumps → C_die + I_DIE pulse

Report: `learn/sim/reports/system_pdn_<variant>.json`

Approfondimento ngspice: [spice-ngspice-primer.md](./spice-ngspice-primer.md)

---

## Lab SPICE locale

```bash
# Export netlist annotate in learn/sim/spice/
FLOW_VARIANT=flowlab ./learn/scripts/export_spice_lab.sh

# Catena completa post-finish
FLOW_VARIANT=flowlab ./learn/scripts/run_power_chain.sh
```

File didattici sempre presenti: `learn/sim/spice/README.md`, `system_pdn_tran_demo.sp`, `nangate_inverter_demo.sp`.

---

## Limiti onesti

- Nessun modello SPICE transistor-level Nangate45 in ORFS GCD
- VCD → `read_power_activities` non ancora automatizzato in FlowLab
- System PDN = ladder educativo, non S-parameter board
- Chip IR `BUMPS` = pattern sintetico OpenROAD (PSM-0073)

## Riferimenti

- [system-pdn.md](./system-pdn.md) — landscape tool
- [pkg-design-package.md](./pkg-design-package.md) — packaging
- [extended-flow.md](./extended-flow.md) — §8 bump/RDL
