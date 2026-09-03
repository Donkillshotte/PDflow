# Suite / flow status (GCD Nangate45 FlowLab)

Honest snapshot of what runs and what does not. Not a product win list.
Do not mix Product / Lab / Course. Do not mix IR meshes.

Evidence: `learn/sim/reports/*_flowlab.json`, ORFS
`results/nangate45/gcd/flowlab/`, `GET /api/suite`. Course progress is
student work (`0/8`).

Legend:

| Status | Meaning |
|---|---|
| **WORKS** | Ran on this GCD; report `ok` / READY |
| **WORKS*** | Works, with an educational leftover in the note |
| **FAIL** | Ran; honest mismatch or pillar fail |
| **GAP** | Missing tool, commercial, or wrong PDK — not faked |
| **LOCKED** | Must not be restamped / must stay as-is |

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
