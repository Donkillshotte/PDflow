# Completeness audit — OpenROAD course (goal)

**Requirement-by-requirement** verification of the `learn/` tree state.
Run `./scripts/test_course.sh` after every structural change.
This file lists **where** evidence lives; the smoke test is the automatic evidence.

| # | Requirement | Evidence in repo | How to verify |
|---|---|---|---|
| 1 | IT theory + LAB 60–120 min + `run.sh` for lessons 00–07 | `learn/lessons/NN-*/{README.md,LAB.md,run.sh}` (8×3). LAB with timed parts and **full** `make` (`DESIGN_CONFIG` + `FLOW_VARIANT=learn` + `CORE_UTILIZATION`). Wrapper `--deep` reads LAB. | smoke: files + `min_lines`; `rg` must not find `make ...` as a command |
| 2 | Tcl walkthroughs: synth, floorplan, placement, CTS, routing, finish | `learn/reference/walkthrough-{synth,floorplan,global_place,cts,route,finish}.tcl.md` aligned to ORFS 26Q2 | smoke: 6 files; `min_lines` on place/CTS |
| 3 | Pixel-level GUI guides | `gui-atlas.md` + PNGs in `gui-shots/` (Qt window + canvas + overlay + ORFS heatmap). Not just ASCII. | smoke: PNG size + atlas embed |
| 4 | Workbook: exercises, quiz, final project | `workbook/{README,quiz,progetto-finale-template,notes-template,solutions}.md` | smoke: files + GUI quiz + project cites golden-metrics |
| 5 | Debug playbook, glossary, file formats | `debug-playbook.md`, `glossary.md` (RSZ-0062, DPL-0038, period_min, NDR, gcell, OpenRCX, IFP-0028), `file-formats.md` (SPEF header) | smoke: `rg` terms + `*SPEF` |
| 6 | Wrapper smoke test + toolchain | `scripts/test_course.sh` → `SMOKE PASSED` (`--list`, `--check`, `--auto --lesson 00`, tool versions) | this command |
| 7 | README/curriculum aligned with materials | `learn/README.md`, `CURRICULUM.md`, root `README.md` cite atlas, LAB, `learn` variant, `golden-metrics.md`, green finish ≠ 2.17 GHz | smoke: `rg golden-metrics` + `gui-atlas` |
| 8 | Studio web UI (wrapper goal) | `studio/` Next.js + `scripts/run_studio.sh` — lessons, materials, toolchain, `/api/run` | smoke Studio + `http://127.0.0.1:43217` |

## Verification commands

```bash
./scripts/test_course.sh
test -s learn/reference/gui-atlas.md
test -s learn/reference/gui-shots/win_anatomy_labeled.png
test -s learn/reference/golden-metrics.md
test -s learn/workbook/solutions.md
ls learn/lessons/*/LAB.md learn/lessons/*/run.sh
```

## What smoke does **not** replace

- Having **run** an RTL→GDS `learn` pipeline (pipeline in [EVIDENCE.md](./EVIDENCE.md), numbers in [golden-metrics.md](./reference/golden-metrics.md)).
- Having opened the GUI on the Cursor **Desktop** (HTTP Preview does not count).
- Having compiled `mio-quaderno.md` / `mio-progetto-finale.md` (student work).
