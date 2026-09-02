# Flusso esteso: RTL → sim → synth → PD → power/DRC → packaging (mappa)

Review of **tool hooks** and how to bring into the treatment (and where already
in the run) the topics: RTL, sim RTL, synthesis, vector activity, DRC, gridcheck,
PDN, bump/RDL/system PDN, thermal.

Legenda stato:

| Status | Meaning |
|---|---|
| **READY** | Nel flusso ORFS/`learn` e usabile ora |
| **PARTIAL** | API/tool presenti; course o wiring incompleto |
| **MISSING** | You need tool/processo fuori scope Nangate45 digitale flat |

Comando ORFS canonico del course:

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 <target>
```

---

## 1. RTL iniziale — READY

| Where | Dettaglio |
|---|---|
| Sorgente | `tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v` |
| Config course | `learn/designs/nangate45/gcd-tutorial/config.mk` → `VERILOG_FILES` |
| Trattazione | Lesson 00 (find RTL), 02 (netlist vs RTL) |

**Studio:** file via materiali / path; you do not need un viewer dedicato.

---

## 2. Simulazione RTL — READY (slice nuovo)

| Componente | Path |
|---|---|
| Testbench | `learn/sim/gcd/tb_gcd.v` |
| Runner | `learn/scripts/run_rtl_sim.sh` |
| Tool | **Icarus Verilog** (`iverilog` / `vvp`) |
| Artifacts | `learn/sim/gcd/sim.log`, `gcd.vcd` |

```bash
./learn/scripts/run_rtl_sim.sh
# aspetta RTL_SIM_PASS + VCD
```

**Studio:** azione `rtl_sim` (console Strumenti).  
**Prossimo passo educational:** wave con GTKWave sul Desktop; Verilator se you need perf.

---

## 3. Sintesi logica — READY

| Layer | Path / hook |
|---|---|
| Yosys ORFS | `flow/scripts/synth*.tcl` → `1_2_yosys.v`, `synth_stat.txt` |
| Inspect | `GET /api/inspect?stage=synth` (Yosys `stat` + ODB) |
| Lesson | 02-synthesis |

```bash
make … synth
```

---

## 4. Vector activity e vectorless — READY

| Layer | Status |
|---|---|
| OpenSTA | `set_power_activity`, **`read_vcd -scope tb_gcd/dut`**, `report_power` |
| Dynamic | VCD Icarus su nomi che matchano il gate netlist (port) |
| Vectorless | global activity 0.5 + envelope Kouroussis (DAC 2003) + Najm \(P_{01}\) |
| Demo | `learn/scripts/run_activity_power.sh` · `run_vectorless.sh` |

```bash
./learn/scripts/run_activity_power.sh
FLOW_VARIANT=flowlab ./learn/scripts/run_vectorless.sh
```

**Studio:** azioni `activity_power` e `vectorless`. Docs: [vectorless-power.md](./vectorless-power.md).

Non usare `read_power_activities` (deprecato, arity rotta in OpenSTA 26Q2).

---

## 5. DRC — READY (route + signoff unificato)

| Tipo | Come |
|---|---|
| Detailed-route DRC | `make … route` → `reports/.../5_route_drc.rpt` (L06) |
| **DRC signoff** | `learn/scripts/run_drc_signoff.sh` → route lines + `make drc` → `drc_signoff_{v}.json` |
| KLayout GDS DRC (legacy) | `learn/scripts/run_klayout_drc.sh` → `6_drc.lyrdb` |
| Magic | tech presente, **non** nel path course |

```bash
# after finish — signoff unificato (preferito)
FLOW_VARIANT=learn ./learn/scripts/run_drc_signoff.sh
```

**Studio:** azione `drc_signoff` · matrice in FlowLab finish / [`/pkg`](/pkg).  
See [signoff-matrix.md](./signoff-matrix.md).

---

## 5b. STA signoff — READY

| Componente | Path |
|---|---|
| Finish report | `reports/.../6_finish.rpt` |
| OpenSTA + SPEF | `run_sta_signoff.sh` |
| Report | `learn/sim/reports/sta_signoff_{v}.json` |
| Gate | vs `learn/signoff/golden-gcd.json` |

**Studio:** azione `sta_signoff` · `GET /api/signoff`.

---

## 5c. LVS signoff — READY (educational)

ORFS: `make lvs` → CDL concat + KLayout LVS → `6_lvs.lvsdb`.

| Componente | Path |
|---|---|
| LVS runset | `platforms/nangate45/lvs/FreePDK45.lylvs` (da [FreePDK45_for_KLayout](https://github.com/laurentc2/FreePDK45_for_KLayout)) |
| Wrapper | `learn/scripts/run_klayout_lvs.sh` |
| Parser UI | `learn/scripts/parse_signoff_artifacts.py` |
| Report | `learn/sim/reports/lvs_signoff_{v}.json` |

**Honest note:** on GCD FreePDK45, LVS may not be tapeout-clean; interpretare the report.

**Studio:** azione `klayout_lvs` · matrice artefatti in FlowLab finish.

---

## 6. Gridcheck (connectivity power grid) — READY (slice)

ORFS lascia `check_power_grid` **commentato** in `pdn.tcl` (CI). On the GCD Nangate
servono spesso `-dont_require_terminals`.

```bash
./learn/scripts/run_gridcheck.sh pdn     # 2_4_floorplan_pdn.odb
./learn/scripts/run_gridcheck.sh final   # 6_final.odb
```

Expected: `PSM-0040 All shapes on net VDD/VSS are connected`.

**Studio:** azione `gridcheck` + sezione inspect.

**IR drop** (different from gridcheck): already in `make … finish` → `analyze_power_grid`
+ heatmap `final_ir_drop` (L07).

---

## 7. PDN (chip-level) — READY

| Item | Path |
|---|---|
| Script | `flow/scripts/pdn.tcl` (`pdngen`) |
| Strategy | `…/gcd/grid_strategy-M1-M4-M7.tcl` |
| Lesson | 03-floorplan |
| GUI | `gui_2_4_floorplan_pdn.odb` / Studio Apri GUI |

---

## 8. Bump · RDL · system PDN — PARTIAL (demo Studio)

OpenROAD espone:

- `assign_io_bump`, `make_io_bump_array`
- `rdl_route`
- `analyze_power_grid -source_type BUMPS|STRAPS|FULL`

**Studio (READY demo):**

| Piece | Where |
|---|---|
| Chip PDN gridcheck | FlowLab fase **PDN** · `FLOW_VARIANT=… ./learn/scripts/run_gridcheck.sh` |
| System PDN (VRM→board→pkg→die) | FlowLab fase **PKG** · `system_pdn` · `run_system_pdn.sh` · ngspice |
| Chip IR static+transient (optional) | `run_chip_pdn_ir.sh` · PDNSim + `pdn_transient.py` |
| vyges-em-ir (engine) | `run_vyges_em_ir.sh` · CG + backward Euler |
| Dynamic IR I(t) | `run_dynamic_ir.sh` · PWL per pin + heatmap |
| Hub packaging | [`/pkg`](/pkg) · [spice-power-chain.md](./spice-power-chain.md) · `system-pdn.md` + `pkg-design-package.md` |

**Guide esaustiva catena fasi:** [spice-power-chain.md](./spice-power-chain.md) — mappa lezioni 00–07 ↔ FlowLab ↔ SPICE.

**Limite onesto:** System PDN is un ladder *lumped* educativo; Nangate45 GCD does not LEF/tech di packaging. Chip IR `BUMPS` use un
pattern sintetico OpenROAD (PSM-0073), non un package tapeout-ready.

**Estensioni future:**

1. Lab su design ORFS con bump LEF reale
2. Board SI/PI models fuori OpenROAD
3. Thermal (HotSpot / 3D-ICE) — ancora MISSING

---

## 9. Thermal analysis — PARTIAL (proxy READY)

Nessun comando thermal nativo in OpenROAD 26Q2; nessun target ORFS HotSpot.

**Slice course (proxy READY):**

| Componente | Path |
|---|---|
| Script | `learn/scripts/run_thermal_signoff.sh` |
| Report | `learn/sim/reports/thermal_signoff_{v}.json` |
| Input | chip IR JSON + heatmap ORFS `orfs_final_ir_drop.png` |
| Studio | azione `thermal_signoff` · matrice Fase 2 su `/pkg` |

Il proxy somma IR statico + droop transient come stima educativa hotspot; soglia 50 mV in the report.

**Opzioni open esterne (non installate):** HotSpot, 3D-ICE.  
**Honest treatment:** “reliability / thermal” chapter with proxy + power map, without pretending tapeout thermal closed-loop.

Power map proxy already available: heatmap IR + `report_power` (activity script).

---

## Agganci Studio (console / API)

| Azione / API | Topic |
|---|---|
| `rtl_sim` | Sim RTL Icarus |
| `gridcheck` | `check_power_grid` |
| `system_pdn` | ngspice System PDN · VRM→board→pkg→die |
| `chip_pdn_ir` | PDNSim + write_pg_spice + pdn_transient |
| `vyges_em_ir` | vyges-em-ir binario su `.pdn` dalla stessa mesh |
| `dynamic_ir` | PWL per ITerm + A LU + B SA-AMG + C Krylov MOR + D RAS |
| `power_chain` | activity → chip IR → system → export lab |
| `activity_power` | `read_vcd` / `set_power_activity` + `report_power` |
| `vectorless` | Vectorless vs dynamic IR (Najm + Kouroussis) |
| `yosys_equiv` | Yosys equiv RTL↔synth (EQY-class) |
| `formal_gcd` | Yosys sat tempinduct (sby-class) |
| `openrcx_report` | OpenRCX SPEF counts |
| `analytical_pex` | Sakurai–Tamaru + FDM 2D (FasterCap-class) |
| `layout_tools` | Magic / Netgen / KLayout probe |
| `tool_matrix` | Orchestrator OSS |
| `klayout_drc` | GDS DRC (legacy, solo GDS) |
| `sta_signoff` | STA vs golden-metrics |
| `drc_signoff` | Route DRC + KLayout GDS unificato |
| `klayout_lvs` | LVS GDS vs CDL |
| `power_signoff` | Catena power + gate golden |
| `signoff_all` | Orchestrator 4 pilastri (+ opz. Fase 2: `SIGNOFF_INCLUDE_PHASE2=1`) |
| `signoff_phase2` | Thermal proxy + PKG orchestrator |
| `thermal_signoff` | Proxy IR+droop hotspot |
| `pkg_signoff` | Bump + RDL edu + system PDN |
| `/api/signoff` | Matrice signoff + gate |
| `/api/inspect` | ODB / STA / Yosys (+ note hook) |
| `/api/viewer` | OpenROAD `-web` |
| `/api/open` | Qt GUI / KLayout |
| fasi `synth`…`finish` | PD classico |

Documentazione hook di basso livello: [tool-hooks.md](./tool-hooks.md).

---

## Piano educational suggerito (estensione)

| Modulo | Quando | Ore stimate (studio) |
|---|---|---|
| RTL + sim + VCD | tra L00 e L02 | 1–2 h |
| Yosys approfondito | L02 | already covered |
| Activity → power | after L07 | 1 h |
| Vectorless / dynamic IR | after L07 + VCD | 1 h |
| Gridcheck + IR | L03 + L07 | 0.5–1 h |
| KLayout DRC | after finish | 0.5–1 h |
| Bump/RDL/system PDN | elettivo avanzato | 2–3 h teoria |
| Thermal | elettivo / lettura | 1 h teoria |

Non allungare il percourse required 00–07: i nuovi script are **modules
opzionali** callsti da Studio e da this mappa.
