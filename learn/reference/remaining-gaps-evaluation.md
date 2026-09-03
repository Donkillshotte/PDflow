# Remaining educational GAPs — feasibility evaluation

Research note. Not a product win plan. Do not mix product and lab.
Do not treat a synthetic table or a wrong-PDK result as foundry sign-off.

**Scope**: every GAP still labeled in the tree after the four closes
(gate VCD, dummy RDL, HotSpot, Xyce). For each: root cause, what
public tools and data exist, what we can realistically do in this
OSS Nangate45/ORFS environment, and an honest verdict.

Course progress `0/8` is student work, not a tool GAP, but is evaluated
here because the user asked.

---

## Summary matrix

| GAP | Verdict | Effort | What changes |
|---|---|---|---|
| **CCS tables** | **Partially closable** — re-characterize from SPICE | Medium-high | New CCS `.lib` from `vyges-char` + Nangate CDL + FreePDK45 PTM |
| **LVS mismatch** | **Partially closable** — investigate + tighten runset | Low-medium | KLayout LVS runset fix or `connect_implicit` for TBUF/TINV/TLAT |
| **Raphael / StarRC** | **Not closable** — commercial | — | OpenRCX + analytical PEX stay the OSS path |
| **FasterCap (field solver)** | **Closable** — build + 2-wire demo | Low | Compile FasterCap, run on existing analytical PEX geometry |
| **Magic `.tech`** | **Partially closable** — write a minimal `.tech` | Medium | Write FreePDK45 `.tech` from the NCSU layer definitions |
| **Netgen LVS** | **Partially closable** — setup file + CDL | Low-medium | Netgen LVS with Nangate CDL + `model blackbox` or `.include` |
| **sky130 multi-PDK** | **Closable but out of scope** — different PDK | High | ORFS already supports sky130hd; course is pinned to Nangate45 |
| **Board S-parameter** | **Partially closable** — public TUHH data | Medium | Load TUHH Touchstone via `scikit-rf`, replace lumped ladder |
| **Course 0/8** | **Closable** — student work automation | Low | Scripted lesson completion, but 0/8 is *designed* as student pace |

---

## 1. CCS tables (Nangate45)

### Root cause

The ORFS Nangate45 liberty (`NangateOpenCellLibrary_typical.lib`) uses
`delay_model : table_lookup` (NLDM). It has **no** `output_current` groups.
The original Nangate library *does* include CCS/ECSM views (the 2008 Nangate
README says "Added CCS Timing and ECSM Timing characterization results in
Liberty format"), but these are in the **full Si2/Silvaco tarball**, not in
the ORFS public drop. The Si2 download requires an institutional request form.

### What exists

- **Si2/Silvaco 45nm library**: CCS liberty exists, free for universities. Requires form submission at [si2.org](https://si2.org/open-cell-and-free-pdk-libraries/). Not a stable wget URL.
- **`vyges-char`** ([github.com/vyges-tools/char](https://github.com/vyges-tools/char)): open-source liberty characterization tool. Supports **NLDM + CCS** (`ccs: true`). Uses ngspice. Validated on sky130. Needs cell SPICE netlist + PDK device models.
- **CharLib** (Mellor & Stine, MWSCAS 2024): NLDM only, no CCS yet. ngspice/Xyce backend.
- **Libretto** (Nishizawa, IEICE 2022): NLDM + NLPM for combinational/sequential. No CCS.
- **Nangate CDL**: 135 cells with NMOS_VTL/PMOS_VTL transistors are in `nangate45/cdl/NangateOpenCellLibrary.cdl`. These are real SPICE-level subcircuits.
- **FreePDK45 PTM BSIM4 models**: published by ASU ([ptm.asu.edu](http://ptm.asu.edu)). The Nangate library was characterized against these models.

### Feasibility

**Yes, partially closable.** Path:

1. Obtain FreePDK45 PTM BSIM4 models (public, ASU).
2. Use `vyges-char` with `ccs: true` on a subset of Nangate cells (INV, BUF, NAND2, NOR2, DFF — ~10–20 cells covering GCD).
3. Produce a `NangateOpenCellLibrary_typical_ccs.lib` with `output_current_rise/fall` vectors.
4. Validate: run OpenSTA with CCS liberty and compare WNS/TNS delta vs NLDM.

**Effort**: medium-high. Each cell needs ~50–100 SPICE sims (7×7 slew×load grid × rise/fall). 20 cells × 100 sims = 2000 ngspice runs. `vyges-char` parallelizes, but this is hours of compute. Device model correlation (PTM vs the Nangate-internal models) may introduce small systematic deltas.

**Honest leftover**: the CCS tables would be re-characterized, not the original Nangate CCS. WNS delta should be small for 45 nm NLDM-vs-CCS (CCS matters more at advanced nodes). The **engine** (`sta_ir_aware` CCS interpolator) is already done and tested.

**Verdict**: partially closable with real work. Not a mock.

---

## 2. LVS netlist match

### Root cause

KLayout LVS log shows:
```
Flatten schematic circuit (no layout): TBUF_X1
Flatten schematic circuit (no layout): TBUF_X16
...
Flatten schematic circuit (no layout): TINV_X1
Flatten schematic circuit (no layout): TLAT_X1
...
ERROR : Netlists don't match
```

The CDL (from `NangateOpenCellLibrary.cdl`) includes **all 135 cells**, but GCD
only uses ~30–40. The extras (TBUF, TINV, TLAT, XOR2, …) are in the CDL as
`.SUBCKT` definitions but have **no corresponding layout cells in the GDS**.
KLayout tries to flatten them and reports "no layout".

Additionally, the CDL uses 4-terminal MOSFET models (`M … NMOS_VTL W=… L=…`)
while the extracted layout may produce 3-terminal devices (no explicit body
connection in the standard cells — body is connected via well taps in separate
cells).

### What exists

- **KLayout LVS forum**: the 4→3 terminal mismatch is well-documented. Solution: `MOS4To3NetlistSpiceReaderDelegate` in the `.lylvs` file (see [klayout.de forum #1442](http://www.klayout.de/forum/discussion/1442/)).
- **`connect_implicit`**: KLayout LVS supports `connect_implicit("*", "VDD:NWELL")` and `connect_implicit("*", "VSS:PWELL")` to implicitly connect body terminals to power/ground rails.
- **CDL filtering**: the runset can exclude cells not present in the layout, or the CDL can be filtered to only include cells actually instantiated in `6_final.v`.

### Feasibility

**Partially closable.** Path:

1. Filter CDL to only include cells instantiated in GCD synthesis (`grep '^\.' 6_final.v` to get the cell list, then filter the CDL).
2. Add `connect_implicit` for NWELL→VDD and PWELL→VSS in the LVS runset.
3. If 4→3 terminal mismatch persists, add a `MOS4To3NetlistSpiceReaderDelegate`.
4. Re-run LVS and check if the remaining mismatches are real connectivity errors or just library-level issues.

**Risk**: even after filtering and connecting wells, FreePDK45 tutorial layouts are sometimes not LVS-clean due to missing well taps, incomplete cell abstracts, or pin labeling issues. The KLayout FreePDK45 runset (`FreePDK45.lylvs` from [laurentc2/FreePDK45_for_KLayout](https://github.com/laurentc2/FreePDK45_for_KLayout)) is community-maintained and may need fixes.

**Honest leftover**: if LVS passes after fixing the runset, it passes on the *educational* FreePDK45 flow, not on a foundry-qualified PDK. If it still fails on real connectivity issues (missing S/D connections, incomplete abstracts), that is an honest fail, not a mock.

**Verdict**: partially closable. Worth investigating. Do **not** write `.lvs.ok` on a fake pass.

---

## 3. Raphael / StarRC (commercial parasitic extraction)

### Root cause

Synopsys commercial tools. No open-source license. No free download.

### What exists

- **OpenRCX**: already integrated. Rule-based, calibrated against a reference extractor. Accuracy: ~2% on block total capacitance, but ±25–40% per-net spread (rule-based ceiling). Good enough for digital flow iterations.
- **`vyges-extract`** ([github.com/vyges-tools/extract](https://github.com/vyges-tools/extract)): calibrated sky130 deck, tracks OpenRCX to ~0.997 correlation. Openly acknowledges the rule-based ceiling vs field-solver accuracy.
- **FasterCap**: LGPL 3D/2D capacitance field solver. Can solve individual structures. Not a full-chip extractor.
- **Analytical PEX** (`run_analytical_pex.py`): Sakurai–Tamaru + 2D FDM Laplace. Educational 2-wire demo.

### Feasibility

**Not closable.** Raphael/StarRC are commercial sign-off tools with 3D field solvers. The open ecosystem currently lacks a field-solver-accurate full-chip extractor. OpenRCX + analytical PEX is the honest OSS path.

**What we can do**: build FasterCap from source and run it on the same 2-wire geometry as `run_analytical_pex.py`, giving students a real BEM field solver to compare against the closed-form Sakurai–Tamaru. This is educational, not sign-off.

**Verdict**: **blocked**. Document that the engine gap is real. OpenRCX is the production path; FasterCap is a tutorial complement.

---

## 4. FasterCap (field solver complement to analytical PEX)

### Root cause

`analytical_pex` uses Sakurai–Tamaru closed-form + 2D FDM. FasterCap is the open BEM solver but not integrated.

### What exists

- **FasterCap 6.0.9** ([github.com/ediloren/FasterCap](https://github.com/ediloren/FasterCap)): LGPL, CMake build. 3D and 2D. Linux binaries available (Kubuntu 16.04, CentOS — may need recompile for Ubuntu 24.04).
- Source: requires `LinAlgebra` and `Geometry` companion libraries from the same author.
- AUR package exists (v6.0.9, June 2026).

### Feasibility

**Closable.** Path:

1. Build FasterCap from source (CMake + gcc).
2. Generate a 2-wire input from the same FreePDK45 M2 geometry used in `run_analytical_pex.py`.
3. Run FasterCap → extract Cg/Cc.
4. Compare: Sakurai–Tamaru vs 2D FDM vs FasterCap BEM vs OpenRCX SPEF.

**Effort**: low. Build + wrapper script + comparison report.

**Verdict**: closable, educational complement.

---

## 5. Magic `.tech` file for FreePDK45

### Root cause

Magic is installed (v8.3) but uses `minimum` tech. No FreePDK45 `.tech` file exists in the ORFS tree. NCSU FreePDK45 ships Calibre DRC/LVS files, not Magic tech files. The open_pdks project supports sky130 and gf180 with full Magic tech, but does **not** ship a FreePDK45 adaptation.

### What exists

- **NCSU FreePDK45**: has the layer definitions (metal stack, via names, design rules) in the Cadence tech file and `HSPICE_MODELS`. The DRC rules are documented.
- **Oklahoma State University** FreePDK45 flow: includes Magic cell layouts for some cells in their standard-cell library, implying a `.tech` existed at one point. But it's not publicly downloadable as a standalone Magic tech file.
- **open_pdks** ([github.com/RTimothyEdwards/open_pdks](https://github.com/RTimothyEdwards/open_pdks)): has a framework for adapting PDKs to Magic/Netgen, including a Makefile that generates `.tech` from metal stack definitions. A [community effort](https://web.open-source-silicon.dev/t/422766/) attempted FreePDK45 integration via open_pdks but encountered issues with `.mag` cell generation and DRC.

### Feasibility

**Partially closable with significant effort.** Path:

1. Write a `FreePDK45.tech` file from the NCSU layer definitions (metal1–metal10, via1–via9, poly, diffusion, nwell, pwell). The Magic tech format is [well-documented](http://opencircuitdesign.com/magic/archive/papers/maint2.pdf).
2. Add a `.magicrc` that loads the tech file.
3. Test: `magic -T FreePDK45 6_final.gds` — can it read the GDS and display correctly?
4. Extract: `magic -dnull -noconsole` + `extract all` → `.ext` → `ext2spice`.

**Risk**: writing a complete, correct `.tech` file is significant work (~200–500 lines, covering all layers, connections, CIF/GDS mapping, extract rules, DRC rules). The extract/DRC accuracy depends on correct parasitic coefficients that need calibration against the FreePDK45 process parameters.

**Honest leftover**: even with a `.tech`, Magic on FreePDK45 is educational, not foundry-qualified. KLayout remains the course DRC/LVS engine.

**Verdict**: partially closable, medium effort. May not be worth it given KLayout already works.

---

## 6. Netgen LVS on Nangate45

### Root cause

Netgen (`netgen-lvs` 1.5.133) is installed but has no setup file for FreePDK45/Nangate45. It needs to know how to map the schematic CDL transistor models (NMOS_VTL, PMOS_VTL) to the extracted layout devices.

### What exists

- **Netgen setup files**: sky130 has a full `sky130A_setup.tcl` shipped with open_pdks. FreePDK45 does not.
- **SiliconCompiler/lambdapdk**: includes a Netgen LVS driver for FreePDK45 (`siliconcompiler/tools/netgen/lvs.py`), suggesting it *can* work with proper setup.
- **Netgen `model blackbox`**: standard cells can be treated as opaque primitives if the schematic includes `.include` of the CDL library.

### Feasibility

**Partially closable.** Path:

1. Write a `freepdk45_setup.tcl` for Netgen:
   - Map NMOS_VTL → nmos, PMOS_VTL → pmos
   - Set permute rules for S/D
   - `property` rules for W/L matching
2. Run: `netgen -batch lvs "6_final_extracted.spice gcd" "NangateOpenCellLibrary.cdl gcd" freepdk45_setup.tcl`
3. Compare results with KLayout LVS.

**Effort**: low-medium. The setup file is ~50 lines. The harder part is getting Magic to extract a clean SPICE netlist from the GDS (which requires the `.tech` file from §5 above). Without Magic extraction, Netgen can still compare CDL-vs-CDL or use KLayout's extracted netlist.

**Verdict**: partially closable, but depends on Magic `.tech` for full utility. Without it, Netgen LVS is limited to schematic-vs-schematic (not very useful).

---

## 7. sky130 multi-PDK

### Root cause

Course is **pinned to Nangate45**. sky130 is a different PDK. Mixing them would violate `oss-integrations.md`.

### What exists

- ORFS supports sky130hd/sky130hs natively with full config.mk, Liberty, LEF, GDS, PDN, CTS.
- sky130 has **real IO cells** (`sky130_fd_io`), unlike Nangate45 dummy pads.
- sky130 has **CCS/ECSM in some liberty variants** (mixed with NLDM).
- sky130 has full Magic `.tech`, Netgen setup, open_pdks integration.
- sky130 **LVS is clean** on most standard cells via KLayout or Netgen.

### Feasibility

**Closable but explicitly out of scope.** If we switched the entire course to sky130, many GAPs would close (LVS, Magic, Netgen, CCS, real IO pads). But:
- The course is designed around Nangate45 (all lessons, golden metrics, SDC).
- Porting would require new golden metrics, new SDC, new config.mk, re-running all lessons.
- AGENTS.md forbids mixing sky130 with FreePDK45.

**What we could do**: add a **sky130 elective module** (parallel to the Nangate45 course) that demonstrates how the same flow runs on a different PDK. This does not close Nangate45 GAPs but shows the student the full-stack PDK comparison.

**Verdict**: closable as a separate elective, not as a replacement for the Nangate45 course.

---

## 8. Board S-parameter System PDN

### Root cause

The current System PDN is a lumped RLC ladder (`pdn_vrm.py`). Real board-level PDN analysis uses frequency-dependent S-parameter models (Touchstone files) from EM simulation or measurement.

### What exists

- **TUHH SI/PI Database** ([Schierholz et al., IEEE Access 2021](https://doi.org/10.1109/ACCESS.2021.3061788)): public S-parameter datasets for 4-layer and 6-layer PCB PDNs with parametric variations. Touchstone `.sNp` files. Open access, CC license.
- **scikit-rf** ([scikit-rf.org](https://scikit-rf.org/)): BSD-licensed Python library for S-parameter analysis. Reads Touchstone, converts to Z/Y/ABCD, cascades networks, models shunt components. Already pip-installable.
- **SRAM-PG** ([ShenShan123/SRAM-PG](https://github.com/ShenShan123/SRAM-PG)): SPICE-format PDN benchmarks from SRAM designs (TSMC 28 nm). Not Touchstone, but correlatable.

### Feasibility

**Partially closable.** Path:

1. Download a TUHH 4-layer PCB PDN Touchstone file (public).
2. Use `scikit-rf` to load the S-parameters and compute Z(f) = Z11 impedance.
3. Replace the lumped board section of `pdn_vrm.py` with the measured Z(f) as a frequency-dependent impedance.
4. Re-run the System PDN AC analysis with the board S-parameter model.
5. Compare: lumped-ladder Z(f) vs S-parameter Z(f) at the die port.

**Effort**: medium. The integration is ~100–200 lines of Python. The conceptual gap is that the TUHH data is for a generic PCB, not for our educational Nangate45 package. But it is *real* EM-simulated data, not a mock.

**Honest leftover**: the board model is generic, not package-matched. The connection point (die ↔ package ↔ board) still uses lumped parameters for the package section. Full SI/PI would need a matched package model (BGA/wirebond) that does not exist for FreePDK45.

**Verdict**: partially closable with real S-parameter data.

---

## 9. Course 0/8 progress

### Root cause

Course progress is tracked by `learn/lib/progress.sh` → `learn/.progress.json`. Each lesson has a `run.sh` that the student runs interactively. Progress is marked when the student calls `learn_mark_complete <lesson_id>`. No progress file exists yet → `0/8`.

### What exists

- 8 lessons (00-intro through 07-finish), each with `run.sh`, `README.md`.
- Lessons involve interactive steps: reading docs, running ORFS commands, inspecting GUI, answering questions.
- `learn_physical_design.sh --check` verifies prerequisites.
- `test_course.sh` runs smoke tests but does not mark progress.

### Feasibility

**Closable but not desirable.** We could script `learn_mark_complete "00-intro"` through `"07-finish"` to set progress to 8/8. But:

- Course 0/8 is **by design**: it reflects the student's actual progress.
- Faking 8/8 violates the AGENTS.md rule: "Do not fake course 0/8."
- The lessons require interactive work (GUI inspection, SDC editing, timing analysis).

**What we could do**:
- Run lesson 00 end-to-end (it is mostly automated) and mark it complete. That makes progress 1/8.
- Add a `--auto` flag to `learn_physical_design.sh` that skips `ui_pause` prompts for CI/demo purposes.
- But this is not "closing a GAP" — it is changing the course UX.

**Verdict**: **not a GAP**. Course progress is student work. Do not automate marking 8/8.

---

## Attempted integration (2026-09-03)

Tried every closable item. Kept only what ran end-to-end.

| GAP | Tried | Result |
|---|---|---|
| LVS CDL filter | Yes — unused library SUBCKTs dropped | Unused TBUF/TLAT gone. **Every used stdcell still fails transistor compare** (`AND2_X1`…`XNOR2_X2`). Not a pass. Script kept as `filter_lvs_cdl.py`. Transistor LVS stays FAIL. |
| FasterCap | Yes — built 6.0.7 headless, 2-wire deck | **READY.** Wired into `run_analytical_pex.py`. |
| CCS / vyges-char | Not shipped | Needs PTM + full-library char hours. No fake tables. |
| Board S-parameter | Not shipped | TUHH data is form-gated. No public Touchstone without a request. |
| Magic `.tech` | Not shipped | No verified extract. KLayout stays LVS/DRC. |
| Netgen | Not shipped | Same device-compare problem without Magic extract. |
| sky130 | Out of scope | Course pinned to Nangate45. |
| Course 0/8 | Not faked | Student progress. |

---

## Recommended implementation order

If we proceed with the closable items:

| Priority | GAP | Why first |
|---|---|---|
| 1 | **LVS investigation** | Low effort, high signal. May close the last red X in the signoff matrix. |
| 2 | **FasterCap** | Low effort. Adds a real field solver to the PEX comparison. |
| 3 | **CCS re-characterization** | Medium-high effort. Closes the last timing-model gap. Requires PTM models + `vyges-char`. |
| 4 | **Board S-parameter** | Medium effort. Adds real EM data to the System PDN. |
| 5 | **Netgen LVS** | Low-medium. Adds a second LVS engine. Depends on LVS investigation results. |
| 6 | **Magic `.tech`** | Medium. Enables Magic extraction but may not add much over KLayout. |
| 7 | **sky130 elective** | High. Out of scope for the current course but valuable as a PDK comparison module. |

---

## References

- Si2 Open Cell Library: <https://si2.org/open-cell-and-free-pdk-libraries/>
- vyges-char (CCS characterization): <https://github.com/vyges-tools/char>
- CharLib (MWSCAS 2024): <https://doi.org/10.1109/mwscas60917.2024.10658687>
- KLayout LVS 4→3 terminal fix: <http://www.klayout.de/forum/discussion/1442/>
- FasterCap: <https://github.com/ediloren/FasterCap>
- vyges-extract: <https://github.com/vyges-tools/extract>
- TUHH SI/PI Database: <https://doi.org/10.1109/ACCESS.2021.3061788>
- scikit-rf: <https://scikit-rf.org/>
- SRAM-PG benchmarks: <https://github.com/ShenShan123/SRAM-PG>
- FreePDK45 NCSU: <https://eda.ncsu.edu/freepdk/freepdk45/>
- ASU PTM: <http://ptm.asu.edu>
- Magic tech file format: <http://opencircuitdesign.com/magic/archive/papers/maint2.pdf>
- SiliconCompiler Netgen driver: <https://github.com/siliconcompiler/siliconcompiler/blob/main/siliconcompiler/tools/netgen/lvs.py>
