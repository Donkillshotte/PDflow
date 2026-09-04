# Template final project (lesson 07)

Copy to `my-final-project.md`. Without this file completed the course **is not finished**,
even if `make finish` is green.

Compare every number with [golden-metrics.md](../reference/golden-metrics.md)
(util 35, SDC 0.46 ns, variant `learn`, OpenROAD/ORFS 26Q2).

## 1. Parameters of *your* run

- SDC used (clock period, file):
- `CORE_UTILIZATION`:
- `PLACE_DENSITY_LB_ADDON` (if different from 0.20):
- Other Makefile overrides:
- Tool: `openroad -version` =

## 2. Metrics vs golden table

Copy **your** values from the reports (`3_resizer.rpt`, `4_cts_final.rpt`, `6_finish.rpt`,
`synth_stat.txt`, `2_1_floorplan.log`). Do not invent.

| Stage | Metric | Your value | Golden reference | Delta |
|---|---|---|---|---|
| Synth | cells / area / DFF_X1 | | 496 / 628.824 / 35 | |
| Floorplan | core area / eff. util | | 1712.5 µm² / 0.367 | |
| Place | worst slack / `period_min` | | +0.01 ns / 0.45 ns | |
| Place | design area post-RSZ | | 684 µm² / 40% | |
| CTS | WNS / viol / skew | | −0.04 / 32 / ~0 | |
| CTS | `Inserted` buffer / util DPL | | 45 / 48.3% | |
| GRT | WNS / viol | | −0.05 / 43 | |
| DRC | `wc -l 5_route_drc.rpt` | | 0 | |
| Finish | WNS / TNS / viol | | −0.04 / −0.60 / 38 | |
| Finish | `period_min` / fmax | | 0.50 ns / ~2011 MHz | |

**Required question:** the SDC period is 0.46 ns (~2174 MHz). Your `period_min` at finish
is ______. So real fmax ≈ 1/`period_min`. Did you close the frequency target? (**Yes/No** + one sentence)

Correct reading on the gold run: **No** — 2011 MHz < 2174 MHz. `make finish` exit 0 ≠ timing closed.

Did you see **RSZ-0062** in the CTS log? (Yes/No). This is not **DPL-0038**. Difference in one sentence:

## 3. Screenshot or atlas reference

Point to the PNG in `learn/reference/gui-shots/` **or** describe the GUI (Desktop, not Preview).

| View | PNG files / ODB | What you recognized |
|---|---|---|
| Anatomy A–G | `win_anatomy_labeled.png` | |
| PDN | `03_pdn_labeled.png` | M1 rail vs strap |
| Place GP vs DP | `04_place_gp_labeled.png` / `05_place_dp.png` | |
| Clock tree | `orfs_cts_clock_tree.png` | latency leaves ~ |
| Route M2/M3 | `08_route_labeled.png` / `win_layers_m2m3.png` | colors |
| Worst path | `orfs_final_worst_path.png` | start/end pin |
| IR drop | `orfs_final_ir_drop.png` | ORFS PDNSim picture (not gold 45.298, not chip PDN) |
| Congestion | `orfs_final_congestion.png` | gcell |

Inspector on net `clk` (post-route): Signal type ______, Wire type ______, NDR ______.

## 4. An error encountered

- Log (3 lines):
- Code (`DPL-0038`, `RSZ-0062`, `STA-2204`, `GUI-0013`, `IFP-0028`, other):
- Hypothesis:
- Fix (one knob):
- Lesson learned:

## 5. Three things I can now explain aloud

1.
2.
3.

## 6. Next design

What you would bring to ORFS after GCD and why (PDK, size, clock constraint).

## 7. Self-certification

- [ ] I read `golden-metrics.md` and filled in the deviation
- [ ] I opened (or studied the PNGs from) atlas `gui-atlas.md`
- [ ] `constraint.sdc` is default again 0.46 ns
- [ ] `FLOW_VARIANT=learn` in all commands I ran manually
