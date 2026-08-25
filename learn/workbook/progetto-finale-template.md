# Template progetto finale (lezione 07)

Copia in `mio-progetto-finale.md`. Senza questo file compilato il corso **non è finito**,
anche se `make finish` è verde.

Confronta ogni numero con [golden-metrics.md](../reference/golden-metrics.md)
(util 35, SDC 0.46 ns, variant `learn`, OpenROAD/ORFS 26Q2).

## 1. Parametri del *tuo* run

- SDC usato (periodo clock, file):
- `CORE_UTILIZATION`:
- `PLACE_DENSITY_LB_ADDON` (se diverso da 0.20):
- Altri override Makefile:
- Tool: `openroad -version` =

## 2. Metriche vs tabella d’oro

Copia i **tuoi** valori dai report (`3_resizer.rpt`, `4_cts_final.rpt`, `6_finish.rpt`,
`synth_stat.txt`, `2_1_floorplan.log`). Non inventare.

| Stadio | Metrica | Tuo valore | Riferimento golden | Scarto |
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

**Domanda obbligatoria:** il periodo SDC è 0.46 ns (~2174 MHz). Il tuo `period_min` a finish
è ______. Quindi fmax reale ≈ 1/`period_min`. Hai chiuso il target di frequenza? (**Sì/No** + una frase)

Lettura corretta sul run d’oro: **No** — 2011 MHz < 2174 MHz. `make finish` exit 0 ≠ timing chiuso.

Hai visto **RSZ-0062** nel log CTS? (Sì/No). Non è **DPL-0038**. Differenza in una frase:

## 3. Screenshot o riferimento atlante

Indica il PNG in `learn/reference/gui-shots/` **o** descrivi la GUI (Desktop, non Preview).

| Vista | File PNG / ODB | Cosa hai riconosciuto |
|---|---|---|
| Anatomia A–G | `win_anatomy_labeled.png` | |
| PDN | `03_pdn_labeled.png` | rail M1 vs strap |
| Place GP vs DP | `04_place_gp_labeled.png` / `05_place_dp.png` | |
| Clock tree | `orfs_cts_clock_tree.png` | latency foglie ~ |
| Route M2/M3 | `08_route_labeled.png` / `win_layers_m2m3.png` | colori |
| Worst path | `orfs_final_worst_path.png` | start/end pin |
| IR drop | `orfs_final_ir_drop.png` | scala mV |
| Congestion | `orfs_final_congestion.png` | gcell |

Inspector su net `clk` (post-route): Signal type ______, Wire type ______, NDR ______.

## 4. Un errore incontrato

- Log (3 righe):
- Codice (`DPL-0038`, `RSZ-0062`, `STA-2204`, `GUI-0013`, `IFP-0028`, altro):
- Ipotesi:
- Fix (un parametro):
- Lezione appresa:

## 5. Tre cose che ora so spiegare a voce

1.
2.
3.

## 6. Prossimo design

Cosa porteresti in ORFS dopo GCD e perché (PDK, size, vincolo clock).

## 7. Autocertificazione

- [ ] Ho letto `golden-metrics.md` e compilato lo scarto
- [ ] Ho aperto (o studiato i PNG di) atlante `gui-atlas.md`
- [ ] `constraint.sdc` è di nuovo il default 0.46 ns
- [ ] `FLOW_VARIANT=learn` in tutti i comandi che ho lanciato a mano
