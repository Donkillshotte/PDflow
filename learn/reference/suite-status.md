# Suite / flow status (GCD Nangate45 FlowLab)

Honest snapshot of what runs and what does not. Not a product win list.
Do not mix Product / Lab / Course. Do not mix IR meshes.
Living campaign review: [`docs/rtl_to_signoff.md`](../../docs/rtl_to_signoff.md)
(leftover-free stopped 2026-09-04, not achieved).

Evidence: `learn/sim/reports/*_flowlab.json`, ORFS
`results/nangate45/gcd/flowlab/`, `GET /api/suite`. Course progress is
student work (`0/8`).

Studio prefers `gcd/flowlab/` then `gcd/learn/`. Live suite count is
taken from `GET /api/suite` after the last signoff run. Magic/Netgen
stays **GAP**. Gold Dynamic IR stays **LOCKED** at 45.298 mV.

Gaps are split in [`gaps.md`](gaps.md): license/PDK gated vs to-build.

Legend:

| Status | Meaning |
|---|---|
| **WORKS** | Ran on this GCD; report `ok` / READY |
| **WORKS*** | Works, with an educational leftover in the note |
| **FAIL** | Ran; honest mismatch or pillar fail |
| **GAP** | Missing tool, commercial, or wrong PDK — not faked |
| **LOCKED** | Must not be restamped / must stay as-is |

---

## What is missing, and why (plain language)

Three different things get mixed in Studio. Only the last two are real leftovers.

### 1. Studio red lights that are not missing work

Studio now prefers `gcd/flowlab/` then `gcd/learn/`. Course lesson
gates stay on `learn` so 0/8 is not stamped by FlowLab artifacts.

LVS compare matches. Leftovers that stay visible on purpose:

- **Timing:** leftover setup open (locked `flowlab` WNS −0.02 · copy
  `eco_scratch` WNS −0.01 on `resp_msg[14]`) · leftover no MCMM
  (`typical.lib` only)
- **Geometry:** antenna 300:1 in `FreePDK45.lydrc` · leftover no
  density / named ERC
- **Equivalence:** leftover must-connect 2 on `DFF_X2` · `VIA_*` flatten
- **Power:** IR meshes not comparable · `em_checked` 0 (no emlimit)
- **Commercial / form-gated GAPs:** official CCS, StarRC, Touchstone,
  Magic/Netgen, sky130 as course PDK

### 2. LVS (KLayout compare)

Signoff LVS now runs KLayout on a prepared CDL: unused library SUBCKTs
dropped, FILLCELL instances taken from the DEF, wells mapped to VDD/VSS
(`connect_global`). A pass is only recorded when KLayout prints
`CONGRATULATIONS! Netlists match`.

Leftovers that stay visible:

- FILL/TAP CDL bodies are empty; `blank_circuit` marks them abstract
  so they no longer flatten as "layout cell (no schematic)".
- VIA_* routing cells have no schematic and still flatten (expected).
- lvsdb still lists must-connect on DFF_X2 well ties (2 warnings).
  Flattening XNOR2/MUX2/NAND3-4/OAI22/AND3 moved the leftover.
  Unpinning DFF_X breaks the match; flattening it after extract raised
  the count to 4. Flattening every used std-cell master before extract
  failed the compare. Flat extract (no `deep`) plus schematic flatten
  also failed the compare. Warnings, not a substitute for the compare line.

### 3. Real GAPs — missing data or a tool we will not pretend to be

| What you might expect | What we have | Why it stays missing |
|---|---|---|
| Foundry / Si2 **CCS liberty** on every Nangate cell | Official `typical.lib` is **NLDM**. PTM sidecar: **19 combinational GCD cells** / 38 `output_current` tables (INV/BUF/CLKBUF/NAND/NOR/AND/OR/AOI21/OAI21). No DFF/MUX. | Si2 2008 CCS is form-gated. Sidecar is re-char, not that file. |
| **StarRC / Raphael** full-chip parasitics | OpenRCX SPEF (657 nets) + 2-wire FasterCap BEM | Those two are Synopsys commercial. No license → no fake SPEF. |
| Board **S-parameter** (Touchstone `.sNp`) | Lumped VRM→board→pkg ladder in ngspice | Public TUHH SI/PI decks are form-gated. Exporting the lump as `.sNp` would be a lie. |
| **Magic + Netgen** LVS/extract on this GCD | KLayout DRC/LVS | `magic` / `netgen` are not in PATH here, and there is no verified FreePDK45 Magic `.tech`. |
| **sky130** course | Nangate45 only | Different PDK. Mixing it into this course is forbidden. |
| Tapeout **C4 bumps / RDL** | Dummy bump LEF + sidecar `rdl_route` (4 bumps, 36 wires) | Educational OpenROAD pad test, not a package foundry. |
| **PrimeTime / Tempus / Voltus** | OpenSTA + PDNSim + Xyce N4 compact | We do not claim sign-off equivalence. |
| Course **8/8** | **0/8** | Student pace. Do not stamp `.progress.json`. |
| A new gold Dynamic IR | **45.298 mV** stays | current_run (~5.173) and chip PDN are other meshes. Never restamp gold. |

**WORKS\*** in the tables below means: the script ran and the number is
real, but it is not the commercial / foundry object with the same name.

---

## Next honest closes (this goal)

The six physical closes below are **done**. The leftover-free goal was
stopped. Next action is leftover-named suite integrity (plan only):
[`docs/rtl_to_signoff_close_plan.md`](../../docs/rtl_to_signoff_close_plan.md).

Do all six. Do not fake a pass. Do not restamp gold IR **45.298 mV**.
Course stays **0/8**. `gcd/flowlab/` baseline ODBs are not overwritten.

| # | Workstream | Status | Evidence |
|---|---|---|---|
| 1 | Studio paths | **done** | `preferredResultsVariant()` · course gates stay `learn` |
| 2 | dynamic_ir hook | **done** | `ok` from `_direct.json` (current_run). Gold 45.298 stays locked on another mesh. |
| 3 | Vectorless VCD | **done** | `gcd_gate.vcd` · `tb_gcd_gate/dut` |
| 4 | gridcheck | **done** | PSM-0040 VDD+VSS · stamp only after pass |
| 5 | Extra combo CCS | **done** | 19 cells / 38 tables · official lib NLDM |
| 6 | LVS increment | **done (KLayout match)** | well→VDD/VSS + FILL from DEF · `.lvs.ok` only on match |

Gates: `test_signoff_honesty.py` · `test_lab_physics.py` · live `GET /api/suite`.

---

## Course (Studio lessons)

| Step | Status | Evidence | Leftover |
|---|---|---|---|
| Lessons 00–07 progress | **LOCKED** | `0/8` · no `.progress.json` | Student pace. Do not fake 8/8 |
| RTL GCD source | **WORKS** | `designs/src/gcd/gcd.v` | — |
| Materials / docs | **WORKS** | `learn/reference/` | English only |

---

## RTL → GDS (ORFS pipeline, `FLOW_VARIANT=flowlab`)

Artifacts exist under `tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/`.

| Step | Status | Evidence | Leftover |
|---|---|---|---|
| Synth (`1_synth.odb`) | **WORKS** | ODB on disk | — |
| Floorplan | **WORKS** | `2_floorplan.odb` | — |
| Place | **WORKS** | `3_place.odb` | — |
| CTS | **WORKS** | `4_cts.odb` | — |
| Route | **WORKS** | `5_route.odb` | — |
| Finish (GDS / SPEF / CDL) | **WORKS** | `6_final.gds` `.spef` `.v` `.odb` | Do not overwrite `gcd/flowlab/` |

---

## Signoff pillars

| Step | Status | Evidence | Leftover |
|---|---|---|---|
| STA | **WORKS** | WNS −0.02 ns · TNS −0.14 · 16 viol | leftover setup open (WNS −0.02 at 0.46 ns) · leftover no MCMM (`typical.lib` only) |
| STA IR-aware | **WORKS*** | `sta_ir_aware` ok · NLDM × ITerm V | Does not change official WNS |
| DRC (route + GDS) | **WORKS** | 0 route lines · 0 GDS items | antenna 300:1 · leftover no density / named ERC |
| LVS (KLayout) | **WORKS*** | Compare match on filtered CDL | FILL/TAP abstract. VIA flatten. DFF_X2 must-connect 2 |
| LVS deep (filter + VTL) | **WORKS*** | same compare path | Black-box is labeled separately |
| ECO | **WORKS*** | propose on flowlab; apply/close on eco_scratch | Does not skip `signoff_all`. Two OpenROAD processes: SPEF size-up, BufferMove without SPEF (29 buffers), `global_connect`. Copy OpenSTA: R2R MET, leftover WNS −0.01 on `resp_msg[14]` (course 20% output delay). Shared NAND2_X2 `_647_` also drives R2R; clone/size-up of that cone regresses R2R. Locked flowlab still has R2R leftover (do not overwrite). DRT-0206 restore-source is the fallback. |
| Power signoff | **WORKS*** | Chip static **1.05 mV** · transient **9.47 mV** | IR meshes not comparable · lumped board, not S-parameter |
| `signoff_all` | **WORKS** | four pillars from their JSON | leftover must-connect · leftover setup open · leftover no MCMM · leftover no density / named ERC · IR meshes not comparable |

---

## Sim · activity · IR (do not mix numbers)

| Step | Status | Evidence | Leftover |
|---|---|---|---|
| RTL sim (Icarus) | **WORKS** | `rtl_sim` · `gcd.vcd` | Ports only for IR name-join |
| Gate sim + name-join | **WORKS** | `GATE_SIM_PASS` · `gcd_gate.vcd` | Functional GLS, no SDF |
| Activity → power | **WORKS** | `activity_power` / vectorless report | Prefer gate VCD scope |
| Vectorless | **WORKS*** | P=4.9 mW · I_avg=4.45 mA · dynamic source gate VCD | GLS, no SDF |
| Chip PDN (PDNSim mesh) | **WORKS*** | static **1.05 mV** · transient **9.47 mV** (`pdn_chip_ir`) | Not gold Dynamic IR. I(t) companion static is 1.05 mV on a different cook — do not mix |
| vyges-em-ir | **WORKS*** | static 15.1 mV · droop 86.0 mV | Different mesh again |
| Dynamic IR **gold** | **LOCKED** | **45.298 mV** · `gold: true` | Never restamp |
| Dynamic IR current_run | **WORKS*** | ~**5.173 mV** | Not gold; not chip PDN. Finish SPEF t50. |
| System PDN | **WORKS*** | droop **6.03 mV** (power_signoff) | Lumped VRM→board→pkg. No Touchstone |
| Board S-parameter | **GAP** | TUHH form-gated | Do not export the lumped ladder as `.sNp` |

---

## PEX · timing models · SPICE

| Step | Status | Evidence | Leftover |
|---|---|---|---|
| OpenRCX SPEF | **WORKS** | 657 nets / CAP / RES | Rule-based, not StarRC |
| Analytical PEX | **WORKS** | ST Cg=1.200 fF Cc=0.864 fF | 2-wire demo |
| FasterCap BEM | **WORKS*** | Cg=1.097 fF Cc=0.564 fF · READY | Not Raphael / not full-chip |
| Raphael / StarRC | **GAP** | commercial | — |
| Official Nangate CCS | **GAP** | `typical.lib` NLDM only | Engine interpolator is real |
| PTM CCS sidecar | **WORKS*** | 19 GCD combo cells · 38 `output_current` tables · INV_X1 16.1 ps vs NLDM 19.2 ps | Re-char, not 2008 Nangate CCS; no DFF |
| ngspice | **WORKS** | System PDN + CCS char | — |
| Xyce N4 | **WORKS** | `xyce_status: READY` | Compact VRM+die, not Voltus |

---

## Package · thermal · formal

| Step | Status | Evidence | Leftover |
|---|---|---|---|
| Dummy bump | **WORKS*** | 14 bumps · mesh V=15 | Dummy, not C4 |
| Dummy `rdl_route` | **WORKS*** | executed · 4 bumps · 36 wires | Sidecar ODB, not C4 |
| PKG signoff | **WORKS*** | bump + RDL + system_pdn | Educational package |
| HotSpot thermal | **WORKS*** | t_max **70.54 °C** | Architecture compact model |
| Phase 2 signoff | **WORKS** | thermal + PKG ok | — |
| Yosys equiv | **WORKS** | RTL ↔ generic-synth PASS | CLI `eqy` absent; Yosys `equiv_*` |
| Formal SAT | **WORKS** | `reset → !resp_val` PASS | CLI `sby` absent; Yosys `sat -tempinduct` |

---

## Layout extras / PDK

| Step | Status | Evidence | Leftover |
|---|---|---|---|
| KLayout viewer / DRC | **WORKS** | signoff DRC 0 | — |
| Magic | **GAP** | not in PATH here | No FreePDK45 `.tech` |
| Netgen | **GAP** | not in PATH here | Needs Magic extract |
| sky130 / open_pdks | **GAP** | course pinned to Nangate45 | Do not mix PDKs |

---

## Product / Lab (separate surfaces)

| Step | Status | Evidence | Leftover |
|---|---|---|---|
| Lab DSE (flowlab memory) | **WORKS*** | `dse_flowlab.json` 140 candidates | Lab, not a product win |
| Product win rule | **LOCKED** | `learn/dse/win_rule.py` | Do not promote lab IR to a win |
| AES row `febe6804241c` | **LOCKED** | memory AES | Do not overwrite |
| Krylov on AES | **GAP** | forbidden (~50–70k-R) | — |
| TPE spi @ 1 ns | **GAP** | forbidden | — |

---

## Invariants (always report together when claiming a finish)

Area, power, leakage, and IR. Honest win/lose.

| Quantity | Value | Do not confuse with |
|---|---|---|
| Gold Dynamic IR | **45.298 mV** | current_run 5.173 · chip PDN |
| Chip PDN static / transient | **1.05 / 9.47 mV** | gold · I(t) companion static 1.05 (same order, not the same mesh) |
| System PDN droop | **6.03 mV** | chip transient |
| HotSpot t_max | **70.54 °C** | IR proxy mV |

---

## Studio `GET /api/suite` hooks (live)

Physics status is the source of truth. `UI` is the boolean Studio
shows. `FN` = false-negative (artifact exists under `flowlab/`).

| Group | Hook | UI | Physics | Note |
|---|---|---|---|---|
| Environment | toolchain | ok | **WORKS** | openroad · yosys · sta · klayout |
| Environment | magic_netgen | no | **GAP** | not in PATH · no FreePDK45 `.tech` |
| Environment | ngspice | ok | **WORKS** | Xyce READY |
| Environment | iverilog | ok | **WORKS** | RTL + gate sim |
| Environment | hotspot | ok | **WORKS*** | t_max 70.54 °C |
| Environment | fastercap | ok | **WORKS*** | 2-wire BEM |
| Environment | ccs_char | ok | **WORKS*** | 19 cells · official lib NLDM |
| Environment | display | ok | **WORKS** | `DISPLAY :1` |
| Environment | spice_engines | ok | **WORKS** | ngspice + Xyce N4 |
| Frontend | rtl | ok | **WORKS** | `gcd.v` |
| Frontend | rtl_sim | ok | **WORKS** | `gcd.vcd` |
| Frontend | gate_sim | ok | **WORKS** | `GATE_SIM_PASS` |
| PD | synth | ok | **WORKS** | `flowlab/1_synth.odb` |
| PD | pdn | ok | **WORKS** | `flowlab/2_4_floorplan_pdn.odb` |
| PD | finish | ok | **WORKS** | `flowlab/6_final.gds` |
| Power | gridcheck | ok | **WORKS*** | PSM-0040 · stamp after pass |
| Power | system_pdn | ok | **WORKS*** | lumped ladder · no Touchstone · `/pkg` |
| Power | activity | ok | **WORKS** | gate VCD preferred |
| Power | vectorless | ok | **WORKS*** | dynamic source gate VCD |
| Power | chip_pdn_ir | ok | **WORKS*** | 1.05 / 9.47 mV |
| Power | vyges_em_ir | ok | **WORKS*** | 15.1 / 86.0 mV · other mesh |
| Power | dynamic_ir | ok | **WORKS*** | current_run `_direct.json` · gold 45.298 locked on another mesh |
| Power | dse | ok | **WORKS*** | lab only · not a product win |
| Power | power_chain | ok | **WORKS*** | convenience; System PDN is PKG |
| Power | spice_lab | ok | **WORKS** | `INDEX_flowlab.md` |
| Signoff | klayout_drc | ok | **WORKS** | `6_final.gds` on flowlab |
| Signoff | sta_signoff | ok | **WORKS** | WNS −0.02 · TNS −0.14 · 16 viol |
| Signoff | sta_ir_aware | ok | **WORKS*** | educational, not Tempus |
| Signoff | drc_signoff | ok | **WORKS** | 0 route · 0 GDS |
| Signoff | lvs_signoff | ok | **WORKS*** | KLayout match · DFF_X2 must-connect 2 |
| Signoff | power_signoff | ok | **WORKS*** | chip IR; System PDN is PKG |
| Signoff | signoff_all | ok | **WORKS** | four pillars |
| Signoff | eco | ok | **WORKS*** | propose flowlab; apply/close eco_scratch · R2R MET · I/O leftover |
| Signoff | thermal_signoff | ok | **WORKS*** | HotSpot |
| Signoff | pkg_rdl | ok | **WORKS*** | dummy, not C4 |
| Signoff | pkg_signoff | ok | **WORKS*** | bump + RDL + system |
| Signoff | signoff_phase2 | ok | **WORKS** | thermal + PKG |
| GUI | or-web | ok | **WORKS** | `POST /api/viewer` |
| GUI | or-gui | ok | **WORKS*** | DISPLAY + flowlab ODB targets |
| Analysis | yosys_equiv | ok | **WORKS** | Yosys `equiv_*` mapped |
| Analysis | formal_gcd | ok | **WORKS** | Yosys `sat -tempinduct` |
| Analysis | openrcx | ok | **WORKS** | 657 nets |
| Analysis | analytical_pex | ok | **WORKS** | ST + FDM + FasterCap |
| Analysis | ccs_char_report | ok | **WORKS*** | sidecar only |
| Analysis | lvs_deep | ok | **WORKS*** | transistor match · FILL/TAP abstract · DFF_X2 must-connect 2 |
| Analysis | inspect | ok | **WORKS** | flowlab `1_synth.odb` |
| Course | docs | ok | **WORKS** | extended-flow + tool-hooks |

ORFS pipeline UI follows `preferredResultsVariant()` (`flowlab` here).

---

## ASAP7 (Lab)

Predictive FinFET track. Not a product win. Not comparable to gold Dynamic IR
**45.298 mV**. Live GDS only — no ASAP7 gold. Runner:
`python3 learn/scripts/run_asap7_e2e.py`. Plan:
[`docs/asap7_e2e_plan.md`](../../docs/asap7_e2e_plan.md).

| Phase | Status | Evidence | Leftover |
|---|---|---|---|
| Cook (gcd / gcd-ccs / uart) | **WORKS*** when GDS live; else GAP until runner | `results/asap7/<d>/lab_asap7_*/6_final.gds` · folio | 310 ps smoke is open by design |
| Stage ledger (synth→finish) | **WORKS** | `collect_report()["stages"]` · `stopped_at` | — |
| DRC (community KLayout) | **WORKS*** when run | `lab_asap7_drc.json` | not Calibre; via-width rules off |
| LVS (cell-vs-CDL) | **WORKS*** when CDL fetched | `lab_asap7_lvs.json` · `lvs_closed: false` | never `.lvs.ok` · leftover Calibre |
| MMMC pair (setup WC / hold BC) | **WORKS*** on closed finish | `lab_asap7_mmmc.json` | two OpenSTA jobs, not one MMMC session |
| Layer-1 inventory | **WORKS*** when fetched | `lab_asap7_pdk.json` | Calibre decks **GAP** |
| Xyce inverter | **WORKS*** when PDK present | `lab_asap7_spice.json` · level 72→107 | not gold IR |
| 6-track finish | **GAP** | `ASAP7_TRACK=6` refused | second platform (W11) |
| Calibre DRC/LVS | **GAP** | ASU tarball + 2017 license | leftover forever |
| FakeRAM | leftover forever | `riscv32i-mock-sram` not in default plan | blackbox SRAM |
| Product win / course swap | **LOCKED** forbidden | `product_win: false` | — |

---

## What is still not functional (do not fake)

| Leftover | Why it stays |
|---|---|
| Course **0/8** | Student work |
| Course 20% output delay on eco_scratch (`resp_msg[14]`, WNS −0.01) | R2R is MET (~3 ps). Shared NAND2_X2 `_647_` also drives R2R. Size-up / BUF_X4 / clone of that cone regress R2R. Do not rewrite SDC. Locked `flowlab` still has R2R leftover. |
| DFF_X2 must-connect (2) | Nangate split wells; unpin or flatten-all-before-extract breaks match; flatten-after-extract raised count |
| EM `em_checked` 0 | Nangate45 has no foundry `emlimit`. Do not invent one. |
| Density / named ERC | Not in `FreePDK45.lydrc`. Antenna 300:1 is. |
| Official Nangate CCS | `typical.lib` is NLDM |
| CCS on DFF / MUX | Sequential / multi-arc not validated · AOI21/OAI21 combo shipped |
| Board S-parameter | TUHH zip is form-gated |
| Raphael / StarRC | Commercial |
| Magic / Netgen extract | No FreePDK45 `.tech` here |
| sky130 | Different PDK · course pinned |
| Gold Dynamic IR restamp | Forbidden · **45.298 mV** |
