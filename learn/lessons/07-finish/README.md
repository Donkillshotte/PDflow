# Lesson 07 — Finish, signoff e GDS

Finish is not “un GDS button”. Is il **contract** with STA, LVS e (in industry) la foundry.

Numbers from a run `learn` completo (SDC 0.46 ns, util 35):

| Stima | worst slack max | Altro |
|---|---|---|
| Liberty / floorplan | +0.04 | wires ≈ 0 |
| Place / resizer | +0.01 | 0 setup violations |
| CTS | −0.04 | 32 viol, skew setup ~0 |
| GRT | −0.05 | 43 viol |
| **Finish SPEF** | **−0.04** | TNS **−0.60**, 38 viol, `period_min=0.50` → fmax **~2.01 GHz** |

Il SDC period is 0.46 ns ma `period_min` a signoff is 0.50 ns: **you have not chiuso** 2.17 GHz, you closed ~2.01 GHz. This is il discourse da mettere nel final project, non “make finish is green”.

IR drop on the GCD: heatmap `orfs_final_ir_drop.png`, scala about **0–5.2 mV** (negligible; on a large core it would not be).

Worst path overlay: `orfs_final_worst_path.png` (launch cyan, signal rosso, inst purple).

## Objectives

- List deliverables e il recipient
- Distinguere fill (processo) da logica
- Confrontare le four WNS estimates **con i tuoi file**
- Aprire GDS in KLayout e confrontare i layer con Display Control (different palette)

## Reading

- This README
- `walkthrough-finish.tcl.md` (follows `final_report.tcl` 26Q2)
- LAB 07 + project template
- `file-formats.md` SPEF/GDS/DEF
- Atlas §5.10 e §9

## Sub-stages

| Step | Script | Output |
|---|---|---|
| 6_1 fill | `density_fill.tcl` | dummy density |
| 6_report | `final_report.tcl` | `6_final.{odb,def,v,sdc,spef}`, `6_finish.rpt` |
| merge | KLayout `def2stream.py` | `6_final.gds` |

`save_images.tcl` (heatmap in `reports/`) may fail headless: **non** is il GDS. ORFS 26Q2 su this ambiente le ha prodotte: copied to `gui-shots/orfs_*.png`.

Mismatch **ORFS master + OpenROAD 26Q2** → `STA-2204` in save_images. Il repo pins the tag **26Q2**.

## What it does `final_report.tcl`

1. `set_propagated_clock` + `global_connect` (VDD/VSS on the cells RSZ/CTS)
2. `write_def` / `write_verilog -remove_cells` (removes physical-only dal .v)
3. Se `RCX_RULES`: OpenRCX `extract_parasitics` → SPEF → `read_spef`
4. IR drop se `PWR_NETS_VOLTAGES` definito
5. Altrimenti fallback `estimate_parasitics -global_routing`
6. `report_metrics 6 "finish"`
7. `gui::show save_images.tcl` se the GUI is compilata

## Signoff package

| Files | Recipient | If missing |
|---|---|---|
| `6_final.gds` | mask / viewer | you have not geometria fab |
| `6_final.def` | ECO / tool terzi | niente coordinate testuali |
| `6_final.spef` | STA | stay on estimates |
| `6_final.sdc` | STA | misaligned constraints |
| `6_final.v` | LVS / sim | netlist ≠ synth (buffer, fill esclusi se `-remove_cells`) |
| `6_finish.rpt` | tu | you do not know if timing is closed |

Senza SPEF stai stimando. With SPEF you are in post-route world.

## Fill

Fill **non** cambia the function. Cambia CMP density e un po’ i parasitics. Find `FILLCELL` in GUI final.

## GUI e KLayout

- `gui_final` — anatomia A–G, `select clk`, worst path PNG
- `klayout 6_final.gds` — F = fit; colors **do not** match Qt

## Final project

Senza `learn/workbook/mio-progetto-finale.md` the course **is not finito**, even if `make finish` is green.

## Signoff 4 pilastri (Fase 1)

Registry and matrix: [`signoff-matrix.md`](../../reference/signoff-matrix.md).

| Pillar | Action Studio | Script |
|---|---|---|
| Timing (STA) | `sta_signoff` | `run_sta_signoff.sh` |
| Geometry (DRC) | `drc_signoff` | `run_drc_signoff.sh` |
| Equivalence (LVS) | `klayout_lvs` | `run_klayout_lvs.sh` |
| Power / PKG | `power_signoff` | `run_power_signoff.sh` |
| All | `signoff_all` | `run_signoff_all.sh` |

FlowLab fase **finish** shows the matrix con gate vs `golden-gcd.json`. LVS su FreePDK45 may FAIL — interpret the report.

## Power & SPICE chain (modulo post-course recommended)

Finish produce `6_final.odb`, heatmap IR e enables the full **SPICE chain**:

1. `activity_power` → I_avg  
2. `chip_pdn_ir` → mesh `write_pg_spice`  
3. `vyges_em_ir` → engine CG + backward Euler on the same mesh  
4. `dynamic_ir` → I(t) per pin + heatmap t_worst  
5. `system_pdn` → ngspice ladder  
6. `power_chain` → tutto + export lab  

Guide master: [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-07-finish) · Hub [PKG](/pkg) · FlowLab [finish](/flusso?phase=finish) · [PKG phase](/flusso?phase=pkg).

```bash
FLOW_VARIANT=learn ./learn/scripts/run_power_chain.sh   # after make finish
FLOW_VARIANT=flowlab ./learn/scripts/run_power_chain.sh # FlowLab variant
```

## Duration

README+walkthrough 50 min, LAB 90 min, project 60 min, **total ~3 hours**.
