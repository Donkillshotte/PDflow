# Template final project (lesson 07)

Copy to `mio-progetto-finale.md`. Senza this file compilato the course **is not finito**,
even if `make finish` is green.

Compare every numero con [golden-metrics.md](../reference/golden-metrics.md)
(util 35, SDC 0.46 ns, variant `learn`, OpenROAD/ORFS 26Q2).

## 1. Parameters of *your* run

- SDC used (clock period, file):
- `CORE_UTILIZATION`:
- `PLACE_DENSITY_LB_ADDON` (se diverso da 0.20):
- Altri override Makefile:
- Tool: `openroad -version` =

## 2. Metrics vs tabella d’oro

Copia i **tuoi** valori dai report (`3_resizer.rpt`, `4_cts_final.rpt`, `6_finish.rpt`,
`synth_stat.txt`, `2_1_floorplan.log`). Non inventare.

| Stadio | Metric | Tuo valore | Riferimento golden | Scarto |
|---|---|---|---|---|
| Synth | celle / area / DFF_X1 | | 496 / 628.824 / 35 | |
| Floorplan | core area / eff. util | | 1712.5 µm² / 0.367 | |
| Place | worst slack / `period_min` | | +0.01 ns / 0.45 ns | |
| Place | design area post-RSZ | | 684 µm² / 40% | |
| CTS | WNS / viol / skew | | −0.04 / 32 / ~0 | |
| CTS | `Inserted` buffer / util DPL | | 45 / 48.3% | |
| GRT | WNS / viol | | −0.05 / 43 | |
| DRC | `wc -l 5_route_drc.rpt` | | 0 | |
| Finish | WNS / TNS / viol | | −0.04 / −0.60 / 38 | |
| Finish | `period_min` / fmax | | 0.50 ns / ~2011 MHz | |

**Domanda required:** the period SDC is 0.46 ns (~2174 MHz). Your `period_min` a finish
is ______. So real fmax ≈ 1/`period_min`. Did you close the frequency target? (**Yes/No** + one sentence)

Correct reading on the gold run: **No** — 2011 MHz < 2174 MHz. `make finish` exit 0 ≠ timing closed.

Did you see **RSZ-0062** in the log CTS? (Yes/No). This is not **DPL-0038**. Difference in one sentence:

## 3. Screenshot o riferimento atlas

Point to the PNG in `learn/reference/gui-shots/` **or** describe the GUI (Desktop, not Preview).

| Vista | Files PNG / ODB | What you recognized |
|---|---|---|
| Anatomia A–G | `win_anatomy_labeled.png` | |
| PDN | `03_pdn_labeled.png` | M1 rail vs strap |
| Place GP vs DP | `04_place_gp_labeled.png` / `05_place_dp.png` | |
| Clock tree | `orfs_cts_clock_tree.png` | latency leaves ~ |
| Route M2/M3 | `08_route_labeled.png` / `win_layers_m2m3.png` | colors |
| Worst path | `orfs_final_worst_path.png` | start/end pin |
| IR drop | `orfs_final_ir_drop.png` | mV scale |
| Congestion | `orfs_final_congestion.png` | gcell |

Inspector su net `clk` (post-route): Signal type ______, Wire type ______, NDR ______.

## 4. An error encountered

- Log (3 righe):
- Codice (`DPL-0038`, `RSZ-0062`, `STA-2204`, `GUI-0013`, `IFP-0028`, altro):
- Hypothesis:
- Fix (one knob):
- Lesson appresa:

## 5. Three things I can now explain aloud

1.
2.
3.

## 6. Next design

What you would bring to ORFS after GCD and why (PDK, size, vincolo clock).

## 7. Autocertificazione

- [ ] Ho letto `golden-metrics.md` e compilato the deviation
- [ ] Ho aperto (o studiato i PNG di) atlas `gui-atlas.md`
- [ ] `constraint.sdc` is default again 0.46 ns
- [ ] `FLOW_VARIANT=learn` in all commands I ran manually
