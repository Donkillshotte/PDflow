# OpenROAD GUI atlas — pixel-level guide (Qt 26Q2)

These are not invented icons: every PNG in `gui-shots/` is a **real capture** of the OpenROAD Qt GUI (`26Q2-1164-g08f67ee5ec`) on the tutorial design `nangate45/gcd` variant `learn`, or a `save_image` of the canvas from the same ODB.

**How to open the GUI:** **Desktop** button on [cursor.com/agents](https://cursor.com/agents) (not Preview chat). Then:

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_final
```

Expected title: `OpenROAD - gcd` (or `OpenROAD - nangate45/gcd/learn - 6_final`).

Menu/panel reference in prose: [gui-openroad.md](./gui-openroad.md). This atlas is the **visual map**.

**FlowLab / lessons (browser):** on `/flow` and in wizard **Results** step, the central canvas shows the same layouts via ORFS PNG + **OpenROAD Web Viewer** embedded (`POST /api/viewer`). You do not need to open Qt for a first inspection — use Desktop for pixel-level analysis as in this atlas.

---

## 1. Window anatomy (learn these 7 rectangles)

Reference window: **1680×1000** pixels (maximize yours to a similar size).

![Labeled anatomy](./gui-shots/win_anatomy_labeled.png)

| Zone | Where to click (1680×1000) | What it does |
|---|---|---|
| **A Menu** | `y ≈ 8–24`, `Files` at `x≈30`, `View` at `x≈80`, `Tools` at `x≈150` | Files→Load ODB, View→fit/heatmap, Tools→ruler |
| **B Toolbar** | `y ≈ 32–52`: **Fit** `x≈40`, **Find** `x≈95`, **Inspect** `x≈155`, **Timing** `x≈230` | Shortcuts; Fit ≡ `F` key ≡ `gui::fit` |
| **C Display Control** | left column `x=0–268`, `y=56–760` | Eye = visible; pointer = selectable |
| **D Canvas** | `x=268–1390`, `y=56–760` | Layout; scroll wheel zoom, middle button pan, click selects |
| **E Inspector** | right column `x=1390–1680` | Properties of the selected object |
| **F Console** | `y≈760–972` | Log + **TCL commands** field at bottom |
| **G Status** | last line `Idle` | If not Idle, wait before clicking |

**90-second exercise:** open `gui_final`, identify A–G **without** rereading the table. Then compare with the screenshot.

![Full window on 6_final.odb](./gui-shots/win_anatomy.png)

---

## 2. Display Control — Nangate45 layer colors

Crop of left panel in the same session:

![Display Control](./gui-shots/win_display_control_crop.png)

In the 26Q2 build the **swatches** (color squares) match the canvas:

| Layer | Color in GUI | What it usually represents on GCD |
|---|---|---|
| `metal1` | blue | VDD/VSS rails on **rows** (followpin) + local pins |
| `metal2` | red | horizontal/vertical signal routing |
| `metal3` | green | signal routing (opposite direction to M2) |
| `metal4` | yellow/light green | vertical PDN straps (M1–M4–M7 grid) |
| `metal5` | magenta/pink | horizontal PDN straps |
| `via1`… | purple/varied | cuts between adjacent metals |

Two checkboxes per row:

1. **Eye** — visible in canvas
2. **Pointer** — clickable/selectable

### Click path: turn everything off, re-enable only M2+M3

1. In **C**, scroll the list `Layers`.
2. Turn off the eye on `metal1`, `metal4`–`metal10` and on the vias you do not need.
3. Leave `metal2` (red) and `metal3` (green) on.
4. Toolbar **Fit** (or `F`).

Equivalent Tcl (paste in **TCL commands** field, Enter after each line):

```tcl
gui::set_display_controls "Layers/*" visible true
gui::set_display_controls "Layers/metal1" visible false
gui::set_display_controls "Layers/metal4" visible false
gui::set_display_controls "Layers/metal5" visible false
gui::fit
```

Expected result (red + green wires, PDN pink/green off):

![Only metal2 and metal3](./gui-shots/win_layers_m2m3.png)

In the console below see exactly the `gui::set_display_controls` run: is the right way to **document** a view in the notebook.

### Nets vs Layers

- **Layers** = geometry (all metal, including power).
- **Nets/Signal** and **Nets/Clock** = which *nets* to highlight/filter.

Hiding `Nets/Signal` **does not** remove wires if layers stay on: wires *are* layer geometry. To isolate the clock: select the net (section 4) or turn off layers and use Highlight.

Clock filter attempt (layers still ON → canvas stays full; console confirms commands):

![Nets/Clock filter with layers still visible](./gui-shots/win_clock_filter.png)

**Lesson:** if you want “clock only”, combine `select -name "clk" -type Net` (yellow highlight) *or* turn off signal metals.

---

## 3. Tcl console — where to write, what works

The field is the white row in **F**, label **TCL commands**, about `x=80–900`, `y ≈ H−50` (on 1000px: `y≈950`).

Click in the row → type → **Enter**. History appears above.

Commands verified on this GUI:

| Command | Visual effect |
|---|---|
| `gui::fit` | die fills **D** |
| `select -name "clk" -type Net` | clock net highlighted; Inspector populates |
| `select -name "clkbuf*" -type Inst` | CTS buffers |
| `gui::clear_selections` | removes highlight |
| `gui::set_display_controls "Layers/metal2" visible false` | turns off M2 |

**Do not** use (error seen in session):

```tcl
report_checks -path_delay max -max_paths 3
```

OpenSTA in this build responds `sta_error 563 ... is not a known keyword`. Use instead:

```tcl
report_checks -max_paths 3
```

Screenshot of the error (so you recognize it):

![Wrong STA command in console](./gui-shots/win_report_checks.png)

---

## 4. Inspector — inspect net `clk`

After `select -name "clk" -type Net` the panel **E** shows real properties of GCD post-route:

![Inspector on the net clk](./gui-shots/win_inspector_tab.png)

What you **must** know how to read (typical values on GCD `learn`):

| Inspector field | Expected value | Why it matters |
|---|---|---|
| Type | `Net` | you did not click a cell |
| Name | `clk` | module clock port |
| Signal type | `CLOCK` | CTS classified the net |
| Wire type | `ROUTED` | detailed route passed |
| Non-default rule | `CTS_NDR_0` | clock with wider rule/spacing |
| ITerm | `clkbuf_0_clk/A` | first buffer of the tree |
| BTerm | `clk` | pin on block edge |
| BBox | ~`(4.5, 0) … (19.8, 23.5)` µm | physical extent of clock |

If Inspector is empty: nothing is selected, or you are on **Help Browser** tab. Click **Inspector** tab at bottom right of panel E (above console).

Toolbar **Inspect** after a selection forces Inspector tab.

---

## 5. Gallery by stage (same GUI, different ODBs)

Each row: **Qt window** + (where available) **canvas `save_image`**. Open `gui_*` in the same order.

### 5.1 Synthesis — `1_synth.odb`

Canvas **black**. Die 0×0: cells exist in DB but **have no coordinates**. Headless `save_image` often does not write PNG. This is normal, not a crash.

![GUI on 1_synth.odb: empty canvas](./gui-shots/win_synth.png)

Command:

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_1_synth.odb
```

Exercise: **Find** → search for `DFF_X1` → Inspect. Master name visible, position (0,0) or absent.

### 5.2 Floorplan — `2_1_floorplan.odb`

Two concentric rectangles: **die** (outer) and **core** (inner). No cells, no PDN.

![GUI floorplan: die/core only](./gui-shots/win_floorplan.png)

Note: `gui::set_display_controls "Rows" visible true` fails with **`[ERROR GUI-0013]`** — in this GUI there is no control named exactly `Rows`. Search Display Control tree for similar node (often under physical groups) or look at blue lines **after** PDN.

### 5.3 Tapcell — `2_3_floorplan_tapcell.odb`

First physical cell geometries (well tap) on rows.

![Tapcell](./gui-shots/win_tapcell.png)

### 5.4 PDN — `2_4_floorplan_pdn.odb`

Before the “chip view”: M1 rail + strap.

![GUI PDN](./gui-shots/win_pdn.png)

High-resolution canvas (same ODB, layout only):

![Annotated PDN](./gui-shots/03_pdn_labeled.png)

Visual checklist:

- [ ] die edge
- [ ] tight blue lines = followpin M1
- [ ] 3 vertical green straps
- [ ] 3 horizontal pink straps
- [ ] **zero** logic rectangles (yet)

Tcl:

```tcl
gui::set_display_controls "Nets/Signal" visible false
gui::set_display_controls "Nets/Power" visible true
gui::set_display_controls "Nets/Ground" visible true
gui::fit
```

### 5.5 Global placement — `3_3_place_gp.odb`

Sparse cells (blobs), I/O pins as triangles on edge, PDN still underneath.

![GUI global place](./gui-shots/win_place_gp.png)

![Annotated GP canvas](./gui-shots/04_place_gp_labeled.png)

**Cyan** triangles (top/bottom) and **red** (left/right) are **BTerms**.

### 5.6 Detailed placement — `3_5_place_dp.odb`

Same content “legalized” on the rows: rectangles aligned to sites, overlap gone.

![GUI detailed place](./gui-shots/win_place_dp.png)

Open **on the same desktop** GP and DP (two windows, or Files→Load in sequence) and note *one* difference in notebook. Canvas DP:

![Canvas DP](./gui-shots/05_place_dp.png)

### 5.7 CTS — `4_cts.odb`

More cells (`CLKBUF*`). Filter clock as in section 2. Canvas:

![Canvas CTS](./gui-shots/06_cts.png)

![GUI CTS](./gui-shots/win_cts.png)

```tcl
select -name "clkbuf*" -type Inst
```

View → **Clock Tree Viewer** if menu is visible; otherwise stay on highlighted net `clk`.

### 5.8 Global route — `5_1_grt.odb`

Guides (corridors), not yet wire mask-ready.

![GUI GRT](./gui-shots/win_grt.png)

![Canvas GRT](./gui-shots/07_grt.png)

### 5.9 Detailed route — `5_2_route.odb`

Colored spaghetti = DRT geometry. Compare with GRT: here wires are fine and on M2/M3 colors.

![GUI route](./gui-shots/win_route.png)

![Annotated route canvas](./gui-shots/08_route_labeled.png)

Exercise: turn off all layers except `metal2`, Fit, count dominant wire direction by eye. Then only `metal3`.

### 5.10 Finish — `6_final.odb`

Fill + SPEF already extracted. Same dense snapshot as route, more dummy fill.

![GUI final](./gui-shots/win_final.png)

![Canvas final](./gui-shots/09_final.png)

KLayout (GDS, not Qt OpenROAD):

```bash
klayout results/nangate45/gcd/learn/6_final.gds
```

**F** key = fit. Layers panel on right: toggle metal like Display Control.

---

## 6. 45-minute guided session (required before lesson 04)

Time yourself. For each step: 1 mental screenshot + 1 notebook line.

| Min | ODB | Pixel action | Write in notebook |
|---|---|---|---|
| 0–5 | `1_synth` | note black canvas | “no die” |
| 5–10 | `2_1_floorplan` | identify two rectangles | die vs core |
| 10–18 | `2_4_pdn` | turn off metal2–3, keep M1+strap | rail/strap colors |
| 18–26 | `3_3` vs `3_5` | Fit on both | GP blob vs DP aligned |
| 26–32 | `4_cts` | `select clk` + Inspector | Signal type CLOCK |
| 32–40 | `5_1` vs `5_2` | M2 only then M3 on route | guide vs wire |
| 40–45 | `6_final` | Find `FILLCELL` if present | fill ≠ logic |

---

## 7. Shortcuts to memorize

| Key / click | Action |
|---|---|
| `F` / toolbar **Fit** | frame the die |
| scroll wheel | zoom on pointer |
| middle button / Space+drag | pan |
| click cell or wire | selection → Inspector |
| TCL field at bottom | `gui::` and `select` commands |
| eye in Display Control | hide/show layer |

---

## 8. Heatmap and Clock Tree Viewer (ORFS `save_images`)

Beyond the Qt window, ORFS 26Q2 in `make finish` writes PNG in `reports/nangate45/gcd/learn/*.webp.png`. Teaching copies in `gui-shots/orfs_*.png`.

### Clock tree (`orfs_cts_clock_tree.png`)

This is the **Clock Tree Viewer**: Y axis = time (ns), triangles = buffers, squares = sink FFs.

On GCD `learn`: root → one buffer → fanout ~4 → leaves around **0.07 ns**. Aligned leaves = small skew (report setup skew ~0).

Use this PNG if View → Clock Tree Viewer does not open from menu.

### Worst path (`orfs_final_worst_path.png`)

Overlay on die: **launch** cyan, **signal** red, **inst** purple. It is View → Show Worst Path / Timing, already computed at signoff.

### Congestion (`orfs_final_congestion.png`)

gcell grid: green = empty, red = full. Hot center, cold edges: same blob as placement.

### IR drop (`orfs_final_ir_drop.png`)

Scale in **mV** (on the GCD ~0–5 mV). If it were hundreds of mV, lesson 03 PDN is insufficient.

These four images close the 45-minute session: after `gui_final`, compare ORFS PNGs with the canvas.

---

## 9. Recapturing screenshots (maintainer)

```bash
# Canvas save_image (headless): 03–09. Synth/floorplan may fail (die 0 / GUI-0078).
./learn/scripts/capture_gui_shots.sh

# Real Qt window (you need DISPLAY=:1 and a desktop):
python3 ./learn/scripts/capture_qt_gallery.py
python3 ./learn/scripts/annotate_gui_shots.py
# Heatmap/clock: copy reports/nangate45/gcd/learn/*.webp.png → gui-shots/orfs_*.png
```

Do not delete PNGs with glob `*_pdn.png`: would also delete `03_pdn.png`.
