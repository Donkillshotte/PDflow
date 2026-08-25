# Lezione 07 — Finish, signoff e GDS

Finish non è “un bottone GDS”. È il **contratto** con STA, LVS e (in azienda) la foundry.

Numeri di un run `learn` completo (SDC 0.46 ns, util 35):

| Stima | worst slack max | Altro |
|---|---|---|
| Liberty / floorplan | +0.04 | fili ≈ 0 |
| Place / resizer | +0.01 | 0 violazioni setup |
| CTS | −0.04 | 32 viol, skew setup ~0 |
| GRT | −0.05 | 43 viol |
| **Finish SPEF** | **−0.04** | TNS **−0.60**, 38 viol, `period_min=0.50` → fmax **~2.01 GHz** |

Il periodo SDC è 0.46 ns ma `period_min` a signoff è 0.50 ns: **non hai chiuso** 2.17 GHz, hai chiuso ~2.01 GHz. Questo è il discorso da mettere nel progetto finale, non “make finish è verde”.

IR drop sul GCD: heatmap `orfs_final_ir_drop.png`, scala circa **0–5.2 mV** (trascurabile; su un core grosso non lo sarebbe).

Worst path overlay: `orfs_final_worst_path.png` (launch ciano, signal rosso, inst viola).

## Obiettivi

- Elencare i deliverable e il destinatario
- Distinguere fill (processo) da logica
- Confrontare le quattro stime di WNS **con i tuoi file**
- Aprire GDS in KLayout e confrontare i layer con Display Control (palette diversa)

## Letture

- Questo README
- `walkthrough-finish.tcl.md` (segue `final_report.tcl` 26Q2)
- LAB 07 + template progetto
- `file-formats.md` SPEF/GDS/DEF
- Atlante §5.10 e §9

## Sottofasi

| Step | Script | Output |
|---|---|---|
| 6_1 fill | `density_fill.tcl` | dummy density |
| 6_report | `final_report.tcl` | `6_final.{odb,def,v,sdc,spef}`, `6_finish.rpt` |
| merge | KLayout `def2stream.py` | `6_final.gds` |

`save_images.tcl` (heatmap in `reports/`) può fallire headless: **non** è il GDS. ORFS 26Q2 su questo ambiente le ha prodotte: copiate in `gui-shots/orfs_*.png`.

Mismatch **ORFS master + OpenROAD 26Q2** → `STA-2204` in save_images. Il repo pinna il tag **26Q2**.

## Cosa fa `final_report.tcl`

1. `set_propagated_clock` + `global_connect` (VDD/VSS sulle celle RSZ/CTS)
2. `write_def` / `write_verilog -remove_cells` (toglie physical-only dal .v)
3. Se `RCX_RULES`: OpenRCX `extract_parasitics` → SPEF → `read_spef`
4. IR drop se `PWR_NETS_VOLTAGES` definito
5. Altrimenti fallback `estimate_parasitics -global_routing`
6. `report_metrics 6 "finish"`
7. `gui::show save_images.tcl` se la GUI è compilata

## Pacchetto signoff

| File | Destinatario | Se manca |
|---|---|---|
| `6_final.gds` | mask / viewer | non hai geometria fab |
| `6_final.def` | ECO / tool terzi | niente coordinate testuali |
| `6_final.spef` | STA | resti sulle stime |
| `6_final.sdc` | STA | vincoli non allineati |
| `6_final.v` | LVS / sim | netlist ≠ synth (buffer, fill esclusi se `-remove_cells`) |
| `6_finish.rpt` | tu | non sai se hai chiuso il timing |

Senza SPEF stai stimando. Con SPEF sei nel mondo post-route.

## Fill

Fill **non** cambia la funzione. Cambia densità CMP e un po’ i parassiti. Find `FILLCELL` in GUI final.

## GUI e KLayout

- `gui_final` — anatomia A–G, `select clk`, worst path PNG
- `klayout 6_final.gds` — F = fit; i colori **non** coincidono con Qt

## Progetto finale

Senza `learn/workbook/mio-progetto-finale.md` il corso **non è finito**, anche se `make finish` è verde.

## Durata

README+walkthrough 50 min, LAB 90 min, progetto 60 min, **totale ~3 ore**.
