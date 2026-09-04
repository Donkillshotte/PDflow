# OpenROAD GUI Guide — panels, menus, Tcl

**Atlas with real screenshots (required):** [gui-atlas.md](./gui-atlas.md)  
PNG in [gui-shots/](./gui-shots/) captured from OpenROAD Qt 26Q2 on the GCD `learn`.

OpenROAD Qt. Layout window after `gui_*.odb` (same labeled rectangles A–G in the atlas):

```
┌──────────────┬────────────────────────────┬─────────────────┐
│ Display      │                            │ Inspector /     │
│ Control      │      Layout canvas         │ Charts          │
│ (layer tree) │                            │                 │
├──────────────┴────────────────────────────┴─────────────────┤
│ Scripting console (Tcl)                                     │
└─────────────────────────────────────────────────────────────┘
```

**How to open:** **Desktop** button on cursor.com/agents (not Preview chat).

**Also from Studio:** Ctrl+K → OpenROAD · …, or **Open GUI** on `.odb` files.
For **Web Viewer** (browser, without Qt): Tools → **Open Web Viewer**
(`openroad -web`, see [tool-hooks.md](./tool-hooks.md)).

---

## Launch

```bash
cd /workspace/tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_3_place.odb
```

Expected title: `OpenROAD - nangate45/gcd/learn - 3_place`

If you do not see the window: Alt+Tab, or **OpenROAD GCD** icon on XFCE desktop.

---

## Display Control panel (left)

Visibility tree. Click the **eye** or checkbox:

| Node | When to use |
|---|---|
| Layers / metal1 … metal10 | Routing (lesson 06–07) |
| Layers / via1 … | Via stack |
| Nets / Signal | Logic interconnections |
| Nets / Clock | Clock only (CTS) |
| Nets / Power, Ground | PDN |
| Instances / StdCells | Logic cells |
| Instances / Physical / Fill | Fill (finish) |
| Rows | Floorplan (lesson 03) |
| Blockages | Placement obstacles |
| Heat Maps / Placement Density | Lesson 04 |
| Heat Maps / Routing Congestion | Lesson 06 |
| Heat Maps / IR Drop | Lesson 07 |

**Standard exercise:** everything OFF, then enable only Rows → only Clock → only metal4.

---

## Canvas (center)

| Action | How |
|---|---|
| Fit all | **F** key or View → Fit |
| Zoom | mouse scroll wheel |
| Pan | middle button / space+drag |
| Select instance | click |
| Select net | click wire or Find |
| Measure | Tools → Ruler (if present) |

**Find:** Edit → Find / `select -name "clk*" -type Inst` in the console.

---

## Inspector (right)

After clicking a cell:
- Master name (`DFF_X1`)
- Coordinates
- Pin list

After clicking a via layer: geometry properties.

---

## Charts — Endpoint Slack

After load with `GUI_TIMING=1` (default `open.tcl`):
1. Charts panel on the right
2. Dropdown **Endpoint Slack**
3. Click a negative bar → path highlighted in canvas

View → **Show Worst Path** if Timing menu is visible.

---

## Clock Tree Viewer (lesson 05)

1. View → **Clock Tree Viewer** (or Clock widget)
2. Clock list: `core_clock`
3. Click clock → tree
4. `gui::select_clockviewer_clock` from console if menu is hidden

---

## Tcl console (bottom)

Useful commands to copy:

```tcl
report_checks -max_paths 3
report_clock_skew
gui::fit
select -name "CLKBUF*" -type Inst
gui::clear_selections
```

**Do not** close OpenROAD with `exit` if you are still inspecting: use `gui::hide` only if needed.

---

## Educational sequence (45-minute GUI session)

Follow the timed table in [gui-atlas.md](./gui-atlas.md) §6. In summary:

1. `gui_1_synth.odb` — black canvas (PNG `win_synth.png`)
2. `gui_2_1_floorplan.odb` — die/core (`win_floorplan.png`)
3. `gui_2_4_floorplan_pdn.odb` — power (`03_pdn_labeled.png`)
4. `gui_3_3_place_gp.odb` vs `gui_3_5_place_dp.odb`
5. `gui_4_cts.odb` — `select -name "clk" -type Net`
6. `gui_5_1_grt.odb` vs `gui_5_2_route.odb` (isolate metal2 / metal3)
7. `gui_final` — Inspector `CTS_NDR_0`

For each: 5 minutes, compare with atlas PNG, one line in notebook.

---

## KLayout (GDS, lesson 07)

```bash
klayout results/nangate45/gcd/learn/6_final.gds
```

- F: fit
- Layers panel: enable metal
- If empty: Files → Load layer properties for PDK if available

---

## GUI troubleshooting

| Symptom | Fix |
|---|---|
| Black window | Display Control: Layers ON |
| No timing chart | GUI_TIMING=0; rerun without skipping liberty |
| Crash save_images | ignore; GDS is independent |
| Preview Cursor "not available" | use Desktop, not Preview |
