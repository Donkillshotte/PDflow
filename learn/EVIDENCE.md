# Verification evidence (course)

Updated during autonomous goal work. Does not replace studying: certifies that **materials and the pipeline** exist and run.

## Structure (automatic test)

```bash
./scripts/test_course.sh
```

Expected outcome: `SMOKE PASSED`.

Covers: 8 lessons × (README, LAB, run.sh) with minimum depth, 6 Tcl walkthroughs,
GUI atlas + Qt/canvas/heatmap PNGs, `golden-metrics.md`, workbook + `solutions.md`,
tutorial design, `--list`, `--check`, `--auto --lesson 00`, tool versions.

## ORFS pipeline `learn` variant

Run on the tutorial design (`FLOW_VARIANT=learn`, `CORE_UTILIZATION=35`, SDC 0.46 ns):

- `make synth floorplan place cts route finish` → exit 0
- Artifact: `flow/results/nangate45/gcd/learn/6_final.gds`
- Numbers: [golden-metrics.md](./reference/golden-metrics.md) — finish WNS −0.04,
  `period_min` 0.50 ns (~2.01 GHz) vs SDC 0.46 ns (~2.17 GHz). Exit 0 ≠ closed timing.

## Pixel-level GUI

Qt screenshots in `learn/reference/gui-shots/` plus ORFS heatmaps (`orfs_*.png`: clock tree, worst path, congestion, IR drop).

Guide: `learn/reference/gui-atlas.md` (sections 1–9).

## Enterprise signoff (Phase 1 + Phase 2)

`flowlab` (FlowLab) and `learn` (ORFS course) variants share scripts in `learn/scripts/`.

```bash
# After make finish on the chosen variant
export FLOW_VARIANT=learn   # or flowlab

./learn/scripts/run_signoff_all.sh
SIGNOFF_INCLUDE_PHASE2=1 ./learn/scripts/run_signoff_all.sh   # includes thermal + PKG

# Gate evaluation vs golden-gcd.json
python3 learn/scripts/signoff_eval.py --variant "${FLOW_VARIANT}"
```

Expected reports in `learn/sim/reports/`:

| Report | Pillar |
|---|---|
| `sta_signoff_{v}.json` | Timing |
| `drc_signoff_{v}.json` | Geometry |
| `lvs_signoff_{v}.json` | Equivalence |
| `power_signoff_{v}.json` | Power / PKG |
| `signoff_all_{v}.json` | Orchestrator |
| `thermal_signoff_{v}.json` | Thermal proxy |
| `pkg_signoff_{v}.json` | Packaging |
| `signoff_phase2_{v}.json` | Phase 2 |

Matrix and DoD: [signoff-matrix.md](./reference/signoff-matrix.md).  
Studio UI: FlowLab **finish** stage, hub [/pkg](http://127.0.0.1:43217/pkg), `GET /api/signoff?variant=flowlab`.

Automatic smoke: `./scripts/test_all_phases.sh` (includes signoff hook in `test_studio_api.sh`).

## Visual lab (FlowLab)

The canvas **above the fold** on `/flow` is a lab viewport (wheel zoom, drag pan, Fit/`0`, Full/`F`), not a static `<img>`:

| Stage | What you see |
|---|---|
| Floorplan / PDN | Die + VDD/VSS straps (`03_pdn*.png`) |
| Place | Cells on rows + PDN (`05_place_dp.png`) · Place↔Route compare |
| Route | M2/M3 metal «spaghetti» (`08_route_labeled.png`) · GRT↔DRT wipe · M2/M3 only |
| Finish | Final layout (`09_final.png`) |

Filmstrip of related gui-shots + Display Control HUD (Nangate45 colors). OpenROAD Web Viewer is **opt-in**. Synth has no die: explicit message.

### `learn` run evidence (2026-08-28)

After `6_final.*` present in `flow/results/.../gcd/learn/`:

```bash
FLOW_VARIANT=learn SIGNOFF_INCLUDE_PHASE2=1 ./learn/scripts/run_signoff_all.sh
```

| Pillar | Result | Summary |
|---|---|---|
| Timing | **PASS** | WNS −0.02 ns · TNS −0.14 · viol 3 |
| Geometry | **PASS** | Route DRC 0 · GDS DRC 0 |
| Equivalence | **PASS** | LVS PASS · errors 0 |
| Power | **PASS** | Chip IR 6.34 mV · Sys droop 10.16 mV |
| Thermal proxy | **FAIL** (educational) | 62.86 mV > 50 mV threshold — interpret as proxy |
| PKG | **PASS** | bump + RDL + system_pdn ok |

Report: `learn/sim/reports/signoff_all_learn.json`. Phase 1 complete; thermal proxy flags elevated transient droop on the learn run (educational value).

## Studio UI (graphical wrapper)

```bash
./scripts/run_studio.sh
# http://127.0.0.1:43217
```

Smoke: `== Studio UI ==` section in `./scripts/test_course.sh` (Next.js build).
Verified APIs: `/api/toolchain`, `/api/lessons`, `/api/run` action `check`.

## Goal requirements audit

See [AUDIT.md](./AUDIT.md).

## What remains for the student (not a repo gap)

- Compile `my-notebook.md` and `my-final-project.md`
- sky130 track: post-course extension in CURRICULUM
