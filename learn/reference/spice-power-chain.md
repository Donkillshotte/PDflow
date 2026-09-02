# Catena power RTL → PKG · guide esaustiva

**Master** document linking the **8 course lessons (00–07)**, the **9 FlowLab phases**, **ORFS artifacts**, **Studio actions**, and the **two SPICE families** (mesh on-die + ladder System PDN).

## Matrice completa

| Lesson | FlowLab | ORFS make / output chiave | Azioni Studio | SPICE / report |
|---|---|---|---|---|
| [00-intro](#lesson-00-intro) | `rtl` | `gcd.v`, `gcd.vcd` | `rtl_sim` | — (VCD → activity futura) |
| [01-constraints](#lesson-01-constraints) | `synth` (prep) | `constraint.sdc`, `config.mk` | — | — |
| [02-synthesis](#lesson-02-synthesis) | `synth` | `1_synth.*`, `.lib` | `synth` | `nangate_inverter_demo.sp` |
| [03-floorplan](#lesson-03-floorplan) | `floorplan`, `pdn` | `2_4_floorplan_pdn.odb` | `floorplan`, `gridcheck` | mesh post-finish |
| [04-placement](#lesson-04-placement) | `place` | `3_*place*.odb` | `place` | `ITermNode_*` in mesh |
| [05-cts](#lesson-05-cts) | `cts` | `4_*cts*.odb` | `cts` | ↑ switching clock |
| [06-routing](#lesson-06-routing) | `route` | `5_*route*.odb`, guide | `route` | SPEF → STA |
| [07-finish](#lesson-07-finish) | `finish`, `pkg` | `6_final.*`, IR PNG | signoff chain | all i report |
| Post-course | `pkg` | `system_pdn/`, reports | `system_pdn`, `power_chain` | ngspice JSON |

### Two SPICE engines (do not confuse them)

| | Chip mesh | System ladder |
|---|---|---|
| **Question** | Where on the die is there IR/droop? | VRM→board→pkg handles the load-step? |
| **Netlist** | `write_pg_spice` (~5k R) | `system_pdn_hier.py` (~15 elementi) |
| **Sim** | PDNSim + `pdn_transient.py` | ngspice TRAN + AC |
| **Quando** | Post-finish | Post-finish (I_die da activity) |
| **Doc** | [spice-chip-mesh.md](./spice-chip-mesh.md) | [spice-ngspice-primer.md](./spice-ngspice-primer.md) |

---

## Diagramma end-to-end

```
┌─────────────────────────────────────────────────────────────────────────┐
│ CORso 00–07 (FLOW_VARIANT=learn)     │  FlowLab (FLOW_VARIANT=flowlab) │
├─────────────────────────────────────────────────────────────────────────┤
│ 00 RTL sim → VCD                     │  rtl_sim → gcd.vcd               │
│ 02 Synth → netlist + .lib            │  synth → 1_synth.odb             │
│ 03 Floorplan → 2_4 PDN ODB           │  floorplan → 2_4_floorplan_pdn   │
│      └─ gridcheck (FlowLab PDN)      │  gridcheck → .gridcheck_pdn.ok   │
│ 04 Place → coordinate celle          │  place → 3_place.odb             │
│ 05 CTS → buffer clock                │  cts → 4_cts.odb                 │
│ 06 Route → guide + DRC               │  route → 5_route.odb             │
│ 07 Finish → GDS/SPEF/IR heatmap      │  finish → 6_final.*              │
│      └─ (post) signoff SPICE         │  activity_power → I_avg          │
│                                      │  chip_pdn_ir → pg_vdd_bumps.sp   │
│                                      │  system_pdn → ngspice JSON       │
│                                      │  power_chain → all + export    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Lesson 00-intro {#lesson-00-intro}

**Course:** `learn/lessons/00-intro/` · **FlowLab:** [fase RTL](/flusso?phase=rtl)

| Produce | Consuma |
|---|---|
| `learn/sim/gcd/gcd.vcd` | `learn/flowlab/gcd.v` o `designs/.../gcd.v` |

VCD records **toggle** on signals. In tapeout:

```tcl
read_vcd -scope tb_gcd/dut gcd.vcd
report_power
```

Studio use **`read_vcd`** (non `read_power_activities`) when `run_rtl_sim.sh` produced `gcd.vcd` — see `learn/lib/power_vcd.sh`. For IR without vectors: azione `vectorless` ([vectorless-power.md](./vectorless-power.md)).

**Prossimo passo catena:** 02 synth (celle) → 07 finish (`report_power`).

---

## Lesson 01-constraints {#lesson-01-constraints}

**Course:** `learn/lessons/01-constraints/` · **FlowLab:** prep synth ([SDC preset](/flusso?phase=synth))

| Impatto power | Dettaglio |
|---|---|
| `create_clock` period | Frequenza ↑ → switching ↑ |
| I/O delay | Activity periferica |
| `config.mk` | `ABC_AREA`, util indiretti |

Does not generate SPICE netlist; prepares timing context where `report_power` will be read at L07.

---

## Lesson 02-synthesis {#lesson-02-synthesis}

**Course:** `learn/lessons/02-synthesis/` · **FlowLab:** [synth](/flusso?phase=synth)

| Artifact | Role in power chain |
|---|---|
| `NangateOpenCellLibrary_typical.lib` | Per-cell power models |
| `1_synth.v` / `1_synth.odb` | Netlist gate-level (pre-place) |

### Liberty → currents (not ORFS transistor-level SPICE)

| Sezione `.lib` | Meaning |
|---|---|
| `cell_leakage_power` | Statico |
| `internal_power` / `switching_power` | Per transizione |
| `pin` capacitance | Carico |

OpenROAD aggrega in `report_power`:

```
Sequential / Combinational / Clock → Total W
I_avg ≈ P_total / Vdd  →  load System PDN
```

**Lab SPICE educational:** [nangate_inverter_demo.sp](../sim/spice/nangate_inverter_demo.sp) — inverter CMOS transistor-level (not foundry Nangate45).

```bash
ngspice -b learn/sim/spice/nangate_inverter_demo.sp
```

---

## Lesson 03-floorplan {#lesson-03-floorplan}

**Course:** `learn/lessons/03-floorplan/` · **FlowLab:** [floorplan](/flusso?phase=floorplan) + [PDN](/flusso?phase=pdn)

| Step ORFS | Output | Catena power |
|---|---|---|
| 2_1 | die/core/rows | geometria |
| 2_4 | `2_4_floorplan_pdn.odb` | straps VDD/VSS |
| gridcheck | `.gridcheck_pdn.ok` | PSM-0040 connectivity |

Files strategia: `grid_strategy-M1-M4-M7.tcl` (course) / nangate45 M5/M8 (FlowLab).

**Note:** resistive SPICE netlist is born **only post-finish** con `write_pg_spice`. At L03 verify the grid exists; at L07 simulate it.

IR heatmap L07 (`orfs_final_ir_drop.png`) is **cieca** se 2_4 PDN manca.

---

## Lesson 04-placement {#lesson-04-placement}

**Course:** `learn/lessons/04-placement/` · **FlowLab:** [place](/flusso?phase=place)

Every cella piazzata otkeeps coordinate → pin VDD su nodi `ITermNode_metal*_*` in `pg_vdd_bumps.sp`.

```
R0 Node_metal1_2400_5600 ITermNode_metal1_2470_5345 R=1e-3
I0 ITermNode_metal1_2470_5345 0 DC 1.23e-05
```

PDNSim distributes current from `report_power` on pins based on activity and cell type.

See [spice-chip-mesh.md § anatomia](./spice-chip-mesh.md#anatomia-di-pg_vdd_bumpssp).

---

## Lesson 05-cts {#lesson-05-cts}

**Course:** `learn/lessons/05-cts/` · **FlowLab:** [cts](/flusso?phase=cts)

| Effetto | Catena power |
|---|---|
| Buffer clock inserted | ↑ capacitance + toggle |
| Skew repair | Nuove celle → nuovi sink |

`report_power` post-CTS often shows significant **Clock** group (~11% su GCD flowlab).

---

## Lesson 06-routing {#lesson-06-routing}

**Course:** `learn/lessons/06-routing/` · **FlowLab:** [route](/flusso?phase=route)

| Output | Uso |
|---|---|
| `5_*route*.odb` | Mesh completa pre-finish |
| `route.guide` | Congestion (indiretto su timing → activity) |
| SPEF (a L07) | Parasitics for STA |

IR drop statico use geometria **post-route/finish**, not placement alone.

---

## Lesson 07-finish {#lesson-07-finish}

**Course:** `learn/lessons/07-finish/` · **FlowLab:** [finish](/flusso?phase=finish) + signoff + [PKG](/flusso?phase=pkg)

### Deliverable ORFS

| Files | Signoff | Catena SPICE |
|---|---|---|
| `6_final.odb` | timing, power | input PDNSim |
| `6_final.gds` | mask/DRC | — |
| `6_final.spef` | STA post-route | — |
| `orfs_final_ir_drop.png` | IR statico PDNSim | confronta chip IR JSON |

### Signoff FlowLab (ordine recommended)

1. **`activity_power`** → `activity_power_<variant>.log` → **I_die**
2. **`chip_pdn_ir`** → `pg_vdd_bumps.sp` + `pdn_chip_ir_*.json`
3. **`vyges_em_ir`** → same mesh, binary CG + backward Euler (`vyges_em_ir_*.json`)
4. **`dynamic_ir`** → I(t) per pin + heatmap (`dynamic_ir_*.json` + `.svg`)
5. **`system_pdn`** → `system_pdn_*.json` (Zmax, droop)
6. **`power_chain`** → esegue activity → chip IR → system → export lab

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_power_chain.sh
```

### Confronto metrics GCD flowlab (tipico)

| Metric | Chip mesh | System ladder |
|---|---|---|
| Static IR | ~4.5 mV (PDNSim) | — |
| Transient droop mesh | ~39 mV (peak switch) | — |
| Die droop ladder | — | ~6 mV (load-step) |
| Zmax @ die | — | ~9 Ω @ ~224 MHz |

**Educational** numbers — lumped ladder, not real board measurement.

---

## Fase FlowLab PKG (post L07) {#fase-pkg}

**Hub:** [/pkg](/pkg) · **Config:** `learn/system_pdn/default.json`

ngspice simula:

```
VRM (R,L,C,ESR) → board plane/bulk/HF → package RLC/bumps → C_die + I_DIE pulse
```

Report: `learn/sim/reports/system_pdn_<variant>.json`

Deep dive: [spice-ngspice-primer.md](./spice-ngspice-primer.md)

---

## Lab netlist SPICE

| Path | Content |
|---|---|
| [sim/spice/README.md](../sim/spice/README.md) | Indice lab |
| `system_pdn_tran_demo.sp` | Ladder eseguibile |
| `nangate_inverter_demo.sp` | Cella educational |
| `export_spice_lab.sh` | Copia mesh + stats |

After export (flowlab):

```json
// mesh_stats_flowlab.json
{ "resistors": 5478, "current_sources": 608, "voltage_sources": ... }
```

---

## Comandi rapidi

```bash
# Singoli step
FLOW_VARIANT=flowlab ./learn/scripts/run_activity_power.sh
FLOW_VARIANT=flowlab ./learn/scripts/run_chip_pdn_ir.sh
FLOW_VARIANT=flowlab ./learn/scripts/run_system_pdn.sh
FLOW_VARIANT=flowlab ./learn/scripts/export_spice_lab.sh

# Catena completa
FLOW_VARIANT=flowlab ./learn/scripts/run_power_chain.sh

# Demo ngspice
ngspice -b learn/sim/spice/system_pdn_tran_demo.sp
```

---

## Limiti onesti

- Nessun SPICE transistor-level Nangate45 in ORFS GCD
- VCD → `read_vcd` via `power_vcd.sh` in `run_activity_power.sh` (FlowLab `rtl_sim` → activity)
- Vectorless IR → `run_vectorless.sh` (Najm + Kouroussis)
- System PDN = ladder lumped educativo
- Chip `BUMPS` = pattern sintetico OpenROAD (PSM-0073)
- Lessons 00–07 **do not require** SPICE for completion — **post-course** module recommended

---

## Indice documentazione correlata

| Doc | Quando leggerlo |
|---|---|
| [spice-chip-mesh.md](./spice-chip-mesh.md) | After L07, before di chip_pdn_ir |
| [spice-ngspice-primer.md](./spice-ngspice-primer.md) | Before di PKG / system_pdn |
| [system-pdn.md](./system-pdn.md) | Landscape tool |
| [pkg-design-package.md](./pkg-design-package.md) | Packaging tapeout |
| [extended-flow.md](./extended-flow.md) | §8 modules opzionali |
| [golden-metrics.md](./golden-metrics.md) | IR heatmap vs report JSON |
| [glossary.md](./glossary.md) | Termini SPICE/ngspice |

**UI:** FlowLab shows the chain below the pipeline · Lessons have «Power chain» panel · Post-finish signoff in GDSII phase.
