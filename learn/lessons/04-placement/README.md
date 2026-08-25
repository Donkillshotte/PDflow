# Lezione 04 — Placement

Il placement è il momento in cui il design **occupa spazio**. Prima: celle in un mucchio. Dopo: ogni gate ha una coordinata, e il timing inizia a dipendere dai fili.

## Obiettivi

- Distinguere **global placement** vs **detailed placement** senza mescolarli
- Capire density, overflow, padding
- Leggere report resizer come *narrativa* (cosa ha fatto RSZ e perché)
- Ispezionare legalizzazione in GUI (gp vs dp)
- Collegare placement al fallimento CTS della lezione 05

## Letture obbligatorie

1. Questo README
2. `walkthrough-global_place.tcl.md`
3. `golden-metrics.md` riga Place / CTS DPL
4. Atlante §5.5–5.6 (`win_place_gp.png` vs `win_place_dp.png`)
5. `LAB.md` lezione 04

## Un run `learn` di riferimento

| Istante | Area / util | Slack |
|---|---|---|
| Post-synth (nel core) | ~629 µm² / 37% | (liberty) |
| Post-resizer `3_4` | **684 µm² / 40%** | worst slack **+0.01 ns**, 0 viol setup |
| `period_min` place | **0.45 ns** (~2240 MHz) | ancora **ideal clock** |
| CTS dopo (lezione 05) | 828 µm² / **48.3%** | −0.04 ns, clock **propagato** |

Il resizer ha già mangiato ~55 µm² prima del CTS. I 45 buffer della lezione 05 partono da qui, non da zero.

## Il problema matematico (intuizione)

Global placement minimizza circa:

```
wirelength + penalità_densità + (opzionale) penalità_timing
```

soggetto a: celle nel core, non troppo ammassate.

Non è NP-hard che *tu* risolvi a mano: RePlAce (in OpenROAD) itera. Tu scegli **density target** e **padding**.

## Sottofasi placement ORFS

| Step | Cosa fa | Perché esiste |
|---|---|---|
| 3_1_place_gp_skip_io | GP senza IO | prima stima interna |
| 3_2_place_iop | I/O placement | pin sul bordo |
| 3_3_place_gp | GP completo | wirelength + density |
| 3_4_place_resized | RSZ buffer/upsize/clone | timing pre-CTS |
| 3_5_place_dp | Detailed placement | legalizzazione site/row |

L'ordine IO → GP è importante: i pin fissati **tirano** le celle verso i bordi.

## Global vs detailed — analogia

- **GP:** sistema i mobili nella stanza “a spanne” (possono sovrapporsi un po' nel disegno)
- **DP:** allinea tutto alle piastrelle (sites). Nessun overlap. Può peggiorare un filo di wirelength.

Se in GUI `3_3` e `3_5` sono identici, stai guardando lo stesso file.

## Resizer (RSZ) — il vero costo del clock stretto

Dopo GP, OpenROAD stima parasitics da placement e:

- inserisce **buffer** su net lente / high fanout
- **upsize** celle (X1 → X2 → X4) per slew
- **clone** gate per split carichi
- swap pin

Ogni inserimento **aumenta area**. Questo è il ponte verso DPL-0038 in CTS.

Prefissi istanze (GUI Find):

| Prefisso | Ruolo |
|---|---|
| `rebuffer*` | buffer timing |
| `fanout*` | split fanout |
| `hold*` | fix hold (più raro pre-CTS) |
| `max_cap*` / `max_length*` | vincoli capacitance/length |

## Metriche da monitorare

| Metrica | Dove | Soglia mentale GCD |
|---|---|---|
| Overflow | `3_global_place.rpt` / log GP | → 0 |
| Density | heatmap / log | sotto 1.0 dopo DP |
| WNS/TNS | `3_resizer.rpt` | può essere negativo |
| Buffer count | log `3_4_place_resized` | cresce se SDC stretto |
| Utilizzazione istanze | log DP | << 100% se vuoi CTS facile |

## GUI — cosa osservare

Sequenza obbligatoria (15 min ciascuna):

1. `gui_3_2_place_iop.odb` — pin sul die edge
2. `gui_3_3_place_gp.odb` — blob, possibile overlap visivo
3. `gui_3_4_place_resized.odb` — cerca buffer nuovi
4. `gui_3_5_place_dp.odb` — rows allineate

Heatmap **Placement Density**: rosso = pieno. Se tutto rosso a util 55% + SDC tight, la lezione 05 fallirà.

Pixel e PNG: `learn/reference/gui-atlas.md` §5.5–5.6. Menu: `gui-openroad.md`.

## Esperimento controllato

Un parametro per run:

- Solo `PLACE_DENSITY_LB_ADDON` 0.10 vs 0.20
- Solo SDC relaxed vs default
- Non entrambi

Tabella nel quaderno: density addon | overflow | buffer | WNS.

## Durata stimata

- README + walkthrough: 45 min
- LAB: 90 min
- GUI confrontata: 45 min
- **Totale: ~3 ore**
