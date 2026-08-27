# Catena power RTL → PKG · guida esaustiva

Documento **master** che collega le **8 lezioni del corso (00–07)**, le **9 fasi FlowLab**, gli **artefatti ORFS**, le **azioni Studio** e le **due famiglie SPICE** (mesh on-die + ladder System PDN).

## Matrice completa

| Lezione | FlowLab | ORFS make / output chiave | Azioni Studio | SPICE / report |
|---|---|---|---|---|
| [00-intro](#lezione-00-intro) | `rtl` | `gcd.v`, `gcd.vcd` | `rtl_sim` | — (VCD → activity futura) |
| [01-constraints](#lezione-01-constraints) | `synth` (prep) | `constraint.sdc`, `config.mk` | — | — |
| [02-synthesis](#lezione-02-synthesis) | `synth` | `1_synth.*`, `.lib` | `synth` | `nangate_inverter_demo.sp` |
| [03-floorplan](#lezione-03-floorplan) | `floorplan`, `pdn` | `2_4_floorplan_pdn.odb` | `floorplan`, `gridcheck` | mesh post-finish |
| [04-placement](#lezione-04-placement) | `place` | `3_*place*.odb` | `place` | `ITermNode_*` in mesh |
| [05-cts](#lezione-05-cts) | `cts` | `4_*cts*.odb` | `cts` | ↑ switching clock |
| [06-routing](#lezione-06-routing) | `route` | `5_*route*.odb`, guide | `route` | SPEF → STA |
| [07-finish](#lezione-07-finish) | `finish`, `pkg` | `6_final.*`, IR PNG | signoff chain | tutti i report |
| Post-corso | `pkg` | `system_pdn/`, reports | `system_pdn`, `power_chain` | ngspice JSON |

### Due engine SPICE (non confonderli)

| | Chip mesh | System ladder |
|---|---|---|
| **Domanda** | Dove sul die c'è IR/droop? | VRM→board→pkg regge il load-step? |
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
│                                      │  power_chain → tutto + export    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Lezione 00-intro {#lezione-00-intro}

**Corso:** `learn/lessons/00-intro/` · **FlowLab:** [fase RTL](/flusso?phase=rtl)

| Produce | Consuma |
|---|---|
| `learn/sim/gcd/gcd.vcd` | `learn/flowlab/gcd.v` o `designs/.../gcd.v` |

Il VCD registra **toggle** sui segnali. In tapeout:

```tcl
read_power_activities -vcd gcd.vcd
report_power
```

Studio oggi usa activity globale sintetica finché il VCD non è collegato automaticamente — ma il VCD resta il **primo anello** della catena.

**Prossimo passo catena:** 02 synth (celle) → 07 finish (`report_power`).

---

## Lezione 01-constraints {#lezione-01-constraints}

**Corso:** `learn/lessons/01-constraints/` · **FlowLab:** prep synth ([SDC preset](/flusso?phase=synth))

| Impatto power | Dettaglio |
|---|---|
| `create_clock` period | Frequenza ↑ → switching ↑ |
| I/O delay | Activity periferica |
| `config.mk` | `ABC_AREA`, util indiretti |

Non genera netlist SPICE; prepara il contesto timing in cui `report_power` sarà letto a L07.

---

## Lezione 02-synthesis {#lezione-02-synthesis}

**Corso:** `learn/lessons/02-synthesis/` · **FlowLab:** [synth](/flusso?phase=synth)

| Artefatto | Ruolo nella catena power |
|---|---|
| `NangateOpenCellLibrary_typical.lib` | Modelli power per cella |
| `1_synth.v` / `1_synth.odb` | Netlist gate-level (pre-place) |

### Liberty → correnti (non SPICE transistor-level ORFS)

| Sezione `.lib` | Significato |
|---|---|
| `cell_leakage_power` | Statico |
| `internal_power` / `switching_power` | Per transizione |
| `pin` capacitance | Carico |

OpenROAD aggrega in `report_power`:

```
Sequential / Combinational / Clock → Total W
I_avg ≈ P_total / Vdd  →  load System PDN
```

**Lab SPICE didattico:** [nangate_inverter_demo.sp](../sim/spice/nangate_inverter_demo.sp) — inverter CMOS transistor-level (non foundry Nangate45).

```bash
ngspice -b learn/sim/spice/nangate_inverter_demo.sp
```

---

## Lezione 03-floorplan {#lezione-03-floorplan}

**Corso:** `learn/lessons/03-floorplan/` · **FlowLab:** [floorplan](/flusso?phase=floorplan) + [PDN](/flusso?phase=pdn)

| Step ORFS | Output | Catena power |
|---|---|---|
| 2_1 | die/core/rows | geometria |
| 2_4 | `2_4_floorplan_pdn.odb` | straps VDD/VSS |
| gridcheck | `.gridcheck_pdn.ok` | PSM-0040 connettività |

File strategia: `grid_strategy-M1-M4-M7.tcl` (corso) / nangate45 M5/M8 (FlowLab).

**Nota:** la netlist SPICE resistiva nasce **solo post-finish** con `write_pg_spice`. A L03 verifichi che la griglia esista; a L07 la simuli.

IR heatmap L07 (`orfs_final_ir_drop.png`) è **cieca** se 2_4 PDN manca.

---

## Lezione 04-placement {#lezione-04-placement}

**Corso:** `learn/lessons/04-placement/` · **FlowLab:** [place](/flusso?phase=place)

Ogni cella piazzata ottiene coordinate → pin VDD su nodi `ITermNode_metal*_*` in `pg_vdd_bumps.sp`.

```
R0 Node_metal1_2400_5600 ITermNode_metal1_2470_5345 R=1e-3
I0 ITermNode_metal1_2470_5345 0 DC 1.23e-05
```

PDNSim ripartisce corrente da `report_power` sui pin in base ad activity e tipo cella.

Vedi [spice-chip-mesh.md § anatomia](./spice-chip-mesh.md#anatomia-di-pg_vdd_bumpssp).

---

## Lezione 05-cts {#lezione-05-cts}

**Corso:** `learn/lessons/05-cts/` · **FlowLab:** [cts](/flusso?phase=cts)

| Effetto | Catena power |
|---|---|
| Buffer clock inseriti | ↑ capacità + toggle |
| Skew repair | Nuove celle → nuovi sink |

`report_power` post-CTS mostra spesso gruppo **Clock** significativo (~11% su GCD flowlab).

---

## Lezione 06-routing {#lezione-06-routing}

**Corso:** `learn/lessons/06-routing/` · **FlowLab:** [route](/flusso?phase=route)

| Output | Uso |
|---|---|
| `5_*route*.odb` | Mesh completa pre-finish |
| `route.guide` | Congestion (indiretto su timing → activity) |
| SPEF (a L07) | Parassiti per STA |

IR drop statico usa geometria **post-route/finish**, non il placement alone.

---

## Lezione 07-finish {#lezione-07-finish}

**Corso:** `learn/lessons/07-finish/` · **FlowLab:** [finish](/flusso?phase=finish) + signoff + [PKG](/flusso?phase=pkg)

### Deliverable ORFS

| File | Signoff | Catena SPICE |
|---|---|---|
| `6_final.odb` | timing, power | input PDNSim |
| `6_final.gds` | mask/DRC | — |
| `6_final.spef` | STA post-route | — |
| `orfs_final_ir_drop.png` | IR statico PDNSim | confronta chip IR JSON |

### Signoff FlowLab (ordine consigliato)

1. **`activity_power`** → `activity_power_<variant>.log` → **I_die**
2. **`chip_pdn_ir`** → `pg_vdd_bumps.sp` + `pdn_chip_ir_*.json`
3. **`system_pdn`** → `system_pdn_*.json` (Zmax, droop)
4. **`power_chain`** → esegue 1→2→3 + `export_spice_lab.sh`

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_power_chain.sh
```

### Confronto metriche GCD flowlab (tipico)

| Metrica | Chip mesh | System ladder |
|---|---|---|
| Static IR | ~4.5 mV (PDNSim) | — |
| Transient droop mesh | ~39 mV (peak switch) | — |
| Die droop ladder | — | ~6 mV (load-step) |
| Zmax @ die | — | ~9 Ω @ ~224 MHz |

Numeri **educativi** — ladder lumped, non misura board reale.

---

## Fase FlowLab PKG (post L07) {#fase-pkg}

**Hub:** [/pkg](/pkg) · **Config:** `learn/system_pdn/default.json`

ngspice simula:

```
VRM (R,L,C,ESR) → board plane/bulk/HF → package RLC/bumps → C_die + I_DIE pulse
```

Report: `learn/sim/reports/system_pdn_<variant>.json`

Approfondimento: [spice-ngspice-primer.md](./spice-ngspice-primer.md)

---

## Lab netlist SPICE

| Path | Contenuto |
|---|---|
| [sim/spice/README.md](../sim/spice/README.md) | Indice lab |
| `system_pdn_tran_demo.sp` | Ladder eseguibile |
| `nangate_inverter_demo.sp` | Cella didattica |
| `export_spice_lab.sh` | Copia mesh + stats |

Dopo export (flowlab):

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
- VCD → `read_power_activities` non automatizzato in FlowLab
- System PDN = ladder lumped educativo
- Chip `BUMPS` = pattern sintetico OpenROAD (PSM-0073)
- Lezioni 00–07 **non richiedono** SPICE per completamento — modulo **post-corso** consigliato

---

## Indice documentazione correlata

| Doc | Quando leggerlo |
|---|---|
| [spice-chip-mesh.md](./spice-chip-mesh.md) | Dopo L07, prima di chip_pdn_ir |
| [spice-ngspice-primer.md](./spice-ngspice-primer.md) | Prima di PKG / system_pdn |
| [system-pdn.md](./system-pdn.md) | Landscape tool |
| [pkg-design-package.md](./pkg-design-package.md) | Packaging tapeout |
| [extended-flow.md](./extended-flow.md) | §8 moduli opzionali |
| [golden-metrics.md](./golden-metrics.md) | IR heatmap vs report JSON |
| [glossary.md](./glossary.md) | Termini SPICE/ngspice |

**UI:** FlowLab mostra la catena sotto la pipeline · Lezioni hanno pannello «Catena power» · Signoff post-finish in fase GDSII.
