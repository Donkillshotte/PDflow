# LAB 07 — Finish, signoff, and final project (90–120 minutes)

Finish is the **contract** with STA, LVS, and (in a company) the foundry. A green `make finish` without a metrics table does **not** complete the course.

## Measurable objectives

- [ ] Listed deliverables and who they are for
- [ ] Compared WNS across at least 3 estimates (place / CTS / finish)
- [ ] Opened GDS in KLayout (or described from file size + layers if KLayout is missing)
- [ ] Completed `my-final-project.md` (not empty)

---

## Part 1 — File inventory (20 min)

```bash
ls -lh tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.*
```

Fill in **before** opening the files:

| Files | Recipient | What happens if missing |
|---|---|---|
| `6_final.gds` | mask / viewer | you have no fab geometry |
| `6_final.def` | ECO / third-party tools | no textual coordinates |
| `6_final.v` | LVS / sim | post-fill netlist differs from synth |
| `6_final.spef` | STA signoff | stay on estimates |
| `6_final.sdc` | STA | constraints not aligned with netlist |
| `6_finish.rpt` | you | you do not know if timing is closed |

Open `learn/reference/walkthrough-finish.tcl.md` and `file-formats.md` SPEF/GDS/DEF sections.

Count components in DEF:

```bash
rg -c '^- ' tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.def | head
rg -n '^COMPONENTS' -A2 tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.def | head
```

Diff synth vs final netlist (buffer/fill names):

```bash
wc -l tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/1_2_yosys.v \
      tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.v
rg -c 'FILLCELL|clkbuf|rebuffer' \
  tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.v
```

Fill does **not** change function: it changes process density and parasitics slightly.

---

## Part 2 — Run finish if missing (15 min)

```bash
./scripts/learn_physical_design.sh --lesson 07
```

If `save_images.tcl` prints a GUI error in the log: **ignore it** if `6_final.gds` exists. The course pins ORFS 26Q2 specifically to avoid `STA-2204` crashes on master save_images.

---

## Part 3 — Four WNS estimates (25 min)

Extract and put in a table (final project §2):

```bash
rg -n 'WNS|TNS|worst' \
  tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/3_resizer.rpt \
  tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/4_cts_final.rpt \
  tools/OpenROAD-flow-scripts/flow/reports/nangate45/gcd/learn/6_finish.rpt \
  | head -50
```

| Estimate | Files | WNS | TNS |
|---|---|---|---|
| Placement RC | 3_resizer | | |
| CTS | 4_cts_final | | |
| Post-route / SPEF | 6_finish | | |

Question: if finish is **worse** than place, why is that honest? (real wires > placement model)

`period_min` at finish: compare with golden-metrics (**0.50 ns** ~2011 MHz vs SDC 0.46 ns).
In the final project you must write **explicitly** whether you closed 2.17 GHz (on the golden run: no).

SPEF: `head -30 results/.../6_final.spef` — search for `*SPEF` and `*D_NET`. You do not need to understand every line: you need to know it **is RC**. See `file-formats.md`.

---

## Part 4 — GUI final + atlas (20 min)

```bash
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_final
```

Checklist (`gui-atlas.md` §4 and §5.10):

- [ ] Anatomy A–G recognized
- [ ] `select -name "clk" -type Net` → Inspector: `CLOCK`, `ROUTED`, `CTS_NDR_0`
- [ ] M2/M3 layers isolated as in lesson 06
- [ ] Find `FILLCELL` if `USE_FILL` is on

PNG: `win_anatomy_labeled.png`, `win_inspector_tab.png`, `09_final.png`.

KLayout:

```bash
klayout tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn/6_final.gds
```

F = fit. Turn off all layers, turn one back on. Compare colors with OpenROAD Display Control: they do **not** necessarily match (different palette).

---

## Part 5 — Final project (30–40 min, may overrun)

Copy:

```bash
cp learn/workbook/final-project-template.md learn/workbook/my-final-project.md
```

Fill in **all** sections of the template. Without this file the course is not finished.

Constraints:

- Numbers taken from **your** reports, not invented
- One real error (even “I ran make without FLOW_VARIANT”)
- Three explanations aloud you would give in an exam

---

## Part 6 — SPICE chain (optional, 45–60 min)

After green `make finish`, connect end-to-end power integrity:

- [ ] Read [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-07-finish)
- [ ] In Studio: post-finish signoff → **SPICE Chain** (or CLI):

```bash
FLOW_VARIANT=learn ./learn/scripts/run_power_chain.sh
```

- [ ] Compare heatmap `orfs_final_ir_drop.png` with `pdn_chip_ir_*.json` — different meshes; do not treat the PNG scale as chip IR or gold 45.298 mV
- [ ] Open `learn/sim/spice/` and count R/I in `mesh_stats_*.json`
- [ ] FlowLab [PKG](/flow?phase=pkg) phase: droop and Zmax System PDN

Optional checklist — does not block lesson completion if skipped.

---

## Part 7 — Signoff 4 pillars (30–45 min)

After `finish`, run the four pillars on Studio **finish** (`/flow?phase=finish#signoff`), not PKG:

- [ ] Read [`signoff-matrix.md`](../../reference/signoff-matrix.md) and [`golden-gcd.json`](../../signoff/golden-gcd.json)
- [ ] **STA:** `FLOW_VARIANT=learn ./learn/scripts/run_sta_signoff.sh` — compare WNS/TNS with golden-metrics
- [ ] **STA IR-aware (optional):** `./learn/scripts/run_sta_ir_aware.sh` — per-cell ITerm V scales NLDM gate delay; does not change nominal WNS; not PrimeTime/Tempus
- [ ] **DRC:** `./learn/scripts/run_drc_signoff.sh` — route DRC lines + GDS violations separate in JSON
- [ ] **LVS:** `./learn/scripts/run_klayout_lvs.sh` — match required; read DFF_X2 must-connect leftover (educational FreePDK45)
- [ ] **Power:** `./learn/scripts/run_power_signoff.sh` — activity → chip IR → system → export + IR/droop gate
- [ ] **Orchestrator:** `./learn/scripts/run_signoff_all.sh` — aggregated report `signoff_all_{v}.json`
- [ ] In Studio: PASS/FAIL badge on matrix vs golden; API `GET /api/signoff?variant=learn`

Signoff checklist — educational close. DFF_X2 must-connect leftover stays named. Not foundry signoff. Not required for `--status` if you skip long LVS.

---

## Course pass criteria (not just this lesson)

- [ ] `--status` : lessons 00–07
- [ ] Workbook A2 (SDC sweep) and D1 (DPL-0038) at least sketched
- [ ] Final project not empty
- [ ] You can open the atlas and find PDN vs route without searching the README
