# OpenROAD + OpenSTA — local physical design environment

Three surfaces in the same tree. Do not mix them.

| Surface | What | Entry |
|---|---|---|
| **Product** | Physical knobs, official netlist, fixed die, real finish | [docs/README.md](docs/README.md) |
| **Lab** | e-graph, rewrite, IR F4, refine | [learn/dse/README.md](learn/dse/README.md) |
| **Course / Studio** | RTL→GDS lessons, FlowLab | [learn/README.md](learn/README.md) |

Product win (slack ±5 ps, area/power/leakage/IR ±10%):
[`learn/dse/win_rule.py`](learn/dse/win_rule.py).
How to cook and test: [`docs/operations.md`](docs/operations.md).
Honest results: [`docs/results.md`](docs/results.md).
Agent rules: [`AGENTS.md`](AGENTS.md).
Tree and ownership: [`docs/architecture.md`](docs/architecture.md).
How to contribute: [`CONTRIBUTING.md`](CONTRIBUTING.md).

Complete local environment for digital physical design (RTL → GDSII) based on:

| Tool | Version | Source |
| --- | --- | --- |
| [OpenROAD](https://github.com/The-OpenROAD-Project/OpenROAD) | 26Q2 (Precision Innovations binaries) | `.deb` package from [VaultLink](https://vaultlink.precisioninno.com/) |
| [OpenSTA](https://github.com/parallaxsw/OpenSTA) | 3.1.0 | built from source (with CUDD) |
| [OpenROAD-flow-scripts](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts) (ORFS) | 26Q2 | tag matching OpenROAD |
| [yosys](https://github.com/YosysHQ/yosys) | submodule pinned from ORFS | built from source (CMake) |
| [KLayout](https://www.klayout.de/) | 0.30.11 | official `.deb` package |

**Yosys** (0.63, ORFS) · **KLayout** (0.30.11) · OpenSTA · ngspice · **vyges-em-ir** (v0.1.33) · **dynamic IR I(t)**. OSS matrix (Magic/Netgen/EQY/sby/Xyce/OpenRCX/FasterCap/Raphael/StarRC/open_pdks): [learn/reference/oss-integrations.md](learn/reference/oss-integrations.md). Vectorless/dynamic: [learn/reference/vectorless-power.md](learn/reference/vectorless-power.md). IR engine: [learn/reference/vyges-em-ir.md](learn/reference/vyges-em-ir.md). Heatmap I(t): [learn/reference/dynamic-ir.md](learn/reference/dynamic-ir.md).

Tested on **Ubuntu 24.04** (also works on 22.04).

## Installation

Cloud Agent (default **core**, without standalone OpenSTA or DSE/AES/Krylov):

```bash
PD_FLOW_PROFILE=core EDA_JOBS=2 bash scripts/cloud_agent_install.sh
./scripts/cloud_agent_smoke.sh          # versions only
./scripts/test_cloud_bootstrap.sh       # static checks
```

Profiles: `core` (RTL→GDS + Studio) · `analysis` (+ `libdpn` / synthetic `dpn_test`) · `full` (+ OpenSTA from source).
AES, PDN mesh with more than 20k R, and Krylov require `ALLOW_HEAVY_ANALYSIS=1`.
Crash-resilient log: [`.cursor/SETUP_LOG.md`](.cursor/SETUP_LOG.md).

Locally, run scripts in order (they require `sudo` for apt packages):

```bash
./scripts/01_install_openroad.sh   # OpenROAD from prebuilt binaries
./scripts/02_install_opensta.sh    # CUDD + OpenSTA from source
./scripts/03_install_klayout.sh    # KLayout (for final GDS)
./scripts/04_setup_orfs.sh         # clone ORFS + build yosys
```

The ORFS script derives the quarterly tag automatically from the installed
OpenROAD version (for example `26Q2-...` → `26Q2`), so tools and flow stay
aligned. The tag can be overridden with `ORFS_TAG=...`.

Everything built or cloned ends up in `tools/` (ignored by git):

```
tools/
├── OpenROAD-flow-scripts/   # ORFS: flow, PDK (nangate45, sky130, asap7...), example designs
├── src/                     # OpenSTA and CUDD sources
├── cudd/                    # CUDD install (BDD library)
├── opensta/                 # OpenSTA install  → symlink /usr/local/bin/sta
├── yosys/                   # yosys install    → symlink /usr/local/bin/yosys
└── vyges-em-ir/             # Apache-2.0 binary (fetch from GitHub Releases, v0.1.33)
```

`openroad` and `klayout` are installed system-wide from `.deb` packages.

## Quick verification

```bash
openroad -version        # 26Q2-1164-g08f67ee5ec
sta -version             # 3.1.0
yosys -V
klayout -v

# OpenSTA smoke test: min/max timing on a small Nangate45 design
./scripts/run_opensta_example.sh
```

## Hands-on Physical Design course (recommended for learning)

Guided path **phase by phase** (constraints → synth → floorplan → place → CTS → route → GDS)
with theory, 60–120 min LABs, Tcl walkthroughs, workbook, and GUI.
Estimated active study time: **20–28 hours** (the `--auto` wrapper does not replace study).

### Graphical UI (Studio)

```bash
./scripts/run_studio.sh
# open http://127.0.0.1:43217
```

Enterprise web UI: lessons with completion gates, SSE console
(confirm/cancel/retry/export), ops dashboard, **suite hub** (`/api/suite`),
**FlowLab** (`/flow`: editable RTL → parameters → GDSII),
**Ctrl+K** (dashboard / run / OpenROAD Qt / web viewer), materials.
OSS analysis actions: `vectorless`, `vyges_em_ir`, `dynamic_ir`, `yosys_equiv`, `formal_gcd`, `openrcx_report`, `analytical_pex`, `tool_matrix`.
Native solvers: `engine/` (`libdpn.so`, LU + SA-AMG). Build: `./learn/scripts/build_dpn_engine.sh`.
Details: [studio/README.md](studio/README.md) (FlowLab, API, troubleshooting).
Smoke: `./scripts/test_all_phases.sh` (exhaustive), `./scripts/test_studio_api.sh`, `./scripts/test_course.sh`.

### FlowLab — RTL → GDSII lab

Interactive workbench at **http://127.0.0.1:43217/flow**:

- Verilog editor (Monaco), live ORFS parameters, visual 7-phase pipeline
- Isolated `flowlab` variant (does not overwrite course `learn`)
- Signoff finish: gridcheck, activity, DRC · download VCD post sim

Screenshot: `studio/docs/images/flowlab/`

Physical-aware DSE (architecture → ABC chip/cone dpath → F2-fast/GPL/GRT+SDF → STA F3 → extract PDN → static/dynamic/EM IR F4):
`FLOW_VARIANT=flowlab ./learn/scripts/run_dse.sh` · [learn/reference/dse.md](learn/reference/dse.md).
GCD Dynamic IR gold stays **45.298 mV** (Solver A); DSE ingests it, does not restamp it.
Candidate extract is `write_pg_spice` after legalized place — not the finish mesh.
F1 chip is flatten-first (teacher 409.108 µm²); with IR focus on `dpath`, ABC is cone-local. GRT annotates SDF, not SPEF.

### CLI (unchanged)

```bash
./scripts/learn_physical_design.sh --check    # verify prerequisites
./scripts/learn_physical_design.sh --list     # index of 8 lessons
./scripts/learn_physical_design.sh --deep --lesson 01-constraints
./scripts/learn_physical_design.sh --resume   # resume progress
./scripts/test_course.sh                     # smoke test structure + lesson 00
```

Documentation: [learn/README.md](learn/README.md) and [learn/CURRICULUM.md](learn/CURRICULUM.md).
Extended flow (RTL sim, activity, DRC, gridcheck, bump/RDL, thermal):
[learn/reference/extended-flow.md](learn/reference/extended-flow.md).
GUI atlas (Qt screenshots): [learn/reference/gui-atlas.md](learn/reference/gui-atlas.md).
Tutorial run metrics: [learn/reference/golden-metrics.md](learn/reference/golden-metrics.md).
Pipeline verification: [learn/EVIDENCE.md](learn/EVIDENCE.md). Requirements audit: [learn/AUDIT.md](learn/AUDIT.md).

For the GUI, use the **Desktop** button on [cursor.com/agents](https://cursor.com/agents) (not Preview cards).

## Full RTL → GDS flow (example design `gcd`)

```bash
./scripts/run_gcd_flow.sh
```

Runs the full ORFS flow on design `gcd` with open PDK **Nangate45**:
synthesis (yosys) → floorplan → placement → clock tree synthesis → routing →
finishing (GDSII via KLayout). Output in
`tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/`:

The launcher uses 35% core utilization to leave room for timing repair
required by the aggressive 0.46 ns constraint in the 26Q2 example. Override with
`CORE_UTILIZATION=45`, for example.

- `6_final.gds` — final layout
- `6_final.odb` / `6_final.def` — final database and DEF
- timing/area/power reports in `flow/reports/nangate45/gcd/`

For other designs or PDKs:

```bash
DESIGN_CONFIG=./designs/sky130hd/gcd/config.mk ./scripts/run_gcd_flow.sh
```

To open the result in the OpenROAD GUI (requires display/X11):

```bash
./scripts/run_gcd_flow.sh gui_final
```

## Interactive use

```bash
# OpenROAD Tcl shell
openroad

# OpenSTA shell
sta
```

## Notes

- Precision Innovations OpenROAD binaries already include OpenSTA internally
  (`report_checks`, `report_wns`, etc.); standalone OpenSTA install is for using
  STA alone, outside the flow.
- Launcher `run_gcd_flow.sh` passes `openroad`, `sta`, and `yosys` paths found in
  `PATH` to ORFS. Outside a Nix environment, ORFS otherwise looks for binaries in
  its own `tools/install` directory.
- Setup script installs `tcl-dev`: yosys Tcl integration is
  required because ORFS runs synthesis scripts with the `-c` option.
- OpenROAD GUI (`openroad -gui`) requires Qt/X11: in headless environments
  use `Xvfb` or work from the command line.

## ORFS troubleshooting

| Problem | Fix |
|---|---|
| Missing `1_synth.odb` | `make synth` or FlowLab Synthesis phase |
| Floorplan 412 in Studio | Run synth first; verify `results/.../learn/` |
| Timing fail @ 0.46 ns | Normal on aggressive GCD tutorial; use relaxed SDC in FlowLab |
| Lock `.studio-run.lock` | `./scripts/test_studio_api.sh` cleans it; or remove manually if stale |
| ORFS tag mismatch | `ORFS_TAG` aligned to `openroad -version` (26Q2) |
