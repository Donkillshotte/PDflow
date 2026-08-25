# Syllabus — Corso Physical Design (OpenROAD)

## Filosofia del corso

Ogni lezione segue il ciclo **Spiega → Esegui → Ispeziona → Verifica → Rifletti**:

1. **Spiega** — README.md con teoria e riferimenti ai file
2. **Esegui** — `run.sh` lancia comandi ORFS reali
3. **Ispeziona** — comandi `gui_*` e lettura log/report
4. **Verifica** — checkpoint automatici su artefatti
5. **Rifletti** — domande e varianti (clock, utilization)

Il corso usa il design **GCD** perché:
- Esecuzione rapida (minuti, non ore)
- Abbastanza complesso da avere CTS e routing reali
- Documentato e usato upstream da ORFS

---

## Lezione 00 — Introduzione

**Obiettivi didattici**
- Orientarsi in ORFS
- Conoscere la mappa file per fase
- Eseguire smoke test synth

**Artefatti**
- `1_synth.odb` (opzionale)

**Competenze acquisite**
- Sapere dove trovare scripts, results, logs, reports
- Distinguere modalità file vs GUI

---

## Lezione 01 — Constraints

**Obiettivi didattici**
- Leggere/scrivere SDC
- Capire `create_clock`, I/O delay
- Modificare `config.mk`

**Esercizi**
- A: Analisi SDC default (0.46 ns)
- B: Clock rilassato (2.0 ns) + place
- C: Clock stretto (0.25 ns) + debug fallimento
- D: GUI Endpoint Slack

**File manipolati**
- `constraint.sdc`, `constraint_relaxed.sdc`, `constraint_tight.sdc`
- `config.mk`

**Competenze**
- Collegare constraints → area → timing closure

---

## Lezione 02 — Synthesis

**Obiettivi**
- RTL → gate-level
- Leggere netlist e synth_stat

**Esercizi**
- A: `make synth`
- B: Analisi `1_2_yosys.v`
- C: Log Yosys
- D: GUI `1_synth.odb`
- E: OpenSTA pre-layout

**Script Tcl**
- `synth.tcl`, `synth_stdcells.tcl`

---

## Lezione 03 — Floorplan

**Obiettivi**
- Die, core, rows, sites
- PDN e tapcells

**Esercizi**
- A–B: `make floorplan`
- C: Confronto utilization 25 vs 45
- D: GUI `2_1` e `2_4`
- E: Metriche da log

**Script Tcl**
- `floorplan.tcl`, `pdn.tcl`
- `grid_strategy-M1-M4-M7.tcl`

---

## Lezione 04 — Placement

**Obiettivi**
- Global vs detailed placement
- Resizer e timing pre-CTS

**Esercizi**
- A–B: `make place`
- C: Report global place + resizer
- D: GUI gp vs dp
- E: Log resizer

**Script Tcl**
- `global_place.tcl`, `detail_place.tcl`, `resize.tcl`

---

## Lezione 05 — CTS

**Obiettivi**
- Clock tree, skew, buffer clock
- Debug utilization overflow

**Esercizi**
- A–B: `make cts`
- C: Report CTS
- D: Clock Tree Viewer
- E: Tcl `report_clock_skew`

**Script Tcl**
- `cts.tcl`

---

## Lezione 06 — Routing

**Obiettivi**
- Global route, detailed route, DRC
- Congestion analysis

**Esercizi**
- A–B: `make route`
- C: Guide + DRC report
- D: GUI grt vs route
- E: KLayout guides

**Script Tcl**
- `global_route.tcl`, `detail_route.tcl`

---

## Lezione 07 — Finish

**Obiettivi**
- GDS, SPEF, signoff timing
- Deliverables per fab

**Esercizi**
- A–B: `make finish`
- C: Report 6_finish
- D: Deliverables checklist
- E: GUI final + worst path
- F: Verifica GDS
- G: Progetto finale (sfida)

---

## Comandi di riferimento rapido

```bash
# Wrapper corso
./scripts/learn_physical_design.sh --lesson NN

# ORFS diretto (equivalente)
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn <target>

# Target utili
synth | floorplan | place | cts | route | finish
clean_synth | clean_floorplan | clean_place | clean_cts | clean_route | clean_finish | clean_all
gui_<stem>   # es. gui_3_place.odb, gui_final
```

## Tempo totale stimato (studio attivo)

| Componente | Ore |
|---|---|
| README lezioni 00–07 | 4–5 |
| LAB.md (8 sessioni) | 8–12 |
| Reference + walkthrough Tcl | 3–4 |
| Workbook + quiz + progetto finale | 3–4 |
| GUI guidata | 2–3 |
| **Totale realistico** | **20–28** |

Il wrapper `--auto` dura minuti: **non** è il corso. Il corso è LAB + quaderno + GUI.

---

## Estensioni consigliate (post-corso)

1. **sky130hd/gcd** — PDK più realistico (finer geometry)
2. **Proprio RTL** — contatore, UART, piccolo RISC-V
3. **Tcl scripting** — automatizza sweep clock/utilization
4. **OpenSTA standalone** — timing analysis fuori dal flusso
5. **KLayout DRC/LVS** — verifica geometrica avanzata
