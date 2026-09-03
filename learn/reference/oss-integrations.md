# OSS integrations (GCD Nangate45)

Honest matrix: every requested tool is **INTEGRATED**, **MAPPED** (equivalent OSS in the student flow), **PARTIAL**, or **GAP**. The course is pinned to **Nangate45 / FreePDK45** — not Sky130.

Legend:

| Status | Meaning |
|---|---|
| **INTEGRATED** | Binary + Studio script + verified run on GCD |
| **MAPPED** | Dedicated binary absent; same role covered by OSS engine already in path |
| **PARTIAL** | Binary present, but PDK/tech incompatible with Nangate45 |
| **GAP** | Commercial or wrong PDK — integration is not faked |

Studio actions: `gate_sim`, `vectorless`, `yosys_equiv`, `formal_gcd`, `openrcx_report`, `analytical_pex`, `layout_tools`, `spice_engines`, `vyges_em_ir`, `dynamic_ir`, `thermal_signoff`, `pkg_rdl`, `tool_matrix`.

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_tool_matrix.sh
```

---

## Tool matrix

| Tool | Status | Role on the GCD | Evidence | Equivalent if not INTEGRATED |
|---|---|---|---|---|
| **Yosys** | INTEGRATED | ORFS synth + `stat` inspect + **equiv RTL↔synth** | `yosys -V` 0.63 · action `yosys_equiv` · `sim/reports/yosys_equiv_flowlab.json` | — |
| **KLayout** | INTEGRATED | DRC/LVS signoff + GDS viewer | `klayout -v` · `drc_signoff` / `klayout_lvs` | — |
| **Magic** | PARTIAL | Installed (8.3); default tech `minimum` | action `layout_tools` · no FreePDK45 `.tech` | Layout signoff = **KLayout** |
| **Netgen** | PARTIAL | `netgen-lvs` 1.5.133 in PATH | same probe; no Nangate setup | LVS signoff = **KLayout** `FreePDK45.lylvs` |
| **EQY** | MAPPED | CLI `eqy` absent | Yosys `equiv_make` / `equiv_induct` / `equiv_status` | Same engine as EQY |
| **SymbiYosys (`sby`)** | MAPPED | CLI `sby` absent; **z3** present | Yosys `sat -tempinduct` on `reset \|-> resp_val=0` | Same SAT/BMC backend |
| **ngspice** | INTEGRATED | System PDN AC+TRAN + demo | `ngspice -v` 42 · `system_pdn` · `spice_engines` | — |
| **Xyce (Sandia)** | INTEGRATED (when `install_xyce.sh` succeeds) | Dual-solver N4 compact VRM+pkg+die | `spice_engines_*.json` `xyce_status: READY` · `xyce_vrm_die_gold` | **ngspice** still covers System PDN AC/TRAN |
| **OpenRCX** | INTEGRATED | Inside OpenROAD (`extract_parasitics`) | `6_final.spef` + `rcx_patterns.rules` · action `openrcx_report` | — |
| **FasterCap** | INTEGRATED (when `install_fastercap.sh` succeeds) | 3D BEM 2-wire extract vs Sakurai–Tamaru + FDM | `analytical_pex_*.json` `fastercap.status: READY` | Raphael remains commercial GAP |
| **Raphael** | GAP | Synopsys commercial, no license | documented | OpenRCX SPEF + analytical PEX |
| **StarRC** | GAP | Synopsys commercial, no license | documented | **OpenRCX** SPEF at finish |
| **open_pdks** | GAP | Sky130 / gf180, **different PDK** | course pinned to Nangate45 | Not mixed with FreePDK45 |
| **vyges-em-ir** | INTEGRATED | static IR CG + transient BE on the mesh `write_pg_spice` | action `vyges_em_ir` · `sim/reports/vyges_em_ir_flowlab.json` · binary v0.1.33 | — |
| **dynamic_ir (this course)** | INTEGRATED | I(t) per ITerm + Solver A LU gold + **Solver B SA-AMG** + scenarios on shared A | action `dynamic_ir` · `sim/reports/dynamic_ir_flowlab.json` + `.svg` | — |

---

## Formal / equiv (EQY · sby)

| Check | Script | Property |
|---|---|---|
| Equiv | `learn/scripts/run_yosys_equiv.sh` | RTL GCD ≡ `synth -top gcd` (sequential induction) |
| Safety | `learn/scripts/run_formal_gcd.sh` | `reset=1` ⇒ `resp_val=0` (`sat -tempinduct`) |
| sby wrapper | `learn/formal/gcd_safety.v` | ready if you install `sby` |

---

## PEX (OpenRCX · FasterCap · Raphael · StarRC)

Finish ORFS already calls OpenRCX if `RCX_RULES` is set (`platforms/nangate45/rcx_patterns.rules`). The `openrcx_*.json` report counts `*D_NET` / `*CAP` / `*RES` on the real SPEF.

FasterCap/Raphael do not extract full-chip: the tutorial 2-wire (`run_analytical_pex.py`) gives Cg/Cc in fF on M2 FreePDK45-like geometry, comparable in order of magnitude to SPEF.

---

## Layout (Magic · Netgen · KLayout · open_pdks)

KLayout is the only course **signoff** tool on this PDK (vendored runset `learn/platforms/nangate45/lvs/FreePDK45.lylvs`). Magic/Netgen remain probes: useful on Sky130 via open_pdks, not on Nangate45.

---

## Power: vectorless + dynamic

See [vectorless-power.md](./vectorless-power.md). OpenSTA 26Q2: use `read_vcd`, **not** `read_power_activities` (broken arity).

Apache-2.0 IR/EM engine on the same mesh: [vyges-em-ir.md](./vyges-em-ir.md) (real binary, not a reimplementation).
I(t) per pin + waveform + heatmap: [dynamic-ir.md](./dynamic-ir.md). OSS landscape: [dynamic-ir-landscape.md](./dynamic-ir-landscape.md).

---

## Verification

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_tool_matrix.sh
test -f learn/sim/reports/vectorless_flowlab.json
test -f learn/sim/reports/yosys_equiv_flowlab.json
test -f learn/sim/reports/vyges_em_ir_flowlab.json
test -f learn/sim/reports/dynamic_ir_flowlab.json
test -f learn/platforms/nangate45/lvs/FreePDK45.lylvs
```

Cross-ref: [signoff-matrix.md](./signoff-matrix.md) · [extended-flow.md](./extended-flow.md) · [tool-hooks.md](./tool-hooks.md) · [gap-close-paths.md](./gap-close-paths.md) (how to close labeled GAPs without mocks)
