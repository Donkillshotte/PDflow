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

## 5. DRC — READY (route) / PARTIAL→script (KLayout GDS)

| Tipo | Come |
|---|---|
| Detailed-route DRC | `make … route` → `reports/.../5_route_drc.rpt` (L06) |
| KLayout GDS DRC | `make … drc` / `learn/scripts/run_klayout_drc.sh` → `6_drc.lyrdb` |
| Magic | tech presente, **non** nel path corso |

```bash
# dopo finish
./learn/scripts/run_klayout_drc.sh
```

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
| System PDN IR | FlowLab fase **PKG** · azione `system_pdn` · `run_system_pdn.sh` |
| Hub packaging | [`/pkg`](/pkg) · docs `system-pdn.md` + `pkg-design-package.md` |

**Limite onesto:** Nangate45 GCD non ha LEF/tech di packaging; `BUMPS` usa un
pattern sintetico OpenROAD (PSM-0073), non un package tapeout-ready.

**Estensioni future:**

1. Lab su design ORFS con bump LEF reale
2. Board SI/PI models fuori OpenROAD
3. Thermal (HotSpot / 3D-ICE) — ancora MISSING

---

## 9. Thermal analysis — MISSING

Nessun comando thermal in OpenROAD 26Q2 di questa VM; nessun target ORFS.

**Opzioni open esterne (non installate):** HotSpot, 3D-ICE, tool vendor.  
**Trattazione onesta:** capitolo “affidabilità / thermal” qualitativo (power map
→ hotspot → derating timing) senza fingere un flow chiuso.

Power map proxy già disponibile: heatmap IR + `report_power` (activity script).

---

## Agganci Studio (console / API)

| Azione / API | Topic |
|---|---|
| `rtl_sim` | Sim RTL Icarus |
| `gridcheck` | `check_power_grid` |
| `system_pdn` | `analyze_power_grid` STRAPS/FULL/BUMPS |
| `activity_power` | `set_power_activity` + `report_power` |
| `klayout_drc` | GDS DRC (lungo) |
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
