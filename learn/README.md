# Physical Design Course — OpenROAD + ORFS

This is the **course**. The product (knobs, fixed die, finish, `win_rule`)
lives in [`docs/README.md`](../docs/README.md). Study guide: [`docs/course.md`](../docs/course.md).

Course path for digital physical design on Nangate45 / FreePDK45.
About **20–28 hours** of LAB + reference + workbook + GUI. The `--auto`
wrapper verifies tools; it does not replace studying.

## Content levels

| Level | What | Indicative time |
|---|---|---|
| `run.sh` | Quick interactive guide per stage | ~30–45 min/lesson |
| `LAB.md` | Extended lab with measurable exercises | ~60–120 min/lesson |
| `reference/` | Glossary, debug, Tcl walkthroughs, **golden-metrics** | ~3–4 hours total |
| `workbook/` | Exercises with solutions and notebook | ~3–4 hours total |

**Recommended mode:** `./scripts/learn_physical_design.sh --deep --lesson 01`

## Quick start

```bash
# Web UI (recommended)
./scripts/run_studio.sh
# → http://127.0.0.1:43217

# Verify toolchain (CLI)
./scripts/learn_physical_design.sh --check

# Lesson index
./scripts/learn_physical_design.sh --list

# One lesson (interactive, with pauses)
./scripts/learn_physical_design.sh --lesson 03-floorplan

# Deep mode (reads LAB.md, more pauses)
./scripts/learn_physical_design.sh --deep --lesson 03-floorplan

# Full path
./scripts/learn_physical_design.sh --deep --all

# Resume where you left off
./scripts/learn_physical_design.sh --resume

# Automatic mode (no pauses — useful for tests)
./scripts/learn_physical_design.sh --auto --lesson 00
```

The web **Studio** (`studio/`) exposes lessons, materials, and ORFS actions without
having to remember `make` one-liners. The CLI remains available and unchanged.

## Structure

```
learn/
├── README.md              ← this file
├── CURRICULUM.md          ← detailed syllabus
├── EVIDENCE.md            ← pipeline verification + smoke
├── lib/                   ← ui, orfs, progress, validate
├── reference/             ← glossary, debug, Tcl walkthroughs, GUI atlas
│   └── gui-shots/         ← Qt PNGs + OpenROAD canvas
├── workbook/              ← exercises, quiz, final project
├── designs/               ← tutorial design config and SDC
└── lessons/
    ├── 00-intro/
    │   ├── README.md      ← theory
    │   ├── LAB.md         ← 60–120 min lab
    │   └── run.sh         ← quick interactive guide
    ...
```

## Tutorial design

- **RTL**: `gcd.v` (Greatest Common Divisor, ~250 cells)
- **PDK**: Nangate45 (open)
- **Flow variant**: `FLOW_VARIANT=learn` → results in `results/.../gcd/learn/` (does not touch `base` runs)

## After lessons 00–07: power & SPICE

**Recommended** module (not required to complete the course):

1. Read [`reference/spice-power-chain.md`](reference/spice-power-chain.md) — exhaustive map lessons ↔ FlowLab ↔ netlists
2. Open FlowLab [RTL → finish](http://127.0.0.1:43217/flow) (`signoff_all` on finish). System PDN is [/pkg](http://127.0.0.1:43217/pkg)
3. Post-`make finish`: `./learn/scripts/run_power_chain.sh` (`learn` or `flowlab` variant)
4. Explore netlists in `learn/sim/spice/` · hub [/pkg](http://127.0.0.1:43217/pkg)

Each lesson README has a **«Power & SPICE chain»** section with a link to the corresponding section.

## Two study modes

| Mode | Tools |
|---|---|
| **Files** | `config.mk`, `constraint.sdc`, logs, reports, ORFS Makefile |
| **GUI** | `gui_*` targets, OpenROAD Qt, KLayout for GDS |

### Opening the GUI

Use the **Desktop** button on the Cursor agent page ([cursor.com/agents](https://cursor.com/agents)).
**Preview** cards in chat do not work for Qt/VNC applications.

Pixel-level guide (real Qt screenshots, anatomy A–G, synth→GDS gallery):
[learn/reference/gui-atlas.md](./reference/gui-atlas.md).

DSE (proposer only; e-graph datapath + ABC + Dynamic IR oracle): [dse.md](./reference/dse.md) · `./learn/scripts/run_dse.sh`. DSE does not run `signoff_all`.

Tutorial run metrics (WNS, `period_min`, area, DRC): [golden-metrics.md](./reference/golden-metrics.md).  
Four-pillar signoff matrix (STA/DRC/LVS/power): [signoff-matrix.md](./reference/signoff-matrix.md) · thresholds in [`signoff/golden-gcd.json`](./signoff/golden-gcd.json).  
Definition of Done per pillar: script + JSON report + golden gate + test + doc (see checklist in signoff-matrix).  
A green `make finish` **does not** mean 2.17 GHz closed: at signoff `period_min` is ~0.50 ns (~2.01 GHz).

Then, on the remote desktop:

```bash
cd /workspace/tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_3_place.odb
```

## Progress

The file `learn/.progress.json` tracks completed lessons.

```bash
./scripts/learn_physical_design.sh --status
```

## Syllabus (summary)

| # | Lesson | Duration | Key output |
|---|---|---|---|
| 00 | Introduction | 45–60 min | RTL→GDS map, smoke synth |
| 01 | Constraints | 60–90 min | SDC, config.mk, clock effect |
| 02 | Synthesis | 45–75 min | `1_2_yosys.v`, `1_synth.odb` |
| 03 | Floorplan | 60–90 min | die/core, PDN |
| 04 | Placement | 75–90 min | global/dp, resizer |
| 05 | CTS | 60–90 min | clock tree, skew |
| 06 | Routing | 75–90 min | guide, DRC, wire |
| 07 | Finish | 60–90 min | GDS, SPEF, signoff; fmax vs SDC |

Full detail: [CURRICULUM.md](./CURRICULUM.md)

## After the course

The course stays on Nangate45 / FreePDK45. Do not mix sky130 into these lessons.

1. Bring your Verilog into `flow/designs/src/`
2. Read and edit `flow/scripts/*.tcl` one command at a time
3. Use `make help` in `flow/` for all GUI targets

sky130 (`DESIGN_CONFIG=./designs/sky130hd/gcd/config.mk`) is a different PDK. It is a post-course experiment, not a course step. See [`reference/gaps.md`](./reference/gaps.md).

## Notes

- Exercises with a **very tight** clock may fail at CTS: this is intentional for learning debug (**DPL-0038**). **RSZ-0062** on the default run is a timing warning, not that crash.
- Use `clean_*` to redo a stage without starting from scratch.
- Consult [golden-metrics.md](./reference/golden-metrics.md) before shouting at the bug.
- Consult the [ORFS documentation](https://openroad-flow-scripts.readthedocs.io/) to go deeper.
