# Lezione 06 — Routing

Routing è il passaggio da “celle con pin” a “fili che la fabbrica può stampare”.

Sul GCD `learn` il timing **peggiora** quando i fili diventano veri:

| Stadio | worst slack max | setup viol | Commento |
|---|---|---|---|
| Detailed place | **+0.01 ns** | 0 | stima placement, ottimistica |
| CTS final | **−0.04 ns** | 32 | clock propagato |
| Global route | **−0.05 ns** | 43 | RC da **guide** |
| Finish SPEF | **−0.04 ns** | 38 | estrazione; TNS −0.60 |

Non “aggiustare i numeri a mano”: capisci **perché** il segno cambia. GRT vede congestione e lunghezza di corridoio; SPEF vede RC geometrica.

## Obiettivi

- Distinguere guide GRT da wire DRT (stessa net, due ODB)
- Leggere congestion heatmap (`orfs_final_congestion.png`)
- Capire perché DRT **abortisce** senza `grt::have_routes`
- Antenna a livello concettuale + loop in `detail_route.tcl`

## Letture

- Questo README
- `walkthrough-route.tcl.md`
- LAB 06
- Atlante §2, §5.8–5.9, §9

## Due problemi diversi

**Global routing:** assegnare fasce (risorse 2D / gcell) minimizzando overflow. Output: `route.guide` (migliaia di righe sul GCD).

**Detailed routing:** geometria mask: width, spacing, via, enclosure. Output: metal in ODB + `5_route_drc.rpt` (0 righe = clean sul nostro GCD).

DRT senza guide è asfaltare senza tracciato: `detail_route.tcl` riga 5–8 esce con errore e ti manda a `make gui_grt`.

## Sottofasi ORFS

| Step | Output | Cosa succede al timing |
|---|---|---|
| 5_1_grt | GRT + `estimate_parasitics -global_routing` + repair incrementale | slack più onesta del place |
| 5_2_route | TritonRoute + `repair_antennas` eventuale re-route | geometria; STA ancora senza SPEF |
| 5_3_fillcell | fill post-route | densità processo |

GRT **ripara ancora il timing** perché le guide sono un modello RC migliore del placement. Poi DPL incrementale + `global_route -start_incremental` / `-end_incremental` ri-routa solo le net toccate.

## Layer Nangate45 in *questa* GUI

| Layer | Colore Qt 26Q2 | Ruolo tipico GCD |
|---|---|---|
| metal1 | blu | rail + pin locali |
| metal2 | rosso | segnale |
| metal3 | verde | segnale, direzione opposta |
| metal4/7 | giallo / rosa | PDN strap |

Esercizio: solo M2, poi solo M3 (`gui-atlas` Tcl). Direzione dominante deve cambiare.

## Congestion

Heatmap `orfs_final_congestion.png`: griglia gcell, verde = aria, rosso = pieno. Sul GCD il centro è caldo, i bordi freddi: coerente col blob di placement.

Se GRT non converge: `5_1_grt-failed.odb` + congestion report. Fix: meno density, più util headroom, meno buffer (SDC).

## Antenna

Durante etch, un filo lungo su un gate è un condensatore che si carica. `repair_antennas` inserisce diodi; poi **ri-esegue** `detailed_route`. Log: `drt_antennas.log`. Non serve la fisica del plasma: serve sapere che ORFS può **iterare**.

`DETAILED_ROUTE_END_ITERATION` / `DETAILED_ROUTE_ARGS -droute_end_iter 5`: ferma TritonRoute presto per debug (commento in `detail_route.tcl` righe 30–42).

## File

| File | Se vuoto / non vuoto |
|---|---|
| `route.guide` | deve essere grande |
| `5_route_drc.rpt` | vuoto = DRC clean (GCD) — vedi anche [`drc_signoff`](../../reference/signoff-matrix.md) unificato post-finish |
| `5_global_route.rpt` | overflow + slack GRT |
| `maze.log` | debug DRT |

## GUI

1. `gui_5_1_grt.odb` — `win_grt.png`, `07_grt.png`
2. `gui_5_2_route.odb` — `08_route_labeled.png`, isola M2/M3

## Catena power & SPICE

Il routing completa la geometria per IR/SPEF. PDNSim usa il design **post-route/finish**. Vedi [`spice-power-chain.md`](../../reference/spice-power-chain.md#lezione-06-routing).

| Collegamento | Dove |
|---|---|
| FlowLab | [route](/flusso?phase=route) |

## Durata

README+walkthrough 50–70 min, LAB 90–120 min, **totale ~3 ore**.
