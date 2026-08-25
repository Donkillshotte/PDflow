# Soluzioni workbook — confronta **dopo** aver provato

Numeri della colonna «riferimento» = run `learn` su questa VM
(`CORE_UTILIZATION=35`, SDC 0.46 ns, OpenROAD/ORFS **26Q2**).
Tabella maestra: [golden-metrics.md](../reference/golden-metrics.md).

I tuoi valori possono scostarsi di pochi percento. Se scarto > 20% su celle/area,
hai sbagliato variant, SDC o PDK — apri il [debug-playbook](../reference/debug-playbook.md).

---

## A1 — I/O delay

`0.46 × 0.2 = 0.092 ns` sia in input sia in output.

Nel file: `set_input_delay` / `set_output_delay` usano `[expr $clk_period * $clk_io_pct]`.

## A2 — Sweep clock (fino a `place`)

Procedura (un SDC alla volta; **ripristina** il default alla fine):

```bash
cp learn/designs/nangate45/gcd-tutorial/constraint.sdc \
   learn/workbook/backup-sdc-default.sdc
cd tools/OpenROAD-flow-scripts/flow
# per ogni file SDC:
cp ../../../../learn/designs/nangate45/gcd-tutorial/constraint_relaxed.sdc \
   ../../../../learn/designs/nangate45/gcd-tutorial/constraint.sdc
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 \
     clean_synth clean_floorplan clean_place
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 synth floorplan place
rg -n 'worst slack|Inserted|period_min' \
  reports/nangate45/gcd/learn/3_resizer.rpt \
  logs/nangate45/gcd/learn/3_4_place_resized.log | head
```

| SDC | Periodo | Cosa attenderti a place (qualitativo) | Default `learn` (0.46 ns) |
|---|---|---|---|
| relaxed | 2.0 ns | WNS largo positivo, pochi buffer RSZ | — |
| default | 0.46 ns | worst slack **+0.01 ns**, `period_min` **0.45 ns**, area **684 µm² / 40%** | questa riga |
| tight | 0.25 ns | più buffer/upsize; CTS può fare **DPL-0038** dopo | non è la riga d’oro |

Osservazione: clock più stretto → più lavoro RSZ → più area sullo **stesso** core.

Ripristino:

```bash
cp learn/workbook/backup-sdc-default.sdc \
   learn/designs/nangate45/gcd-tutorial/constraint.sdc
```

## A3 — SDC e utilization accoppiati

Clock stretto → slack negativo → RSZ inserisce buffer/upsize → area celle cresce →
`CORE_UTILIZATION` fissa il core → utilization *effettiva* sale → al CTS
`detailed_placement` può fare **DPL-0038** (util > 100%).

Nel run sano sei al **48.3%** post-CTS, non al 100%. DPL-0038 è l’esperimento LAB 05 parte 4
(util 55 + SDC 0.25), **non** la tabella d’oro.

---

## B1 — Core area vs utilization

Dal log `2_1_floorplan.log`, riga `Core area`.

Riferimento **util 35**: **1712.5 µm²**, effective util **0.367**.

Formula mentale: `area_core ≈ area_celle / (utilization/100)`.
A parità di 629 µm² di celle, util 50 → core ≈ metà di util 25
(non esatto: snapping **IFP-0028**, margini, aspect 1.0).

## B2 — Disegno

Die esterno, core interno, rows orizzontali, rail M1 sulle rows,
strap M4/M7 a maglia. Confronta col PNG `gui-shots/03_pdn_labeled.png`.

## B3 — GUI scavenger (PDN)

| Cosa | Dove |
|---|---|
| VDD / VSS | Inspector su una strap; `Nets/Power` e `Nets/Ground` |
| Site | log `2_1`: `FreePDK45_38x28_10R_NP_162NW_34O` |
| Tapcell | `gui_2_3_floorplan_tapcell.odb` o PNG `win_tapcell.png` |

Non usare `gui::set_display_controls "Rows"` → **GUI-0013**.

---

## C1 — GP vs DP

| Vista | PNG | Cosa vedi |
|---|---|---|
| GP | `win_place_gp.png`, `04_place_gp_labeled.png` | blob, overlap visivo possibile, I/O a triangolo |
| DP | `win_place_dp.png`, `05_place_dp.png` | allineamento alle rows, overlap sparito |

## C2 — Buffer resizer a place

Cerca `Inserted` in `logs/.../3_4_place_resized.log`.
Area post-resize riferimento: **684 µm² / 40%** (era ~629 / 37% post-synth).
I **45** buffer annotati in golden-metrics sono del **CTS**, non di questo step:
non mescolare i due `Inserted`.

---

## D1 — DPL-0038 intenzionale

`constraint_tight.sdc` (0.25 ns) + `CORE_UTILIZATION=55` → atteso **DPL-0038**
in `4_1_cts.log`. Snapshot: `4_1_error.odb`.

Non è **RSZ-0062**: 0062 = timing non riparato (il run d’oro lo ha, e **passa**);
0038 = legalize impossibile perché area > core.

## D2 — Fix

Uno solo: `CORE_UTILIZATION=30` **oppure** SDC 0.46/2.0 ns. Poi CTS deve passare.
Ripristina SDC e util 35 prima della lezione 06.

---

## E1 — DRC

`wc -l reports/nangate45/gcd/learn/5_route_drc.rpt` → **0** sul GCD `learn` = nessuna violazione listata.

## E2 — GDS

`klayout results/.../6_final.gds`, tasto F. Celle top ≥ 1, layer metal visibili.
Colori **≠** Display Control Qt.

## E3 — Progetto finale

Template: `progetto-finale-template.md`. Obbligatorio confrontare `period_min`
finish (**0.50 ns** ~ **2011 MHz**) con SDC 0.46 ns (~2174 MHz):
`make finish` verde **non** chiude 2.17 GHz.

PNG da citare: `orfs_final_worst_path.png`, `orfs_cts_clock_tree.png`,
`orfs_final_ir_drop.png`, `03_pdn_labeled.png`.
