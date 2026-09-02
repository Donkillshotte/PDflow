# Playbook di debug — Physical Design con OpenROAD

Guide operativa quando qualcosa va storto. Leggila **prima** di panic, **durante** every lesson.

---

## Metodologia generale (sempre uguale)

```
1. Identifica la FASE (synth? floorplan? cts?)
2. Apri il LOG della fase (logs/.../learn/<step>.log)
3. Search for ERROR, WARNING critici, codici (DPL-0038, RSZ-0062, STA-2204)
4. Apri l'ODB di errore se esiste (gui_<step>_error.odb)
5. Compare con l'ODB of the step precedente
6. Modify UN parayardstick alla volta (SDC o config.mk)
7. clean_<stage> and rerun only from there
```

Non cambiare cinque variabili insieme: non capirai never quale ha causato l'effetto.

---

## Errori per fase

### Synthesis (step 1_x)

| Sintomo | Cause probabile | Fix |
|---|---|---|
| `No such command: source` | yosys senza Tcl | reinstall yosys con `tcl-dev`, see script 04 |
| `Error parsing options: Option 'c'` | yosys 0.68+ vs ORFS vecchio | allinea tag ORFS a OpenROAD (26Q2) |
| Celle unmapped | libreria mancante | verifica LIB_FILES in platform config |
| Latch inferiti | RTL senza reset | controlla always block in gcd.v |

**Files da aprire:** `logs/.../1_2_yosys.log`, `reports/.../synth_stat.txt`

---

### Floorplan (step 2_x)

| Sintomo | Cause probabile | Fix |
|---|---|---|
| Core area troppo piccola | CORE_UTILIZATION alta | abbassa a 25–35% |
| `Floorplan methods mutually exclusive` | DIE_AREA + UTILIZATION insieme | use solo uno in config.mk |
| PDN non visibile in GUI | layer PDN disabilitati | Display Control → PDN → visible |
| IO pin fuori core | vincoli IO | controlla `3_2_place_iop` (fase successiva) |

**Files:** `logs/2_1_floorplan.log` — search for `Core area`, `Effective utilization`

**Exercise debug:** confronta utilization 25 vs 55 e note area core nel notebook.

---

### Placement (step 3_x)

| Sintomo | Cause probabile | Fix |
|---|---|---|
| High overflow post-GP | excessive density | PLACE_DENSITY, CORE_UTILIZATION |
| RSZ inserisce centinaia di buffer | clock troppo stretto | rilassa SDC |
| WNS molto negativo pre-CTS | normale su design stretti | osserva se migliora post-route |
| `place_density` error | config incoerente | leggi variables.mk del platform |

**Files:** `reports/3_global_place.rpt`, `reports/3_resizer.rpt`, `logs/3_4_place_resized.log`

**GUI:** confronta `gui_3_3_place_gp` vs `gui_3_5_place_dp` — see legalizzazione.

---

### CTS (step 4_x) — the most educational

| Sintomo | Cause probabile | Fix |
|---|---|---|
| **`DPL-0038 Utilization > 100%`** | area celle > area core | ↓ utilization, ↑ clock period |
| `RSZ-0062 Unable to repair all setup` | timing irrealistico | constraint_relaxed.sdc |
| `Detailed placement failed in CTS` | idem | gui_4_1_error.odb |
| Clock tree vuoto in viewer | clock non propagated | verifica create_clock in SDC |

**Sequenza tipica del nostro course con clock 0.25 ns + util 55%:**
1. Placement OK
2. Resizer inflates area del ~30%
3. CTS detailed placement fallisce al 100.2% utilization

**Fix educational (scegli uno):**
- `CORE_UTILIZATION=30`
- `constraint_relaxed.sdc` (2.0 ns)
- Entrambi per comparison

---

### Routing (step 5_x)

| Sintomo | Cause probabile | Fix |
|---|---|---|
| GRT overflow | congestione | abbassa density, ripeti place |
| DRC non zero | spacing/width | `reports/5_route_drc.rpt` riga per riga |
| Antenna violations | routing su gate | diodi antenna (step finishing) |
| Route non completa | guide mancanti | verifica `route.guide` size > 0 |

### GUI

| Sintomo | Cause probabile | Fix |
|---|---|---|
| Preview Cursor nera / “non disponibile” | Preview ≠ VNC | **Desktop** su cursor.com/agents |
| Canvas nero su `1_synth` | nessun die | normale; vai a floorplan |
| `GUI-0013` su `"Rows"` | nome controllo inesistente | non usare quella stringa; see atlas §5.2 |
| `sta_error 563` su `report_checks -path_delay max` | flag non valido in this STA | `report_checks -max_paths 3` |
| Layer accesi ma “non vedo the clock” | i fili are geometria layer | `select -name "clk" -type Net` |
| `save_image` GUI-0078 su `2_1_floorplan` | poca geometria | use `2_4` PDN o the window Qt |

See `gui-atlas.md`.

---

### Finish (step 6_x)

| Sintomo | Cause probabile | Fix |
|---|---|---|
| `STA-2204 get_property default` | mismatch ORFS/OpenROAD version | allinea tag 26Q2 |
| GUI save_images fallisce | headless / no display | normale in batch; GDS ok comunque |
| GDS vuoto | merge failed | `logs/6_1_merge.log`, klayout installato? |
| Slack peggiora post-route | parasitics reali | normale; confronta pre/post SPEF |

---

## Checklist pre-run (copia-incolla)

Before di every sessione di studio:

- [ ] `./scripts/learn_physical_design.sh --check` green
- [ ] `FLOW_VARIANT=learn` (non sovrascrivere base)
- [ ] SDC backup se fai esperimenti (`cp constraint.sdc constraint.sdc.bak`)
- [ ] Desktop Cursor aperto se you need GUI
- [ ] Notebook / file note aperto (`learn/workbook/notes-template.md`)

---

## Comandi di emergenza

Da `tools/OpenROAD-flow-scripts/flow` il comando **canonico** (never puntini):

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 <target>
```

`<target>`: `synth` `floorplan` `place` `cts` `route` `finish` `clean_<stage>` `gui_<stem>.odb`

```bash
# Status artefatti
ls -lh tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/

# Ultimo errore in log
rg -n 'ERROR|Error:' tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/

# GUI ultimo snapshot
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_4_1_error.odb

# Reset solo una fase (copia intero — never «make ...»)
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 clean_cts
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 cts
```

---

## Diario di debug (template)

Quando qualcosa fallisce, scrivi:

```
Data:
Fase:
Comando eseguito:
Errore (copia-incolla 3 righe dal log):
CORE_UTILIZATION:
clk_period SDC:
Hypothesis:
Fix provato:
Risultato:
Lesson appresa:
```

Salva in `learn/workbook/mio-debug-log.md`.
