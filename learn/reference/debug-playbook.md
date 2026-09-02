# Debug playbook — Physical Design with OpenROAD

Operational guide for when something goes wrong. Read it **before** you panic, **during** every lesson.

---

## General methodology (always the same)

```
1. Identify the PHASE (synth? floorplan? cts?)
2. Open the phase LOG (logs/.../learn/<step>.log)
3. Search for ERROR, critical WARNINGs, codes (DPL-0038, RSZ-0062, STA-2204)
4. Open the error ODB if it exists (gui_<step>_error.odb)
5. Compare with the ODB from the previous step
6. Change ONE variable at a time (SDC or config.mk)
7. clean_<stage> and rerun only from there
```

Do not change five variables at once: you will never know which one caused the effect.

---

## Errors by phase

### Synthesis (step 1_x)

| Symptom | Probable cause | Fix |
|---|---|---|
| `No such command: source` | yosys without Tcl | reinstall yosys with `tcl-dev`, see script 04 |
| `Error parsing options: Option 'c'` | yosys 0.68+ vs old ORFS | align ORFS tag to OpenROAD (26Q2) |
| Unmapped cells | missing library | verify LIB_FILES in platform config |
| Inferred latches | RTL without reset | check always blocks in gcd.v |

**Files to open:** `logs/.../1_2_yosys.log`, `reports/.../synth_stat.txt`

---

### Floorplan (step 2_x)

| Symptom | Probable cause | Fix |
|---|---|---|
| Core area too small | high CORE_UTILIZATION | lower to 25–35% |
| `Floorplan methods mutually exclusive` | DIE_AREA + UTILIZATION together | use only one in config.mk |
| PDN not visible in GUI | PDN layers disabled | Display Control → PDN → visible |
| IO pin outside core | IO constraints | check `3_2_place_iop` (next phase) |

**Files:** `logs/2_1_floorplan.log` — search for `Core area`, `Effective utilization`

**Debug exercise:** compare utilization 25 vs 55 and note core area in the notebook.

---

### Placement (step 3_x)

| Symptom | Probable cause | Fix |
|---|---|---|
| High overflow post-GP | excessive density | PLACE_DENSITY, CORE_UTILIZATION |
| RSZ inserts hundreds of buffers | clock too tight | relax SDC |
| Very negative WNS pre-CTS | normal on tight designs | observe whether it improves post-route |
| `place_density` error | inconsistent config | read variables.mk of the platform |

**Files:** `reports/3_global_place.rpt`, `reports/3_resizer.rpt`, `logs/3_4_place_resized.log`

**GUI:** compare `gui_3_3_place_gp` vs `gui_3_5_place_dp` — see legalization.

---

### CTS (step 4_x) — the most educational

| Symptom | Probable cause | Fix |
|---|---|---|
| **`DPL-0038 Utilization > 100%`** | cell area > core area | ↓ utilization, ↑ clock period |
| `RSZ-0062 Unable to repair all setup` | unrealistic timing | constraint_relaxed.sdc |
| `Detailed placement failed in CTS` | same as above | gui_4_1_error.odb |
| Empty clock tree in viewer | clock not propagated | verify create_clock in SDC |

**Typical sequence in our course with clock 0.25 ns + util 55%:**
1. Placement OK
2. Resizer inflates area by ~30%
3. CTS detailed placement fails at 100.2% utilization

**Educational fix (pick one):**
- `CORE_UTILIZATION=30`
- `constraint_relaxed.sdc` (2.0 ns)
- Both for comparison

---

### Routing (step 5_x)

| Symptom | Probable cause | Fix |
|---|---|---|
| GRT overflow | congestion | lower density, rerun place |
| DRC non-zero | spacing/width | `reports/5_route_drc.rpt` line by line |
| Antenna violations | routing on gate | antenna diodes (finishing step) |
| Route incomplete | missing guides | verify `route.guide` size > 0 |

### GUI

| Symptom | Probable cause | Fix |
|---|---|---|
| Black Preview / “not available” | Preview ≠ VNC | **Desktop** on cursor.com/agents |
| Black canvas on `1_synth` | no die | normal; go to floorplan |
| `GUI-0013` on `"Rows"` | control name does not exist | do not use that string; see atlas §5.2 |
| `sta_error 563` on `report_checks -path_delay max` | invalid flag in this STA | `report_checks -max_paths 3` |
| Layers on but “cannot see the clock” | wires are layer geometry | `select -name "clk" -type Net` |
| `save_image` GUI-0078 on `2_1_floorplan` | little geometry | use `2_4` PDN or the Qt window |

See `gui-atlas.md`.

---

### Finish (step 6_x)

| Symptom | Probable cause | Fix |
|---|---|---|
| `STA-2204 get_property default` | ORFS/OpenROAD version mismatch | align tag 26Q2 |
| GUI save_images fails | headless / no display | normal in batch; GDS ok anyway |
| Empty GDS | merge failed | `logs/6_1_merge.log`, klayout installed? |
| Slack worsens post-route | real parasitics | normal; compare pre/post SPEF |

---

## Pre-run checklist (copy-paste)

Before every study session:

- [ ] `./scripts/learn_physical_design.sh --check` green
- [ ] `FLOW_VARIANT=learn` (do not overwrite base)
- [ ] SDC backup if you run experiments (`cp constraint.sdc constraint.sdc.bak`)
- [ ] Cursor Desktop open if you need GUI
- [ ] Notebook / notes file open (`learn/workbook/notes-template.md`)

---

## Emergency commands

From `tools/OpenROAD-flow-scripts/flow` the **canonical** command (never ellipsis):

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 <target>
```

`<target>`: `synth` `floorplan` `place` `cts` `route` `finish` `clean_<stage>` `gui_<stem>.odb`

```bash
# Artifact status
ls -lh tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/

# Latest error in log
rg -n 'ERROR|Error:' tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/

# GUI latest snapshot
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_4_1_error.odb

# Reset only one phase (copy entire command — never «make ...»)
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 clean_cts
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 cts
```

---

## Debug diary (template)

When something fails, write:

```
Date:
Phase:
Command run:
Error (copy-paste 3 lines from log):
CORE_UTILIZATION:
clk_period SDC:
Hypothesis:
Fix tried:
Result:
Lesson learned:
```

Save in `learn/workbook/my-debug-log.md`.
