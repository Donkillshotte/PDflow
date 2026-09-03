# Suite / flow status (GCD Nangate45 FlowLab)

Honest snapshot of what runs and what does not. Not a product win list.
Do not mix Product / Lab / Course. Do not mix IR meshes.

Evidence: `learn/sim/reports/*_flowlab.json`, ORFS
`results/nangate45/gcd/flowlab/`, `GET /api/suite`. Course progress is
student work (`0/8`).

Live `GET /api/suite` on this Cloud VM: **35 / 46** hooks `ok`,
`lessonsDone` **0 / 8**, `pipelineReady` **0**. Several Studio hooks
look at `results/.../gcd/learn/` (empty here) instead of
`gcd/flowlab/` — those are **UI false-negatives**, not missing cooks.
`dynamic_ir` is also false in the UI because the gold JSON has no
`ok: true` field (it is **LOCKED**, not missing).

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

`GET /api/suite` is **35 / 46**. Several hooks look at
`results/nangate45/gcd/learn/` (empty on this VM) instead of
`gcd/flowlab/` where the real cook lives.

| Looks broken in Studio | Reality |
|---|---|
| synth / pdn / finish / inspect / klayout_drc / pipelineReady 0 | ODBs and GDS are on disk under `flowlab/` |
| dynamic_ir hook `ok=false` | Gold file is present and **LOCKED** at 45.298 mV; it has no `ok` field |
| or-gui | DISPLAY is up; Qt targets also look at `learn/` |

These are UI path bugs, not missing RTL→GDS.

### 2. The only flow step that ran and failed: LVS

KLayout compared the GDS transistors to the CDL schematic and printed
`Netlists don't match`. That is why `signoff_all` is FAIL (timing,
geometry, and power already pass).

Root leftover after we filtered unused library cells (TBUF/TLAT flatten
is now **0**):

- Extracted cells expose extra well pins (`NWELL|VDD`, `PWELL`) that
  the official CDL does not list as ports.
- `FILLCELL_*` / `TAPCELL_*` CDL is pins-only (empty body). OpenROAD
  `6_final.cdl` also omits fills. Layout still has them →
  "Flatten layout cell (no schematic)".

We do **not** write `.lvs.ok` on a black-box-only or filtered fake
match. Deep LVS (`lvs_deep`) is the same FAIL, documented.

### 3. Real GAPs — missing data or a tool we will not pretend to be

| What you might expect | What we have | Why it stays missing |
|---|---|---|
| Foundry / Si2 **CCS liberty** on every Nangate cell | Official `typical.lib` is **NLDM** (delay/slew tables only). We re-characterized **9 combinational GCD cells** with PTM+ngspice (`output_current`). No DFF/MUX/AOI. | The 2008 CCS views are in the Si2 tarball (form), not the public ORFS drop. A PTM sidecar is not that file. |
| **StarRC / Raphael** full-chip parasitics | OpenRCX SPEF (657 nets) + 2-wire FasterCap BEM | Those two are Synopsys commercial. No license → no fake SPEF. |
| Board **S-parameter** (Touchstone `.sNp`) | Lumped VRM→board→pkg ladder in ngspice (droop 6.27 mV) | Public TUHH SI/PI decks are form-gated. Exporting the lump as `.sNp` would be a lie. |
| **Magic + Netgen** LVS/extract on this GCD | KLayout DRC/LVS | `magic` / `netgen` are not in PATH here, and there is no verified FreePDK45 Magic `.tech`. |
| **sky130** course | Nangate45 only | Different PDK. Mixing it into this course is forbidden. |
| Tapeout **C4 bumps / RDL** | Dummy bump LEF + sidecar `rdl_route` (4 bumps, 36 wires) | Educational OpenROAD pad test, not a package foundry. |
| **PrimeTime / Tempus / Voltus** | OpenSTA + PDNSim + Xyce N4 compact | We do not claim sign-off equivalence. |
| Course **8/8** | **0/8** | Student pace. Do not stamp `.progress.json`. |
| A new gold Dynamic IR | **45.298 mV** stays | current_run (~6.075) and chip PDN (28.3) are other meshes. Never restamp gold. |

**WORKS\*** in the tables below means: the script ran and the number is
real, but it is not the commercial / foundry object with the same name.

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
| Synth (`1_synth.odb`) | **WORKS** | ODB on disk | Some Studio hooks look at another results path and show false-negative |
| Floorplan | **WORKS** | `2_floorplan.odb` | — |
| Place | **WORKS** | `3_place.odb` | — |
| CTS | **WORKS** | `4_cts.odb` | — |
| Route | **WORKS** | `5_route.odb` | — |
| Finish (GDS / SPEF / CDL) | **WORKS** | `6_final.gds` `.spef` `.v` `.odb` | Do not overwrite `gcd/flowlab/` |

---

## Signoff pillars

| Step | Status | Evidence | Leftover |
|---|---|---|---|
| STA | **WORKS** | WNS −0.02 ns · TNS −0.14 · 3 viol | Educational Nangate, not PrimeTime |
| STA IR-aware | **WORKS*** | `sta_ir_aware` ok · NLDM × ITerm V | Does not change official WNS |
| DRC (route + GDS) | **WORKS** | 0 route lines · 0 GDS items | — |
| LVS (KLayout) | **FAIL** | `Netlists don't match` · no `.lvs.ok` | Well pins `NWELL\|VDD`; empty FILL/TAP CDL |
| LVS deep (filter + VTL) | **FAIL** | unused flatten 0 · transistor FAIL · black-box FAIL | Same leftover; not a fake pass |
| Power signoff | **WORKS*** | Chip IR 3.09 mV · sys droop 6.27 mV · Zmax 9.06 Ω | Lumped board, not S-parameter |
| `signoff_all` | **FAIL** | timing/geometry/power ok · LVS fail | Stays fail while LVS fails |

---

## Sim · activity · IR (do not mix numbers)

| Step | Status | Evidence | Leftover |
|---|---|---|---|
| RTL sim (Icarus) | **WORKS** | `rtl_sim` · `gcd.vcd` | Ports only for IR name-join |
| Gate sim + name-join | **WORKS** | `GATE_SIM_PASS` · `gcd_gate.vcd` | Functional GLS, no SDF |
| Activity → power | **WORKS** | `activity_power` / vectorless report | Prefer gate VCD scope |
| Vectorless | **WORKS*** | P=4.9 mW · I_avg=4.45 mA | Report still says `missing_vcd` vs dynamic |
| Chip PDN (PDNSim mesh) | **WORKS*** | static **3.09 mV** · transient **28.3 mV** | Not gold Dynamic IR |
| vyges-em-ir | **WORKS*** | static 15.1 mV · droop 86.0 mV | Different mesh from 3.09 / 28.3 |
| Dynamic IR **gold** | **LOCKED** | **45.298 mV** · `gold: true` | Never restamp |
| Dynamic IR current_run | **WORKS*** | ~**6.075 mV** | Not gold; not chip 28.3 |
| System PDN | **WORKS*** | droop 6.27 mV · Zmax 9058 mΩ | Lumped VRM→board→pkg. No Touchstone |
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
| PTM CCS sidecar | **WORKS*** | 9 GCD cells · 18 `output_current` tables · INV_X1 16.1 ps vs NLDM 19.2 ps | Re-char, not 2008 Nangate CCS; no DFF |
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
| Yosys equiv (EQY-class) | **WORKS** | RTL ↔ generic-synth PASS | CLI `eqy` absent (mapped) |
| Formal SAT (sby-class) | **WORKS** | `reset → !resp_val` PASS | CLI `sby` absent (mapped) |

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
| Gold Dynamic IR | **45.298 mV** | current_run 6.075 · chip PDN 28.3 |
| Chip PDN static / transient | **3.09 / 28.3 mV** | gold · vyges mesh |
| System PDN droop | **6.27 mV** | chip transient |
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
| Environment | ccs_char | ok | **WORKS*** | 9 cells · official lib NLDM |
| Environment | display | ok | **WORKS** | `DISPLAY :1` |
| Environment | spice_engines | ok | **WORKS** | ngspice + Xyce N4 |
| Frontend | rtl | ok | **WORKS** | `gcd.v` |
| Frontend | rtl_sim | ok | **WORKS** | `gcd.vcd` |
| Frontend | gate_sim | ok | **WORKS** | `GATE_SIM_PASS` |
| PD | synth | no | **WORKS** | FN · `flowlab/1_synth.odb` exists |
| PD | pdn | no | **WORKS** | FN · `flowlab/2_4_floorplan_pdn.odb` |
| PD | finish | no | **WORKS** | FN · `flowlab/6_final.gds` |
| Power | gridcheck | no | **WORKS*** | PDN ODB exists · no `.gridcheck_pdn.ok` stamp |
| Power | system_pdn | ok | **WORKS*** | droop 6.27 mV · no Touchstone |
| Power | activity | ok | **WORKS** | gate VCD preferred |
| Power | vectorless | ok | **WORKS*** | label still `missing_vcd` |
| Power | chip_pdn_ir | ok | **WORKS*** | 3.09 / 28.3 mV |
| Power | vyges_em_ir | ok | **WORKS*** | 15.1 / 86.0 mV · other mesh |
| Power | dynamic_ir | no | **LOCKED** | gold 45.298 · JSON has no `ok` |
| Power | dse | ok | **WORKS*** | lab only · not a product win |
| Power | power_chain | ok | **WORKS** | activity → chip → system |
| Power | spice_lab | ok | **WORKS** | `INDEX_flowlab.md` |
| Signoff | klayout_drc | no | **WORKS** | FN · signoff DRC 0 |
| Signoff | sta_signoff | ok | **WORKS** | WNS −0.02 · TNS −0.14 · 3 viol |
| Signoff | sta_ir_aware | ok | **WORKS*** | educational, not Tempus |
| Signoff | drc_signoff | ok | **WORKS** | 0 route · 0 GDS |
| Signoff | lvs_signoff | no | **FAIL** | `Netlists don't match` |
| Signoff | power_signoff | ok | **WORKS*** | lumped board |
| Signoff | signoff_all | no | **FAIL** | LVS pillar |
| Signoff | thermal_signoff | ok | **WORKS*** | HotSpot |
| Signoff | pkg_rdl | ok | **WORKS*** | dummy, not C4 |
| Signoff | pkg_signoff | ok | **WORKS*** | bump + RDL + system |
| Signoff | signoff_phase2 | ok | **WORKS** | thermal + PKG |
| GUI | or-web | ok | **WORKS** | `POST /api/viewer` |
| GUI | or-gui | no | **WORKS*** | DISPLAY ok · Qt targets look at `learn/` |
| Analysis | yosys_equiv | ok | **WORKS** | EQY-class mapped |
| Analysis | formal_gcd | ok | **WORKS** | sby-class mapped |
| Analysis | openrcx | ok | **WORKS** | 657 nets |
| Analysis | analytical_pex | ok | **WORKS** | ST + FDM + FasterCap |
| Analysis | ccs_char_report | ok | **WORKS*** | sidecar only |
| Analysis | lvs_deep | ok | **FAIL** | report exists · transistor FAIL |
| Analysis | inspect | no | **WORKS** | FN · looks at `learn/1_synth.odb` |
| Course | docs | ok | **WORKS** | extended-flow + tool-hooks |

ORFS pipeline UI (`pipelineReady 0`) is the same `learn/` path issue.
Physical stages synth → finish are **WORKS** on `flowlab/`.

---

## What is still not functional (do not fake)

| Leftover | Why it stays |
|---|---|
| Course **0/8** | Student work |
| Official LVS / `signoff_all` | Well ports + empty FILL/TAP CDL |
| Official Nangate CCS | `typical.lib` is NLDM |
| CCS on DFF / MUX / AOI / OAI | Sequential / multi-arc not validated |
| Board S-parameter | TUHH zip is form-gated |
| Raphael / StarRC | Commercial |
| Magic / Netgen extract | No FreePDK45 `.tech` here |
| sky130 | Different PDK · course pinned |
| Gold Dynamic IR restamp | Forbidden · **45.298 mV** |
