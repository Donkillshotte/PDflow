# RTL → PKG power chain · comprehensive guide

**Master** document linking the **8 course lessons (00–07)**, the **9 FlowLab phases**, **ORFS artifacts**, **Studio actions**, and the **two SPICE families** (on-die mesh + System PDN ladder).

## Complete matrix

| Lesson | FlowLab | Key ORFS make / output | Studio actions | SPICE / report |
|---|---|---|---|---|
| [00-intro](#lesson-00-intro) | `rtl` | `gcd.v`, `gcd.vcd`, `gcd_gate.vcd` | `rtl_sim`, `gate_sim` | gate VCD name-join → activity |
| [01-constraints](#lesson-01-constraints) | `synth` (prep) | `constraint.sdc`, `config.mk` | — | — |
| [02-synthesis](#lesson-02-synthesis) | `synth` | `1_synth.*`, `.lib` | `synth` | `nangate_inverter_demo.sp` |
| [03-floorplan](#lesson-03-floorplan) | `floorplan`, `pdn` | `2_4_floorplan_pdn.odb` | `floorplan`, `gridcheck` | mesh post-finish |
| [04-placement](#lesson-04-placement) | `place` | `3_*place*.odb` | `place` | `ITermNode_*` in mesh |
| [05-cts](#lesson-05-cts) | `cts` | `4_*cts*.odb` | `cts` | ↑ switching clock |
| [06-routing](#lesson-06-routing) | `route` | `5_*route*.odb`, guide | `route` | SPEF → STA |
| [07-finish](#lesson-07-finish) | `finish`, `pkg` | `6_final.*`, IR PNG | signoff chain | all reports |
| Post-course | `pkg` | `system_pdn/`, reports | `system_pdn`, `power_chain` | ngspice JSON |

### Two SPICE engines (do not confuse them)

| | Chip mesh | System ladder |
|---|---|---|
| **Question** | Where on the die is there IR/droop? | Does VRM→board→pkg handle the load-step? |
| **Netlist** | `write_pg_spice` (~5k R) | `system_pdn_hier.py` (~15 elements) |
| **Sim** | PDNSim + `pdn_transient.py` | ngspice TRAN + AC |
| **When** | Post-finish | Post-finish (I_die from activity) |
| **Doc** | [spice-chip-mesh.md](./spice-chip-mesh.md) | [spice-ngspice-primer.md](./spice-ngspice-primer.md) |

---

## End-to-end diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Course 00–07 (FLOW_VARIANT=learn)     │  FlowLab (FLOW_VARIANT=flowlab) │
├─────────────────────────────────────────────────────────────────────────┤
│ 00 RTL sim → VCD                     │  rtl_sim → gcd.vcd               │
│      gate sim → name-join VCD        │  gate_sim → gcd_gate.vcd         │
│ 02 Synth → netlist + .lib            │  synth → 1_synth.odb             │
│ 03 Floorplan → 2_4 PDN ODB           │  floorplan → 2_4_floorplan_pdn   │
│      └─ gridcheck (FlowLab PDN)      │  gridcheck → .gridcheck_pdn.ok   │
│ 04 Place → cell coordinates          │  place → 3_place.odb             │
│ 05 CTS → clock buffers               │  cts → 4_cts.odb                 │
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

**Course:** `learn/lessons/00-intro/` · **FlowLab:** [RTL phase](/flow?phase=rtl)

| Produces | Consumes |
|---|---|
| `learn/sim/gcd/gcd.vcd` | `learn/flowlab/gcd.v` or `designs/.../gcd.v` |

VCD records **toggle** on signals. In tapeout:

```tcl
read_vcd -scope tb_gcd/dut gcd.vcd
report_power
```

Studio uses **`read_vcd`** (not `read_power_activities`). `power_vcd.sh` prefers `gcd_gate.vcd` from `gate_sim` (`-scope tb_gcd_gate/dut`) and falls back to RTL `gcd.vcd` for lesson 00. For IR without vectors: `vectorless` action ([vectorless-power.md](./vectorless-power.md)).

**Next chain step:** 02 synth (cells) → 07 finish (`report_power`).

---

## Lesson 01-constraints {#lesson-01-constraints}

**Course:** `learn/lessons/01-constraints/` · **FlowLab:** synth prep ([SDC preset](/flow?phase=synth))

| Power impact | Detail |
|---|---|
| `create_clock` period | Higher frequency ↑ → switching ↑ |
| I/O delay | Peripheral activity |
| `config.mk` | `ABC_AREA`, indirect util |

Does not generate SPICE netlist; prepares timing context where `report_power` will be read at L07.

---

## Lesson 02-synthesis {#lesson-02-synthesis}

**Course:** `learn/lessons/02-synthesis/` · **FlowLab:** [synth](/flow?phase=synth)

| Artifact | Role in power chain |
|---|---|
| `NangateOpenCellLibrary_typical.lib` | Per-cell power models |
| `1_synth.v` / `1_synth.odb` | Gate-level netlist (pre-place) |

### Liberty → currents (not ORFS transistor-level SPICE)

| `.lib` section | Meaning |
|---|---|
| `cell_leakage_power` | Static |
| `internal_power` / `switching_power` | Per transition |
| `pin` capacitance | Load |

OpenROAD aggregates in `report_power`:

```
Sequential / Combinational / Clock → Total W
I_avg ≈ P_total / Vdd  →  load System PDN
```

**Educational SPICE lab:** [nangate_inverter_demo.sp](../sim/spice/nangate_inverter_demo.sp) — transistor-level CMOS inverter (not foundry Nangate45).

```bash
ngspice -b learn/sim/spice/nangate_inverter_demo.sp
```

---

## Lesson 03-floorplan {#lesson-03-floorplan}

**Course:** `learn/lessons/03-floorplan/` · **FlowLab:** [floorplan](/flow?phase=floorplan) + [PDN](/flow?phase=pdn)

| ORFS step | Output | Power chain |
|---|---|---|
| 2_1 | die/core/rows | geometry |
| 2_4 | `2_4_floorplan_pdn.odb` | VDD/VSS straps |
| gridcheck | `.gridcheck_pdn.ok` | PSM-0040 connectivity |

Strategy files: `grid_strategy-M1-M4-M7.tcl` (course) / nangate45 M5/M8 (FlowLab).

**Note:** resistive SPICE netlist is born **only post-finish** with `write_pg_spice`. At L03 verify the grid exists; at L07 simulate it.

L07 IR heatmap (`orfs_final_ir_drop.png`) is **blind** if 2_4 PDN is missing.

---

## Lesson 04-placement {#lesson-04-placement}

**Course:** `learn/lessons/04-placement/` · **FlowLab:** [place](/flow?phase=place)

Every placed cell gets coordinates → VDD pins on `ITermNode_metal*_*` nodes in `pg_vdd_bumps.sp`.

```
R0 Node_metal1_2400_5600 ITermNode_metal1_2470_5345 R=1e-3
I0 ITermNode_metal1_2470_5345 0 DC 1.23e-05
```

PDNSim distributes current from `report_power` on pins based on activity and cell type.

See [spice-chip-mesh.md § anatomy](./spice-chip-mesh.md#anatomy-of-pg_vdd_bumpssp).

---

## Lesson 05-cts {#lesson-05-cts}

**Course:** `learn/lessons/05-cts/` · **FlowLab:** [cts](/flow?phase=cts)

| Effect | Power chain |
|---|---|
| Inserted clock buffers | ↑ capacitance + toggle |
| Skew repair | New cells → new sinks |

`report_power` post-CTS often shows significant **Clock** group (~11% on GCD flowlab).

---

## Lesson 06-routing {#lesson-06-routing}

**Course:** `learn/lessons/06-routing/` · **FlowLab:** [route](/flow?phase=route)

| Output | Use |
|---|---|
| `5_*route*.odb` | Complete mesh pre-finish |
| `route.guide` | Congestion (indirect on timing → activity) |
| SPEF (at L07) | Parasitics for STA |

Static IR drop uses **post-route/finish** geometry, not placement alone.

---

## Lesson 07-finish {#lesson-07-finish}

**Course:** `learn/lessons/07-finish/` · **FlowLab:** [finish](/flow?phase=finish) + signoff + [PKG](/flow?phase=pkg)

### ORFS deliverables

| Files | Signoff | SPICE chain |
|---|---|---|
| `6_final.odb` | timing, power | PDNSim input |
| `6_final.gds` | mask/DRC | — |
| `6_final.spef` | STA post-route | — |
| `orfs_final_ir_drop.png` | PDNSim static IR | compare chip IR JSON |

### FlowLab signoff (recommended order)

1. **`activity_power`** → `activity_power_<variant>.log` → **I_die**
2. **`chip_pdn_ir`** → `pg_vdd_bumps.sp` + `pdn_chip_ir_*.json`
3. **`vyges_em_ir`** → same mesh, binary CG + backward Euler (`vyges_em_ir_*.json`)
4. **`dynamic_ir`** → I(t) per pin + heatmap (`dynamic_ir_*.json` + `.svg`)
5. **`system_pdn`** → `system_pdn_*.json` (Zmax, droop)
6. **`power_chain`** → runs activity → chip IR → system → lab export

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_power_chain.sh
```

### GCD flowlab metrics comparison (typical)

| Metric | Chip mesh | System ladder |
|---|---|---|
| Static IR | ~4.5 mV (PDNSim) | — |
| Transient droop mesh | ~39 mV (peak switch) | — |
| Die droop ladder | — | ~6 mV (load-step) |
| Zmax @ die | — | ~9 Ω @ ~224 MHz |

**Educational** numbers — lumped ladder, not real board measurement.

---

## FlowLab PKG phase (post L07) {#pkg-phase}

**Hub:** [/pkg](/pkg) · **Config:** `learn/system_pdn/default.json`

ngspice simulates:

```
VRM (R,L,C,ESR) → board plane/bulk/HF → package RLC/bumps → C_die + I_DIE pulse
```

Report: `learn/sim/reports/system_pdn_<variant>.json`

Deep dive: [spice-ngspice-primer.md](./spice-ngspice-primer.md)

---

## SPICE lab netlists

| Path | Content |
|---|---|
| [sim/spice/README.md](../sim/spice/README.md) | Lab index |
| `system_pdn_tran_demo.sp` | Runnable ladder |
| `nangate_inverter_demo.sp` | Educational cell |
| `export_spice_lab.sh` | Copy mesh + stats |

After export (flowlab):

```json
// mesh_stats_flowlab.json
{ "resistors": 5478, "current_sources": 608, "voltage_sources": ... }
```

---

## Quick commands

```bash
# Individual steps
FLOW_VARIANT=flowlab ./learn/scripts/run_activity_power.sh
FLOW_VARIANT=flowlab ./learn/scripts/run_chip_pdn_ir.sh
FLOW_VARIANT=flowlab ./learn/scripts/run_system_pdn.sh
FLOW_VARIANT=flowlab ./learn/scripts/export_spice_lab.sh

# Full chain
FLOW_VARIANT=flowlab ./learn/scripts/run_power_chain.sh

# ngspice demo
ngspice -b learn/sim/spice/system_pdn_tran_demo.sp
```

---

## Honest limits

- No transistor-level Nangate45 SPICE in ORFS GCD
- VCD → `read_vcd` via `power_vcd.sh` in `run_activity_power.sh` (FlowLab `rtl_sim` → activity)
- Vectorless IR → `run_vectorless.sh` (Najm + Kouroussis)
- System PDN = educational lumped ladder
- Chip `BUMPS` = synthetic OpenROAD pattern (PSM-0073)
- Lessons 00–07 **do not require** SPICE for completion — **post-course** module recommended

---

## Related documentation index

| Doc | When to read |
|---|---|
| [spice-chip-mesh.md](./spice-chip-mesh.md) | After L07, before chip_pdn_ir |
| [spice-ngspice-primer.md](./spice-ngspice-primer.md) | Before PKG / system_pdn |
| [system-pdn.md](./system-pdn.md) | Tool landscape |
| [pkg-design-package.md](./pkg-design-package.md) | Tapeout packaging |
| [extended-flow.md](./extended-flow.md) | §8 optional modules |
| [golden-metrics.md](./golden-metrics.md) | IR heatmap vs report JSON |
| [glossary.md](./glossary.md) | SPICE/ngspice terms |

**UI:** FlowLab shows the chain below the pipeline · Lessons have «Power chain» panel · Post-finish signoff in GDSII phase.
