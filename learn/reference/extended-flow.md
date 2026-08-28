# Flusso esteso: RTL → sim → synth → PD → power/DRC → packaging (mappa)

Review degli **agganci tool** e di come portare nella trattazione (e dove già
nel run) i temi: RTL, sim RTL, sintesi, attività vettoriale, DRC, gridcheck,
PDN, bump/RDL/system PDN, thermal.

Legenda stato:

| Stato | Significato |
|---|---|
| **READY** | Nel flusso ORFS/`learn` e usabile ora |
| **PARTIAL** | API/tool presenti; corso o wiring incompleto |
| **MISSING** | Serve tool/processo fuori scope Nangate45 digitale flat |

Comando ORFS canonico del corso:

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 <target>
```

---

## 1. RTL iniziale — READY

| Dove | Dettaglio |
|---|---|
| Sorgente | `tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v` |
| Config corso | `learn/designs/nangate45/gcd-tutorial/config.mk` → `VERILOG_FILES` |
| Trattazione | Lezione 00 (trova RTL), 02 (netlist vs RTL) |

**Studio:** file via materiali / path; non serve un viewer dedicato.

---

## 2. Simulazione RTL — READY (slice nuovo)

| Componente | Path |
|---|---|
| Testbench | `learn/sim/gcd/tb_gcd.v` |
| Runner | `learn/scripts/run_rtl_sim.sh` |
| Tool | **Icarus Verilog** (`iverilog` / `vvp`) |
| Artefatti | `learn/sim/gcd/sim.log`, `gcd.vcd` |

```bash
./learn/scripts/run_rtl_sim.sh
# aspetta RTL_SIM_PASS + VCD
```

**Studio:** azione `rtl_sim` (console Strumenti).  
**Prossimo passo didattico:** wave con GTKWave sul Desktop; Verilator se serve perf.

---

## 3. Sintesi logica — READY

| Layer | Path / hook |
|---|---|
| Yosys ORFS | `flow/scripts/synth*.tcl` → `1_2_yosys.v`, `synth_stat.txt` |
| Inspect | `GET /api/inspect?stage=synth` (Yosys `stat` + ODB) |
| Lezione | 02-synthesis |

```bash
make … synth
```

---

## 4. Attività vettoriale (SAIF/VCD → power) — PARTIAL → slice demo

| Layer | Stato |
|---|---|
| OpenROAD | `set_power_activity`, `read_power_activities -vcd`, `report_power` |
| ORFS GCD | non legge VCD/SAIF di default (IR usa default liberty) |
| Demo corso | `learn/scripts/run_activity_power.sh` (attività globale 0.2) |
| Vettori reali | VCD da `run_rtl_sim.sh` → poi `read_power_activities -vcd …` (esercizio avanzato) |

```bash
./learn/scripts/run_activity_power.sh
```

**Trattazione consigliata:** dopo lezione 07 (hai `6_final.odb`); confronta power
default vs attività sintetica vs (opz.) VCD annotato.

---

## 5. DRC — READY (route + signoff unificato)

| Tipo | Come |
|---|---|
| Detailed-route DRC | `make … route` → `reports/.../5_route_drc.rpt` (L06) |
| **DRC signoff** | `learn/scripts/run_drc_signoff.sh` → route lines + `make drc` → `drc_signoff_{v}.json` |
| KLayout GDS DRC (legacy) | `learn/scripts/run_klayout_drc.sh` → `6_drc.lyrdb` |
| Magic | tech presente, **non** nel path corso |

```bash
# dopo finish — signoff unificato (preferito)
FLOW_VARIANT=learn ./learn/scripts/run_drc_signoff.sh
```

**Studio:** azione `drc_signoff` · matrice in FlowLab finish / [`/pkg`](/pkg).  
Vedi [signoff-matrix.md](./signoff-matrix.md).

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
| Wrapper | `learn/scripts/run_klayout_lvs.sh` |
| Report | `learn/sim/reports/lvs_signoff_{v}.json` |
| Stamp | `results/.../.lvs.ok` |

**Nota onesta:** su GCD FreePDK45, LVS può non essere tapeout-clean; interpretare il report.

**Studio:** azione `klayout_lvs`.

---

## 6. Gridcheck (connettività power grid) — READY (slice)

ORFS lascia `check_power_grid` **commentato** in `pdn.tcl` (CI). Sul GCD Nangate
servono spesso `-dont_require_terminals`.

```bash
./learn/scripts/run_gridcheck.sh pdn     # 2_4_floorplan_pdn.odb
./learn/scripts/run_gridcheck.sh final   # 6_final.odb
```

Atteso: `PSM-0040 All shapes on net VDD/VSS are connected`.

**Studio:** azione `gridcheck` + sezione inspect.

**IR drop** (diverso da gridcheck): già in `make … finish` → `analyze_power_grid`
+ heatmap `final_ir_drop` (L07).

---

## 7. PDN (chip-level) — READY

| Item | Path |
|---|---|
| Script | `flow/scripts/pdn.tcl` (`pdngen`) |
| Strategy | `…/gcd/grid_strategy-M1-M4-M7.tcl` |
| Lezione | 03-floorplan |
| GUI | `gui_2_4_floorplan_pdn.odb` / Studio Apri GUI |

---

## 8. Bump · RDL · system PDN — PARTIAL (demo Studio)

OpenROAD espone:

- `assign_io_bump`, `make_io_bump_array`
- `rdl_route`
- `analyze_power_grid -source_type BUMPS|STRAPS|FULL`

**Studio (READY demo):**

| Pezzo | Dove |
|---|---|
| Chip PDN gridcheck | FlowLab fase **PDN** · `FLOW_VARIANT=… ./learn/scripts/run_gridcheck.sh` |
| System PDN (VRM→board→pkg→die) | FlowLab fase **PKG** · `system_pdn` · `run_system_pdn.sh` · ngspice |
| Chip IR static+transient (opzionale) | `run_chip_pdn_ir.sh` · PDNSim + `pdn_transient.py` |
| Hub packaging | [`/pkg`](/pkg) · [spice-power-chain.md](./spice-power-chain.md) · `system-pdn.md` + `pkg-design-package.md` |

**Guida esaustiva catena fasi:** [spice-power-chain.md](./spice-power-chain.md) — mappa lezioni 00–07 ↔ FlowLab ↔ SPICE.

**Limite onesto:** System PDN è un ladder *lumped* educativo; Nangate45 GCD non ha LEF/tech di packaging. Chip IR `BUMPS` usa un
pattern sintetico OpenROAD (PSM-0073), non un package tapeout-ready.

**Estensioni future:**

1. Lab su design ORFS con bump LEF reale
2. Board SI/PI models fuori OpenROAD
3. Thermal (HotSpot / 3D-ICE) — ancora MISSING

---

## 9. Thermal analysis — PARTIAL (proxy READY)

Nessun comando thermal nativo in OpenROAD 26Q2; nessun target ORFS HotSpot.

**Slice corso (proxy READY):**

| Componente | Path |
|---|---|
| Script | `learn/scripts/run_thermal_signoff.sh` |
| Report | `learn/sim/reports/thermal_signoff_{v}.json` |
| Input | chip IR JSON + heatmap ORFS `orfs_final_ir_drop.png` |
| Studio | azione `thermal_signoff` · matrice Fase 2 su `/pkg` |

Il proxy somma IR statico + droop transient come stima educativa hotspot; soglia 50 mV nel report.

**Opzioni open esterne (non installate):** HotSpot, 3D-ICE.  
**Trattazione onesta:** capitolo “affidabilità / thermal” con proxy + power map, senza fingere tapeout thermal closed-loop.

Power map proxy già disponibile: heatmap IR + `report_power` (activity script).

---

## Agganci Studio (console / API)

| Azione / API | Topic |
|---|---|
| `rtl_sim` | Sim RTL Icarus |
| `gridcheck` | `check_power_grid` |
| `system_pdn` | ngspice System PDN · VRM→board→pkg→die |
| `chip_pdn_ir` | PDNSim + write_pg_spice + pdn_transient |
| `power_chain` | activity → chip IR → system → export lab |
| `activity_power` | `set_power_activity` + `report_power` |
| `klayout_drc` | GDS DRC (legacy, solo GDS) |
| `sta_signoff` | STA vs golden-metrics |
| `drc_signoff` | Route DRC + KLayout GDS unificato |
| `klayout_lvs` | LVS GDS vs CDL |
| `power_signoff` | Catena power + gate golden |
| `signoff_all` | Orchestrator 4 pilastri |
| `thermal_signoff` | Proxy IR+droop hotspot |
| `pkg_signoff` | Bump + RDL edu + system PDN |
| `/api/signoff` | Matrice signoff + gate |
| `/api/inspect` | ODB / STA / Yosys (+ note hook) |
| `/api/viewer` | OpenROAD `-web` |
| `/api/open` | Qt GUI / KLayout |
| fasi `synth`…`finish` | PD classico |

Documentazione hook di basso livello: [tool-hooks.md](./tool-hooks.md).

---

## Piano didattico suggerito (estensione)

| Modulo | Quando | Ore stimate (studio) |
|---|---|---|
| RTL + sim + VCD | tra L00 e L02 | 1–2 h |
| Yosys approfondito | L02 | già coperto |
| Activity → power | dopo L07 | 1 h |
| Gridcheck + IR | L03 + L07 | 0.5–1 h |
| KLayout DRC | dopo finish | 0.5–1 h |
| Bump/RDL/system PDN | elettivo avanzato | 2–3 h teoria |
| Thermal | elettivo / lettura | 1 h teoria |

Non allungare il percorso obbligatorio 00–07: i nuovi script sono **moduli
opzionali** richiamati da Studio e da questa mappa.
