# Playbook di debug — Physical Design con OpenROAD

Guida operativa quando qualcosa va storto. Leggila **prima** di panic, **durante** ogni lezione.

---

## Metodologia generale (sempre uguale)

```
1. Identifica la FASE (synth? floorplan? cts?)
2. Apri il LOG della fase (logs/.../learn/<step>.log)
3. Cerca ERROR, WARNING critici, codici (DPL-0038, RSZ-0062, STA-2204)
4. Apri l'ODB di errore se esiste (gui_<step>_error.odb)
5. Confronta con l'ODB dello step precedente
6. Modifica UN parametro alla volta (SDC o config.mk)
7. clean_<fase> e rilancia solo da lì
```

Non cambiare cinque variabili insieme: non capirai mai quale ha causato l'effetto.

---

## Errori per fase

### Synthesis (step 1_x)

| Sintomo | Causa probabile | Fix |
|---|---|---|
| `No such command: source` | yosys senza Tcl | reinstall yosys con `tcl-dev`, vedi script 04 |
| `Error parsing options: Option 'c'` | yosys 0.68+ vs ORFS vecchio | allinea tag ORFS a OpenROAD (26Q2) |
| Celle unmapped | libreria mancante | verifica LIB_FILES in platform config |
| Latch inferiti | RTL senza reset | controlla always block in gcd.v |

**File da aprire:** `logs/.../1_2_yosys.log`, `reports/.../synth_stat.txt`

---

### Floorplan (step 2_x)

| Sintomo | Causa probabile | Fix |
|---|---|---|
| Core area troppo piccola | CORE_UTILIZATION alta | abbassa a 25–35% |
| `Floorplan methods mutually exclusive` | DIE_AREA + UTILIZATION insieme | usa solo uno in config.mk |
| PDN non visibile in GUI | layer PDN disabilitati | Display Control → PDN → visible |
| IO pin fuori core | vincoli IO | controlla `3_2_place_iop` (fase successiva) |

**File:** `logs/2_1_floorplan.log` — cerca `Core area`, `Effective utilization`

**Esercizio debug:** confronta utilization 25 vs 55 e annota area core nel quaderno.

---

### Placement (step 3_x)

| Sintomo | Causa probabile | Fix |
|---|---|---|
| Overflow alto post-GP | densità eccessiva | PLACE_DENSITY, CORE_UTILIZATION |
| RSZ inserisce centinaia di buffer | clock troppo stretto | rilassa SDC |
| WNS molto negativo pre-CTS | normale su design stretti | osserva se migliora post-route |
| `place_density` error | config incoerente | leggi variables.mk del platform |

**File:** `reports/3_global_place.rpt`, `reports/3_resizer.rpt`, `logs/3_4_place_resized.log`

**GUI:** confronta `gui_3_3_place_gp` vs `gui_3_5_place_dp` — vedi legalizzazione.

---

### CTS (step 4_x) — il più didattico

| Sintomo | Causa probabile | Fix |
|---|---|---|
| **`DPL-0038 Utilization > 100%`** | area celle > area core | ↓ utilization, ↑ clock period |
| `RSZ-0062 Unable to repair all setup` | timing irrealistico | constraint_relaxed.sdc |
| `Detailed placement failed in CTS` | idem | gui_4_1_error.odb |
| Clock tree vuoto in viewer | clock non propagated | verifica create_clock in SDC |

**Sequenza tipica del nostro corso con clock 0.25 ns + util 55%:**
1. Placement OK
2. Resizer gonfia area del ~30%
3. CTS detailed placement fallisce al 100.2% utilization

**Fix didattico (scegli uno):**
- `CORE_UTILIZATION=30`
- `constraint_relaxed.sdc` (2.0 ns)
- Entrambi per confronto

---

### Routing (step 5_x)

| Sintomo | Causa probabile | Fix |
|---|---|---|
| GRT overflow | congestione | abbassa density, ripeti place |
| DRC non zero | spacing/width | `reports/5_route_drc.rpt` riga per riga |
| Antenna violations | routing su gate | diodi antenna (step finishing) |
| Route non completa | guide mancanti | verifica `route.guide` size > 0 |

### GUI

| Sintomo | Causa probabile | Fix |
|---|---|---|
| Preview Cursor nera / “non disponibile” | Preview ≠ VNC | **Desktop** su cursor.com/agents |
| Canvas nero su `1_synth` | nessun die | normale; vai a floorplan |
| `GUI-0013` su `"Rows"` | nome controllo inesistente | non usare quella stringa; vedi atlante §5.2 |
| `sta_error 563` su `report_checks -path_delay max` | flag non valido in questa STA | `report_checks -max_paths 3` |
| Layer accesi ma “non vedo il clock” | i fili sono geometria layer | `select -name "clk" -type Net` |
| `save_image` GUI-0078 su `2_1_floorplan` | poca geometria | usa `2_4` PDN o la finestra Qt |

Vedi `gui-atlas.md`.

---

### Finish (step 6_x)

| Sintomo | Causa probabile | Fix |
|---|---|---|
| `STA-2204 get_property default` | mismatch ORFS/OpenROAD version | allinea tag 26Q2 |
| GUI save_images fallisce | headless / no display | normale in batch; GDS ok comunque |
| GDS vuoto | merge fallito | `logs/6_1_merge.log`, klayout installato? |
| Slack peggiora post-route | parassiti reali | normale; confronta pre/post SPEF |

---

## Checklist pre-run (copia-incolla)

Prima di ogni sessione di studio:

- [ ] `./scripts/learn_physical_design.sh --check` verde
- [ ] `FLOW_VARIANT=learn` (non sovrascrivere base)
- [ ] SDC backup se fai esperimenti (`cp constraint.sdc constraint.sdc.bak`)
- [ ] Desktop Cursor aperto se serve GUI
- [ ] Quaderno / file note aperto (`learn/workbook/notes-template.md`)

---

## Comandi di emergenza

Da `tools/OpenROAD-flow-scripts/flow` il comando **canonico** (mai puntini):

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 <target>
```

`<target>`: `synth` `floorplan` `place` `cts` `route` `finish` `clean_<fase>` `gui_<stem>.odb`

```bash
# Stato artefatti
ls -lh tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/

# Ultimo errore in log
rg -n 'ERROR|Error:' tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/

# GUI ultimo snapshot
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_4_1_error.odb

# Reset solo una fase (copia intero — mai «make ...»)
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
Ipotesi:
Fix provato:
Risultato:
Lezione appresa:
```

Salva in `learn/workbook/mio-debug-log.md`.
