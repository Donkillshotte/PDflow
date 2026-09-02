# LAB 03 — Floorplan (90–120 minute session)

## Measurable objectives

- Draw die/core/rows on paper from the log
- Explain the 4 ORFS floorplan init methods
- Identify PDN VDD/VSS in the GUI
- Predict the effect of utilization on core area

---

## Part 1 — Visual theory (15 min)

```
┌──────────────────────── DIE ────────────────────────┐
│  margin                                             │
│    ┌────────────── CORE ──────────────┐             │
│    │ row row row row row row row row  │             │
│    │  ▢  ▢  ▢  ▢  ▢  ▢  ▢  ▢  cells  │             │
│    │ row row row row row row row row  │             │
│    └──────────────────────────────────┘             │
│  margin                                             │
└─────────────────────────────────────────────────────┘
     ↑ metal4/7 stripes VDD/VSS (PDN)
```

Read: `learn/reference/walkthrough-floorplan.tcl.md` (30 min recommended).

---

## Part 2 — Run floorplan (20 min)

```bash
./scripts/learn_physical_design.sh --lesson 03
```

Or manual:
```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 floorplan
```

Verify output:
```bash
ls -lh results/nangate45/gcd/learn/2_*.odb
```

Expected: `2_1_floorplan.odb`, `2_2_floorplan_macro.odb`, `2_3_floorplan_tapcell.odb`, `2_4_floorplan_pdn.odb`, `2_floorplan.odb`

---

## Part 3 — Log analysis (25 min)

```bash
rg -n 'Core area|Die area|utilization|initialize_floorplan' \
  tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/learn/2_1_floorplan.log
```

Fill in the notebook table:

| Metric | Value | Unit |
|---|---|---|
| Core area | | µm² |
| Effective utilization | | ratio |
| Site name | | text |

**Workbook exercise B1:** repeat with `CORE_UTILIZATION=25` and `50`.

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=25 clean_floorplan floorplan
# note Core area from log 2_1_floorplan.log
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=50 clean_floorplan floorplan
```

Question: does core area scale linearly with 1/utilization? (approximately yes)

---

## Part 4 — PDN Tcl (20 min)

Open: `flow/designs/nangate45/gcd/grid_strategy-M1-M4-M7.tcl`

Identify:
1. `set_voltage_domain` — which power/ground net?
2. `add_pdn_stripe` — which layers?
3. `add_pdn_connect` — which via stack?

Draw by hand: M1 followpin → M4 → M7

---

## Part 5 — GUI session (30 min)

Atlas required: `learn/reference/gui-atlas.md` §5.2–5.4 (PNG `win_floorplan.png`, `win_pdn.png`, `03_pdn_labeled.png`).

### Session A — Core init
```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_2_1_floorplan.odb
```

Checklist:
- [ ] Fit (`F`) — two concentric rectangles (die / core)
- [ ] Nearly empty canvas: **normal** (no logic placed)
- [ ] **Do not** use `gui::set_display_controls "Rows" visible true` → `GUI-0013` in this build; search for Rows in the tree if present, otherwise skip to PDN
- [ ] Visual aspect ratio ~1.0

### Session B — PDN
```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_2_4_floorplan_pdn.odb
```

Checklist (Nangate45 colors in *this* GUI):
- [ ] Dense blue lines = M1 followpin rails
- [ ] Green vertical straps + pink horizontal straps
- [ ] Display Control: turn off metal2/metal3 to “clean up” the signal (not there yet)
- [ ] Tcl: `gui::set_display_controls "Nets/Power" visible true`
- [ ] Tapcell: `gui_2_3_floorplan_tapcell.odb` or PNG `win_tapcell.png`

**Scavenger hunt B3:** note strap vs rail colors in the notebook; compare with `03_pdn_labeled.png`.

---

## Part 6 — Pre/post floorplan comparison (10 min)

| File | Cells placed? | Routing? | PDN? |
|---|---|---|---|
| 1_synth.odb | no (0,0 stack) | no | no |
| 2_1_floorplan.odb | no | no | no |
| 2_4_floorplan_pdn.odb | no | no | yes |

Floorplan **does not place logic cells** — it only prepares the “ground”.

---

## “Lesson passed” criteria

- [ ] Utilization vs core area table (3 rows)
- [ ] PDN explained aloud in 60 seconds
- [ ] PDN GUI screenshot or description
- [ ] Read walkthrough-floorplan.tcl.md completely

Next LAB: 04-placement (global vs detailed)
