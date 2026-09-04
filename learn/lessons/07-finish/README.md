# Lesson 07 — Finish, signoff, and GDS

Finish is not “a GDS button”. It is the **contract** with STA, LVS, and (in industry) the foundry.

Numbers from a complete `learn` run (SDC 0.46 ns, util 35):

| Estimate | worst slack max | Other |
|---|---|---|
| Liberty / floorplan | +0.04 | wires ≈ 0 |
| Place / resizer | +0.01 | 0 setup violations |
| CTS | −0.04 | 32 viol, skew setup ~0 |
| GRT | −0.05 | 43 viol |
| **Finish SPEF** | **−0.04** | TNS **−0.60**, 38 viol, `period_min=0.50` → fmax **~2.01 GHz** |
| **OpenSTA signoff** | **−0.02** | TNS **−0.14**, **16 viol** (`engine: opensta`). Not the finish report. |

The SDC period is 0.46 ns but `period_min` at ORFS finish is 0.50 ns: **you have not closed** 2.17 GHz, you closed ~2.01 GHz. OpenSTA signoff on the same SPEF lists every negative-slack path (16), not the finish-report 38. This is the narrative to put in the final project, not “make finish is green”.

IR is not one number. The ORFS finish heatmap (`orfs_final_ir_drop.png`)
is a PDNSim picture — not gold Dynamic IR **45.298 mV**, not chip PDN
(1.05 / 9.47 mV), and not current_run I(t) (~6.08 mV). Those meshes are
stamped in `power_signoff_*.json` (`comparable: false`). EM `em_checked`
is 0 (no foundry `emlimit`). FlowLab finish shows the ledger at `#ir`.

Worst path overlay: `orfs_final_worst_path.png` (launch cyan, signal red, inst purple).

## Objectives

- List deliverables and their recipient
- Distinguish fill (process) from logic
- Compare the four WNS estimates **with your files**
- Open GDS in KLayout and compare layers with Display Control (different palette)

## Reading

- This README
- `walkthrough-finish.tcl.md` (follows `final_report.tcl` 26Q2)
- LAB 07 + project template
- `file-formats.md` SPEF/GDS/DEF
- Atlas §5.10 and §9

## Sub-stages

| Step | Script | Output |
|---|---|---|
| 6_1 fill | `density_fill.tcl` | dummy density |
| 6_report | `final_report.tcl` | `6_final.{odb,def,v,sdc,spef}`, `6_finish.rpt` |
| merge | KLayout `def2stream.py` | `6_final.gds` |

`save_images.tcl` (heatmap in `reports/`) may fail headless: that is **not** the GDS. ORFS 26Q2 on this environment produced them: copied to `gui-shots/orfs_*.png`.

Mismatch **ORFS master + OpenROAD 26Q2** → `STA-2204` in save_images. The repo pins the tag **26Q2**.

## What `final_report.tcl` does

1. `set_propagated_clock` + `global_connect` (VDD/VSS on RSZ/CTS cells)
2. `write_def` / `write_verilog -remove_cells` (removes physical-only from .v)
3. If `RCX_RULES`: OpenRCX `extract_parasitics` → SPEF → `read_spef`
4. IR drop if `PWR_NETS_VOLTAGES` defined
5. Otherwise fallback `estimate_parasitics -global_routing`
6. `report_metrics 6 "finish"`
7. `gui::show save_images.tcl` if the GUI is compiled

## Signoff package

| Files | Recipient | If missing |
|---|---|---|
| `6_final.gds` | mask / viewer | you have no fab geometry |
| `6_final.def` | ECO / third-party tools | no textual coordinates |
| `6_final.spef` | STA | stay on estimates |
| `6_final.sdc` | STA | misaligned constraints |
| `6_final.v` | LVS / sim | netlist ≠ synth (buffers, fill excluded if `-remove_cells`) |
| `6_finish.rpt` | you | you do not know if timing is closed |

Without SPEF you are estimating. With SPEF you are in post-route world.

## Fill

Fill does **not** change function. It changes CMP density and parasitics slightly. Find `FILLCELL` in GUI final.

## GUI and KLayout

- `gui_final` — anatomy A–G, `select clk`, worst path PNG
- `klayout 6_final.gds` — F = fit; colors **do not** match Qt

## Final project

Without `learn/workbook/my-final-project.md` the course **is not finished**, even if `make finish` is green.

## Signoff 4 pillars (Phase 1)

Registry and matrix: [`signoff-matrix.md`](../../reference/signoff-matrix.md).

| Pillar | Action Studio | Script |
|---|---|---|
| Timing (STA) | `sta_signoff` | `run_sta_signoff.sh` |
| Timing (STA IR-aware) | `sta_ir_aware` | `run_sta_ir_aware.sh` |
| Geometry (DRC) | `drc_signoff` | `run_drc_signoff.sh` |
| Equivalence (LVS) | `klayout_lvs` | `run_klayout_lvs.sh` |
| Power | `power_signoff` | `run_power_signoff.sh` |
| All | `signoff_all` | `run_signoff_all.sh` |

FlowLab **finish** phase shows the matrix vs `golden-gcd.json`. LVS is a
KLayout compare (filtered CDL + well→VDD/VSS + FILL/TAP `blank_circuit`).
Read the report, including remaining DFF_X2 must-connect warnings.
Educational FreePDK45, not foundry LVS.

After signoff, ECO propose is allowed on `flowlab`. Apply only on an
unlocked copy (`FLOW_VARIANT` not in flowlab/learn/base). Apply loads
SPEF, then size-only repair. BufferMove is unsafe on this finished ODB
(SIGSEGV without GRT, RSZ-0074 with GRT). Size-up fails TritonRoute
connectivity; apply restores the source `6_final` and names leftover.
Then run `FLOW_VARIANT=<copy> ./learn/scripts/run_signoff_all.sh`. DSE
does not run that script.

## Power & SPICE chain (recommended post-course module)

Finish produces `6_final.odb`, IR heatmap, and enables the full **SPICE chain**:

1. `activity_power` → I_avg  
2. `chip_pdn_ir` → mesh `write_pg_spice`  
3. `vyges_em_ir` → CG engine + backward Euler on the same mesh  
4. `dynamic_ir` → I(t) per pin + heatmap t_worst  
5. `system_pdn` → ngspice ladder  
6. `power_chain` → all steps + lab export  

Master guide: [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-07-finish) · Hub [PKG](/pkg) · FlowLab [finish](/flow?phase=finish).

```bash
FLOW_VARIANT=learn ./learn/scripts/run_power_chain.sh   # after make finish
FLOW_VARIANT=flowlab ./learn/scripts/run_power_chain.sh # FlowLab variant
```

## Duration

README+walkthrough 50 min, LAB 90 min, project 60 min, **total ~3 hours**.
