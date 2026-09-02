# Extended flow: RTL → sim → synth → PD → power/DRC → packaging (map)

Review of **tool hooks** and how to bring into the treatment (and where already
in the run) the topics: RTL, RTL sim, synthesis, vector activity, DRC, gridcheck,
PDN, bump/RDL/system PDN, thermal.

Status legend:

| Status | Meaning |
|---|---|
| **READY** | In the ORFS/`learn` flow and usable now |
| **PARTIAL** | APIs/tools present; course or wiring incomplete |
| **MISSING** | You need a tool/process outside flat digital Nangate45 scope |

Canonical ORFS command for the course:

```bash
cd tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 <target>
```

---

## 1. Initial RTL — READY

| Where | Detail |
|---|---|
| Source | `tools/OpenROAD-flow-scripts/flow/designs/src/gcd/gcd.v` |
| Course config | `learn/designs/nangate45/gcd-tutorial/config.mk` → `VERILOG_FILES` |
| Treatment | Lesson 00 (find RTL), 02 (netlist vs RTL) |

**Study:** file via materials / path; you do not need a dedicated viewer.

---

## 2. RTL simulation — READY (new slice)

| Component | Path |
|---|---|
| Testbench | `learn/sim/gcd/tb_gcd.v` |
| Runner | `learn/scripts/run_rtl_sim.sh` |
| Tool | **Icarus Verilog** (`iverilog` / `vvp`) |
| Artifacts | `learn/sim/gcd/sim.log`, `gcd.vcd` |

```bash
./learn/scripts/run_rtl_sim.sh
# wait for RTL_SIM_PASS + VCD
```

**Study:** action `rtl_sim` (Tools console).  
**Next educational step:** waves with GTKWave on Desktop; Verilator if you need performance.

---

## 3. Logic synthesis — READY

| Layer | Path / hook |
|---|---|
| Yosys ORFS | `flow/scripts/synth*.tcl` → `1_2_yosys.v`, `synth_stat.txt` |
| Inspect | `GET /api/inspect?stage=synth` (Yosys `stat` + ODB) |
| Lesson | 02-synthesis |

```bash
make … synth
```

---

## 4. Vector activity and vectorless — READY

| Layer | Status |
|---|---|
| OpenSTA | `set_power_activity`, **`read_vcd -scope tb_gcd/dut`**, `report_power` |
| Dynamic | Icarus VCD on names that match the gate netlist (port) |
| Vectorless | global activity 0.5 + Kouroussis envelope (DAC 2003) + Najm \(P_{01}\) |
| Demo | `learn/scripts/run_activity_power.sh` · `run_vectorless.sh` |

```bash
./learn/scripts/run_activity_power.sh
FLOW_VARIANT=flowlab ./learn/scripts/run_vectorless.sh
```

**Study:** actions `activity_power` and `vectorless`. Docs: [vectorless-power.md](./vectorless-power.md).

Do not use `read_power_activities` (deprecated, broken arity in OpenSTA 26Q2).

---

## 5. DRC — READY (unified route + signoff)

| Type | How |
|---|---|
| Detailed-route DRC | `make … route` → `reports/.../5_route_drc.rpt` (L06) |
| **DRC signoff** | `learn/scripts/run_drc_signoff.sh` → route lines + `make drc` → `drc_signoff_{v}.json` |
| KLayout GDS DRC (legacy) | `learn/scripts/run_klayout_drc.sh` → `6_drc.lyrdb` |
| Magic | tech present, **not** in the course path |

```bash
# after finish — unified signoff (preferred)
FLOW_VARIANT=learn ./learn/scripts/run_drc_signoff.sh
```

**Study:** action `drc_signoff` · matrix in FlowLab finish / [`/pkg`](/pkg).  
See [signoff-matrix.md](./signoff-matrix.md).

---

## 5b. STA signoff — READY

| Component | Path |
|---|---|
| Finish report | `reports/.../6_finish.rpt` |
| OpenSTA + SPEF | `run_sta_signoff.sh` |
| Report | `learn/sim/reports/sta_signoff_{v}.json` |
| Gate | vs `learn/signoff/golden-gcd.json` |
| IR-aware overlay | `run_sta_ir_aware.sh` → `sta_ir_aware_{v}.json` (NLDM × ITerm V; does not change WNS) |

**Study:** action `sta_signoff` · `sta_ir_aware` · `GET /api/signoff`.

---

## 5c. LVS signoff — READY (educational)

ORFS: `make lvs` → CDL concat + KLayout LVS → `6_lvs.lvsdb`.

| Component | Path |
|---|---|
| LVS runset | `platforms/nangate45/lvs/FreePDK45.lylvs` (from [FreePDK45_for_KLayout](https://github.com/laurentc2/FreePDK45_for_KLayout)) |
| Wrapper | `learn/scripts/run_klayout_lvs.sh` |
| Parser UI | `learn/scripts/parse_signoff_artifacts.py` |
| Report | `learn/sim/reports/lvs_signoff_{v}.json` |

**Honest note:** on GCD FreePDK45, LVS may not be tapeout-clean; interpret the report.

**Study:** action `klayout_lvs` · artifact matrix in FlowLab finish.

---

## 6. Gridcheck (power grid connectivity) — READY (slice)

ORFS leaves `check_power_grid` **commented** in `pdn.tcl` (CI). On Nangate GCD
`-dont_require_terminals` is often needed.

```bash
./learn/scripts/run_gridcheck.sh pdn     # 2_4_floorplan_pdn.odb
./learn/scripts/run_gridcheck.sh final   # 6_final.odb
```

Expected: `PSM-0040 All shapes on net VDD/VSS are connected`.

**Study:** action `gridcheck` + inspect section.

**IR drop** (different from gridcheck): already in `make … finish` → `analyze_power_grid`
+ heatmap `final_ir_drop` (L07).

---

## 7. PDN (chip-level) — READY

| Item | Path |
|---|---|
| Script | `flow/scripts/pdn.tcl` (`pdngen`) |
| Strategy | `…/gcd/grid_strategy-M1-M4-M7.tcl` |
| Lesson | 03-floorplan |
| GUI | `gui_2_4_floorplan_pdn.odb` / Studio Open GUI |

---

## 8. Bump · RDL · system PDN — PARTIAL (Studio demo)

OpenROAD exposes:

- `assign_io_bump`, `make_io_bump_array`
- `rdl_route`
- `analyze_power_grid -source_type BUMPS|STRAPS|FULL`

**Study (READY demo):**

| Piece | Where |
|---|---|
| Chip PDN gridcheck | FlowLab **PDN** phase · `FLOW_VARIANT=… ./learn/scripts/run_gridcheck.sh` |
| System PDN (VRM→board→pkg→die) | FlowLab **PKG** phase · `system_pdn` · `run_system_pdn.sh` · ngspice |
| Chip IR static+transient (optional) | `run_chip_pdn_ir.sh` · PDNSim + `pdn_transient.py` |
| vyges-em-ir (engine) | `run_vyges_em_ir.sh` · CG + backward Euler |
| Dynamic IR I(t) | `run_dynamic_ir.sh` · PWL per pin + heatmap |
| Packaging hub | [`/pkg`](/pkg) · [spice-power-chain.md](./spice-power-chain.md) · `system-pdn.md` + `pkg-design-package.md` |

**Exhaustive phase-chain guide:** [spice-power-chain.md](./spice-power-chain.md) — maps lessons 00–07 ↔ FlowLab ↔ SPICE.

**Honest limit:** System PDN is an educational *lumped* ladder; Nangate45 GCD has no packaging LEF/tech. Chip IR `BUMPS` uses a synthetic OpenROAD pattern (PSM-0073), not a tapeout-ready package.

**Future extensions:**

1. Lab on an ORFS design with real bump LEF
2. Board SI/PI models outside OpenROAD
3. Thermal (HotSpot / 3D-ICE) — still MISSING

---

## 9. Thermal analysis — PARTIAL (proxy READY)

No native thermal command in OpenROAD 26Q2; no HotSpot ORFS target.

**Course slice (proxy READY):**

| Component | Path |
|---|---|
| Script | `learn/scripts/run_thermal_signoff.sh` |
| Report | `learn/sim/reports/thermal_signoff_{v}.json` |
| Input | chip IR JSON + ORFS heatmap `orfs_final_ir_drop.png` |
| Studio | action `thermal_signoff` · Phase 2 matrix on `/pkg` |

The proxy sums static IR + transient droop as an educational hotspot estimate; 50 mV threshold in the report.

**External open options (not installed):** HotSpot, 3D-ICE.  
**Honest treatment:** “reliability / thermal” chapter with proxy + power map, without pretending tapeout thermal closed-loop.

Power map proxy already available: IR heatmap + `report_power` (activity script).

---

## Studio hooks (console / API)

| Action / API | Topic |
|---|---|
| `rtl_sim` | Icarus RTL sim |
| `gridcheck` | `check_power_grid` |
| `system_pdn` | ngspice System PDN · VRM→board→pkg→die |
| `chip_pdn_ir` | PDNSim + write_pg_spice + pdn_transient |
| `vyges_em_ir` | vyges-em-ir binary on `.pdn` from the same mesh |
| `dynamic_ir` | PWL per ITerm + A LU + B SA-AMG + C Krylov MOR + D RAS |
| `power_chain` | activity → chip IR → system → lab export |
| `activity_power` | `read_vcd` / `set_power_activity` + `report_power` |
| `vectorless` | Vectorless vs dynamic IR (Najm + Kouroussis) |
| `yosys_equiv` | Yosys equiv RTL↔synth (EQY-class) |
| `formal_gcd` | Yosys sat tempinduct (sby-class) |
| `openrcx_report` | OpenRCX SPEF counts |
| `analytical_pex` | Sakurai–Tamaru + FDM 2D (FasterCap-class) |
| `layout_tools` | Magic / Netgen / KLayout probe |
| `tool_matrix` | OSS orchestrator |
| `klayout_drc` | GDS DRC (legacy, GDS only) |
| `sta_signoff` | STA vs golden-metrics |
| `sta_ir_aware` | Educational IR-aware STA (NLDM × ITerm V) |
| `drc_signoff` | Route DRC + unified KLayout GDS |
| `klayout_lvs` | LVS GDS vs CDL |
| `power_signoff` | Power chain + golden gate |
| `signoff_all` | Four-pillar orchestrator (+ optional Phase 2: `SIGNOFF_INCLUDE_PHASE2=1`) |
| `signoff_phase2` | Thermal proxy + PKG orchestrator |
| `thermal_signoff` | IR+droop hotspot proxy |
| `pkg_signoff` | Bump + educational RDL + system PDN |
| `/api/signoff` | Signoff matrix + gate |
| `/api/inspect` | ODB / STA / Yosys (+ hook notes) |
| `/api/viewer` | OpenROAD `-web` |
| `/api/open` | Qt GUI / KLayout |
| phases `synth`…`finish` | classic PD |

Low-level hook documentation: [tool-hooks.md](./tool-hooks.md).

---

## Suggested educational plan (extension)

| Module | When | Estimated study hours |
|---|---|---|
| RTL + sim + VCD | between L00 and L02 | 1–2 h |
| Yosys deep dive | L02 | already covered |
| Activity → power | after L07 | 1 h |
| Vectorless / dynamic IR | after L07 + VCD | 1 h |
| Gridcheck + IR | L03 + L07 | 0.5–1 h |
| KLayout DRC | after finish | 0.5–1 h |
| Bump/RDL/system PDN | advanced elective | 2–3 h theory |
| Thermal | elective / reading | 1 h theory |

Do not lengthen the required 00–07 course: the new scripts are **optional
modules** callable from Studio and from this map.
