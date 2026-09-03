# Closing labeled GAPs without mocks

Research note (tree + public sources). Not a product win plan.
Do not restamp gold Dynamic IR 45.298. Do not mix product and lab.
Do not treat a dummy LEF, a proxy °C, or a synthetic CCS table as tapeout.

Course progress `0/8` is student work, not a tool GAP.

| GAP | Closable without a mock? | Honest leftover if we do the work |
|---|---|---|
| Gate VCD name-join | **Yes** — gate-level sim | Functional GLS, not SDF sign-off |
| `rdl_route` | **Yes, educational** — OpenROAD dummy pad/bump LEF | Dummy bump, not C4 tapeout |
| HotSpot / compact thermal | **Yes, architecture-level** | Not Ansys/COMSOL, not foundry |
| Xyce | **Yes, env install** | Dual-solver gold; ngspice already covers GCD PDN |
| Nangate CCS tables | **No from the public lib** | Interpolator already real; tables are the missing IP |
| LVS netlist match | **Maybe** — CDL vs GDS cell set | FreePDK45 tutorial is often not LVS-clean |
| Raphael / StarRC | **No** — commercial | OpenRCX + analytical PEX stay the OSS path |
| Magic / Netgen on Nangate | **No without a FreePDK45 `.tech`** | KLayout LVS stays the engine |

---

## 1. RTL VCD name-join

**Tree today.** `learn/scripts/pdn_activity.py` `probe_activity_trace` joins VCD scopes to gate instance names. Synthetic VCD is READY. Live `learn/sim/gcd/gcd.vcd` is **RTL** and matches **0** gate insts. `gate_sim` dumps `gcd_gate.vcd`; `power_vcd.sh` prefers it. RTL VCD stays the lesson-00 artifact.

**Why it is GAP.** RTL names (`req_msg`, `tb.dut.clk`) are not `_479_/ZN` or `ctrl.state.out[0]$_DFF_P_`.

**Non-mock close.** Simulate the **gate netlist**, dump VCD, join by name:

1. Vendor Nangate **behavioral Verilog** (original library `Front_End/Verilog/NangateOpenCellLibrary.v`). ORFS Nangate45 ships Liberty/LEF/GDS, not the `.v` models. Public copy of the same library file: [Drexel ECEC575 tree](https://github.com/juliankemmerer/drexel-ecec575/blob/master/Encounter/NangateOpenCellLibrary/Front_End/Verilog/NangateOpenCellLibrary.v) (Nangate copyright header). Prefer the Si2 / Silvaco Open Cell Library tarball if the license file is kept.
2. Compile with Icarus: `6_final.v` (or `1_synth.v`) + cell models + existing TB. Sky130 GLS pattern (`FUNCTIONAL`, cell `.v`) is documented in [mattvenn/gate_level_simulation](https://github.com/mattvenn/gate_level_simulation) and OpenLane threads; Nangate is the same idea.
3. `$dumpvars` on the DUT instance so scopes are gate insts.
4. Point `probe_activity_trace` / `run_dynamic_ir` at that VCD. Expect `n_matched > 0` and `t50_via == vcd_name_join`.

**Blockers.** Yosys/ORFS hierarchical names (`$_DFF_P_`) must match the Verilog dump. Functional GLS (no SDF interconnect) is enough for activity edges; Icarus SDF is still incomplete ([iverilog#746](https://github.com/steveicarus/iverilog/issues/746)). Do not invent a name map from RTL ports to ITerms.

**Done.** `run_gate_sim.sh` + Studio action `gate_sim`. Keep RTL VCD for lesson 00. Gate VCD is the IR activity source. Functional GLS, not SDF.

---

## 2. `rdl_route` (no bump LEF on ORFS GCD)

**Tree today.** Dummy `rdl_route` runs on a sidecar ODB (`run_pkg_rdl.sh`). Bump mesh + system PDN already run. `ok` only if the router wrote wires.

**Why it is GAP.** `rdl_route` needs a bump **master** in LEF (`make_io_bump_array -bump …`). OpenROAD docs: [pad README](https://openroad.readthedocs.io/en/latest/main/src/pad/README.html).

**Non-mock close (educational, dummy LEF).** OpenROAD already has a Nangate IO test deck:

- `src/pad/test/rdl_route.tcl` — `read_lef Nangate45/Nangate45.lef` + `Nangate45_io/dummy_pads.lef`, then `rdl_route -layer metal10 -width 4 -spacing 4 "VDD DVDD VSS DVSS p_*"` ([source](https://github.com/The-OpenROAD-Project/OpenROAD/blob/master/src/pad/test/rdl_route.tcl)).
- Same dummy pad LEF is used by `place_pad.tcl`, `bump_array_make.tcl`. Maintainer note: Nangate45 and sky130 have dummy bump LEF; ASAP7 does not ([discussion #4115](https://github.com/The-OpenROAD-Project/OpenROAD/discussions/4115)).

Path:

1. Vendor `dummy_pads.lef` (and the flipchip DEF **or** build bumps on FlowLab `6_final.odb`).
2. Tcl: `make_io_bump_array` → `assign_io_bump` on VDD/VSS (and a few ports) → `rdl_route -layer metal10`.
3. Write DEF/JSON: `rdl.executed=true`, via/layer/net counts, `educational_note: dummy bump LEF (OpenROAD pad test), not C4`.
4. `pkg_rdl.ok` becomes true **only if** `rdl_route` returned and the router wrote wires.

**Blockers.** Dummy pads are not a foundry bump. Do not grow the die or rewrite FlowLab finish. Prefer a **sidecar ODB** so `gcd/flowlab` baseline stays untouched. sky130hd in ORFS has a real IO library; that is a **different PDK** (`oss-integrations.md` forbids mixing).

**Done.** `pkg_rdl_sidecar.tcl` on a copy of the finish ODB + scaled `dummy_bump_gcd.lef`. Dummy label kept. FlowLab baseline untouched.

---

## 3. Thermal (HotSpot / 3D-ICE / PACT)

**Tree today.** `run_thermal_signoff.sh` runs UVA HotSpot and reports `t_max_c` (live ~70.54 °C on FlowLab GCD). IR+droop mV stays a secondary check. OpenROAD has no thermal command (`extended-flow.md` §9).

**Public tools.**

| Tool | License / home | Fit |
|---|---|---|
| **HotSpot 7.0** | UVA, permissive academic — [uvahotspot/HotSpot](https://github.com/uvahotspot/HotSpot) | `.flp` + `.ptrace` → grid T. Pre-RTL / block-level. Compiles with make. |
| **3D-ICE 4.0** | EPFL ESL, [3d-ice page](https://www.epfl.ch/labs/esl/research/open-source-tools-datasets/3d-ice/) | Stack + liquid cooling. Heavier than GCD needs. |
| **PACT** | BU PEACLab, [OSDA 2024](https://www.bu.edu/peaclab/files/2024/03/OSDA_PACT.pdf), GitHub peaclab/PACT | Compact thermal **with an OpenROAD interface** (DEF + OpenSTA power). Uses a SPICE backend (often Xyce); they ship Docker. |

**Non-mock close (recommended: HotSpot first).**

1. Build HotSpot in the env (`make` in the UVA repo).
2. From GCD DEF + `report_power` (or chip IR current density): emit a coarse `.flp` (rows or IR bins) and a `.ptrace` (W per block).
3. Run `hotspot -c hotspot.config -f gcd.flp -p gcd.ptrace`.
4. Parse `maxT` / hotspot cell. Report `kind: thermal_hotspot`, `t_max_c`, `ok` vs an educational bound (e.g. 85 °C), `note: architecture compact model, not foundry`.
5. Keep the IR+droop proxy as a second check, or retire it once HotSpot runs.

PACT is the better **standard-cell** path if we accept a Docker/Xyce dependency. Do not claim Ansys Icepak.

**Blockers.** Floorplan power from OpenSTA is switching/internal/leakage, not a measured IR²R map. Package is a lumped R_ja unless we add a HotSpot package config. That is still more physics than `IR_mV + droop_mV`.

**Done.** `install_hotspot.sh` → `learn/tools/hotspot`. `write_hotspot_deck.py` + `run_thermal_signoff.sh` report `t_max_c`. IR+droop stays a secondary check.

---

## 4. Xyce

**Tree today.** `spice_engines_flowlab.json`: `ngspice=ok Xyce=READY`. `install_xyce.sh` puts the vlsida-eda Xyce 7.4 prefix on PATH; `xyce_vrm_die_gold` runs the N4 deck. Tests keep the deck contract when the binary is missing.

**Why it is GAP.** Sandia ships **RPM for RHEL 8**, not Debian/Ubuntu ([executables](https://xyce.sandia.gov/downloads/executables/)). GitHub is GPLv3 source ([Xyce/Xyce](https://github.com/Xyce/Xyce)). Official install is **CMake + Trilinos** ([INSTALL.md](https://github.com/Xyce/Xyce/blob/master/INSTALL.md)). **Spack** has `xyce` (`spack install xyce ~mpi` is enough for the N4 deck).

**Non-mock close.**

1. Install serial Xyce in the Cloud Agent image (Spack **or** Trilinos cache + Xyce prefix). Put `Xyce` on PATH.
2. Re-run `run_spice_engines.sh` and `xyce_vrm_die_gold`. Expect `status: READY` and |BE−Xyce| bound already in `test_pdn_layers.py`.
3. Optional later: same `write_pg_spice` mesh through Xyce vs ngspice. GCD mesh is small; this is correlation, not a new IR number.

**Blockers.** Trilinos build is heavy (time, disk). Do not drop ngspice. Do not treat Xyce as Voltus. Parallel Xyce is unnecessary for GCD.

**Done (env).** `learn/scripts/install_xyce.sh` puts `Xyce` on PATH (`learn/tools/xyce/bin`). `run_spice_engines.sh` runs `xyce_vrm_die_gold`. Do not restamp gold Dynamic IR.

---

## 5. Nangate CCS

**Tree today.** CCS interpolator + BE loop are real (`test_pdn_layers.py`, synthetic liberty). `NangateOpenCellLibrary_typical.lib` has **no** `output_current` / CCS tables (NLDM `table_lookup` only). Probe on the live lib is GAP by design.

**Public fact.** The ORFS / SiliconCompiler Nangate drop is **NLDM only** ([lambdapdk nangate45](https://github.com/siliconcompiler/lambdapdk/blob/v0.1.52/lambdapdk/freepdk45/libs/nangate45.py) sets `output … nldm`). The 2008 Nangate press release advertised CCS/ECSM in a **commercial-style** kit ([EDN](https://www.edn.com/free-45nm-open-source-digital-cell-library-from-nangate-released-in-its-second-edition/)); that CCS liberty is **not** in ORFS and Si2/Silvaco downloads are not a stable public CCS tarball.

**Non-mock close options (all hard).**

| Option | Verdict |
|---|---|
| Use synthetic CCS in production IR | **Mock.** Tests already forbid mapping NLDM → CCS. |
| Re-characterize Nangate SPICE with a liberty writer | Real, months of work; still not foundry CCS. |
| Switch the course to sky130 (some CCS/NLDM mixes) | **Forbidden** — course pinned to Nangate45. |
| Keep NLDM + α-law STA IR (`sta_ir_aware`) | Current honest path. |

**Done (educational sidecar).** `char_nangate_ccs.py` runs ngspice on GCD combinational cells + PTM 45 nm and writes `learn/sim/lib/nangate45_ptm_ccs_sidecar.lib` with real `output_current_rise/fall`. Probe on that file is READY. Probe on official `typical.lib` stays **NLDM GAP**. INV_X1 delay @ 20 ps / 10 fF is the same order as Nangate NLDM (~16 ps vs ~19 ps). Sequential cells and the 2008 Nangate CCS kit are leftovers. Do not restamp gold Dynamic IR with the sidecar.

---

## 6. LVS match

**Tree today.** Signoff LVS prepares a CDL (unused library cells dropped,
FILLCELL from DEF) and maps wells to VDD/VSS. KLayout printed
`CONGRATULATIONS! Netlists match` on FlowLab GCD. `.lvs.ok` is stamped
only on that line.

Leftovers: FILL/TAP are `blank_circuit` (empty Nangate CDL, no invented
devices). VIA_* have no schematic and still flatten. lvsdb lists
DFF_X2 must-connect (2). Unpinning DFF_X breaks the match; flattening
it after extract raised the count. Flattening every used std-cell
master before extract failed the compare (layout-only cells at align).
Flat extract (no `deep`) plus schematic flatten also failed the compare.
Do not hide those. Do not stamp `.lvs.ok` without the match line.

---

## 7. Commercial / wrong-PDK leftovers

These stay GAP on purpose (`oss-integrations.md`):

- **Raphael / StarRC** — Synopsys. Mapped to OpenRCX + Sakurai–Tamaru/FDM.
- **Magic / Netgen** — installed, no FreePDK45 `.tech`. LVS engine is KLayout.
- **open_pdks / sky130** — different PDK.
- **Board S-parameter System PDN** — would need a vendor Touchstone + a different ngspice deck. Lumped ladder stays educational.

---

## Suggested order if we implement

1. **Gate-level VCD** — highest IR value, code already joins names.
2. **Dummy `rdl_route` lab** — OpenROAD test LEF, sidecar ODB, honest dummy label.
3. **HotSpot** — replace mV proxy with °C on a coarse floorplan.
4. **Xyce in the image** — flip the existing deck from GAP to READY.
5. Leave **Raphael**, **sky130**, and **course 0/8** alone. CCS is the INV_X1 PTM sidecar only.

---

## Deep feasibility analysis

For a per-GAP evaluation of all remaining items (CCS, LVS, Raphael/StarRC,
FasterCap, Magic/Netgen, sky130, board S-parameter, course 0/8) with public
tools, papers, and implementation paths, see
[remaining-gaps-evaluation.md](./remaining-gaps-evaluation.md).
