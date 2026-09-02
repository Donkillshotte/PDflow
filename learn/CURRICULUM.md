# Syllabus — Physical Design Course (OpenROAD)

## Course philosophy

Each lesson follows the cycle **Explain → Run → Inspect → Verify → Reflect**:

1. **Explain** — README.md with theory and file references
2. **Run** — `run.sh` launches real ORFS commands
3. **Inspect** — `gui_*` commands and reading logs/reports
4. **Verify** — automatic checkpoints on artifacts
5. **Reflect** — questions and variants (clock, utilization)

The course uses the **GCD** design because:
- Fast execution (minutes, not hours)
- Complex enough for real CTS and routing
- Documented and used upstream by ORFS

---

## Lesson 00 — Introduction

**Learning objectives**
- Orient yourself in ORFS
- Know the per-stage file map
- Run a synth smoke test

**Artifacts**
- `1_synth.odb` (optional)

**Skills gained**
- Know where to find scripts, results, logs, reports
- Distinguish file mode vs GUI mode

---

## Lesson 01 — Constraints

**Learning objectives**
- Read/write SDC
- Understand `create_clock`, I/O delay
- Modify `config.mk`
- Connect SDC → area → CTS (a chain, not silos)

**Exercises**
- A: Analyze default SDC (0.46 ns)
- B: Relaxed clock (2.0 ns) + place
- C: Tight clock (0.25 ns) + debug failure
- D: GUI Endpoint Slack

**Filess touched**
- `constraint.sdc`, `constraint_relaxed.sdc`, `constraint_tight.sdc`
- `config.mk`

**Skills**
- Connect constraints → area → timing closure

---

## Lesson 02 — Synthesis

**Objectives**
- RTL → gate-level
- Read netlist and synth_stat

**Exercises**
- A: `make synth`
- B: Analyze `1_2_yosys.v`
- C: Yosys log
- D: GUI `1_synth.odb`
- E: OpenSTA pre-layout

**Tcl scripts**
- `synth.tcl`, `synth_stdcells.tcl`

---

## Lesson 03 — Floorplan

**Objectives**
- Die, core, rows, sites
- PDN and tapcells

**Exercises**
- A–B: `make floorplan`
- C: Compare utilization 25 vs 45
- D: GUI `2_1` and `2_4`
- E: Metrics from log

**Tcl scripts**
- `floorplan.tcl`, `pdn.tcl`
- `grid_strategy-M1-M4-M7.tcl`

---

## Lesson 04 — Placement

**Objectives**
- Global vs detailed placement
- Resizer and pre-CTS timing

**Exercises**
- A–B: `make place`
- C: Global place + resizer report
- D: GUI gp vs dp
- E: Resizer log

**Tcl scripts**
- `global_place.tcl`, `detail_place.tcl`, `resize.tcl`

---

## Lesson 05 — CTS

**Objectives**
- Clock tree, skew, clock buffers
- Distinguish **RSZ-0062** (timing not repaired) from **DPL-0038** (util > 100%)
- Debug utilization overflow (LAB part 4)

**Exercises**
- A–B: `make cts`
- C: CTS report
- D: Clock Tree Viewer
- E: Tcl `report_clock_skew`

**Tcl scripts**
- `cts.tcl`

---

## Lesson 06 — Routing

**Objectives**
- Global route, detailed route, DRC
- Congestion analysis

**Exercises**
- A–B: `make route`
- C: Guide + DRC report
- D: GUI grt vs route
- E: KLayout guides

**Tcl scripts**
- `global_route.tcl`, `detail_route.tcl`

---

## Lesson 07 — Finish

**Objectives**
- GDS, SPEF (OpenRCX), signoff timing
- Distinguish green `make finish` from **closed timing**
- Deliverables for fab / STA / LVS

**Exercises**
- A–B: `make finish`
- C: `6_finish` report + `period_min` vs SDC 0.46 ns
- D: Deliverables checklist
- E: Final GUI + worst path (`orfs_final_worst_path.png`)
- F: GDS verification
- G: Final project (compare `golden-metrics.md`)

**Exam concept:** on the golden run finish WNS **−0.04**, `period_min` **0.50 ns** (~2.01 GHz).
SDC period 0.46 ns (~2.17 GHz) is **not** closed. **RSZ-0062** at CTS is a timing warning,
not **DPL-0038**.

---

## Quick reference commands

```bash
# Course wrapper
./scripts/learn_physical_design.sh --lesson NN

# ORFS direct (equivalent)
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 <target>

# Useful targets
synth | floorplan | place | cts | route | finish
clean_synth | clean_floorplan | clean_place | clean_cts | clean_route | clean_finish | clean_all
gui_<stem>   # e.g. gui_3_place.odb, gui_final
```

## Estimated total time (active study)

| Component | Hours |
|---|---|
| Lessons 00–07 README | 4–5 |
| LAB.md (8 sessions) | 8–12 |
| Reference + Tcl walkthroughs | 3–4 |
| Workbook + quiz + final project | 3–4 |
| Guided GUI (pixel atlas + 45 min) | 2–3 |
| **Realistic total** | **20–28** |

Atlas: `learn/reference/gui-atlas.md` (PNGs in `gui-shots/`). Without that session lessons 03–07 stay abstract.

Measured tutorial metrics: `learn/reference/golden-metrics.md` (WNS, `period_min`, area, DRC).
Each LAB asks you to copy your **own** numbers next to that table.

The `--auto` wrapper takes minutes: it is **not** the course. The course is LAB + workbook + GUI.

---

## Recommended extensions (post-course)

1. **sky130hd/gcd** — more realistic PDK (finer geometry)
2. **Your own RTL** — counter, UART, small RISC-V
3. **Tcl scripting** — automate clock/utilization sweeps
4. **OpenSTA standalone** — timing analysis outside the flow
5. **KLayout DRC/LVS** — advanced geometric verification

### Optional modules already wired (Studio + scripts)

Full map: [`learn/reference/extended-flow.md`](./reference/extended-flow.md).

| Module | Script / Studio action | Status |
|---|---|---|
| RTL sim (Icarus) + VCD | `learn/scripts/run_rtl_sim.sh` · `rtl_sim` | READY |
| PDN gridcheck | `run_gridcheck.sh` · `gridcheck` · FlowLab PDN stage | READY |
| System PDN (hier) | `run_system_pdn.sh` · FlowLab PKG · ngspice | READY |
| Chip IR mesh | `run_chip_pdn_ir.sh` · write_pg_spice | READY |
| vyges-em-ir | `run_vyges_em_ir.sh` · CG+BE binary | READY |
| Dynamic IR I(t) | `run_dynamic_ir.sh` · A gold + B SA-AMG + heatmap | READY |
| SPICE chain | `run_power_chain.sh` · FlowLab signoff | READY |
| Per-stage chain docs | `spice-power-chain.md` + lab `sim/spice/` | READY |
| Activity → power | `run_activity_power.sh` · `activity_power` | READY (VCD `read_vcd`) |
| Vectorless / dynamic IR | `run_vectorless.sh` · `vectorless` | READY (Najm + Kouroussis) |
| KLayout GDS DRC | `run_klayout_drc.sh` · `klayout_drc` | READY (after finish) |
| Bump / RDL / design package | `/pkg` · Packaging docs | PARTIAL (theory + BUMPS demo) |
| Thermal | no tool in VM | MISSING (theory) |
