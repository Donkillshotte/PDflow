# Lesson 04 — Placement

Il placement is il momento in cui il design **occupies space**. Prima: celle in un mucchio. Dopo: every gate ha una coordinata, e the timing inizia a dipendere dai fili.

## Objectives

- Distinguere **global placement** vs **detailed placement** senza mescolarli
- Capire density, overflow, padding
- Read resizer report as *narrative* (what RSZ did and why)
- Ispezionare legalizzazione in GUI (gp vs dp)
- Collegare placement al failure CTS of the lesson 05

## Required reading

1. This README
2. `walkthrough-global_place.tcl.md`
3. `golden-metrics.md` riga Place / CTS DPL
4. Atlas §5.5–5.6 (`win_place_gp.png` vs `win_place_dp.png`)
5. `LAB.md` lesson 04

## A reference `learn` run

| Stage | Area / util | Slack |
|---|---|---|
| Post-synth (nel core) | ~629 µm² / 37% | (liberty) |
| Post-resizer `3_4` | **684 µm² / 40%** | worst slack **+0.01 ns**, 0 viol setup |
| `period_min` place | **0.45 ns** (~2240 MHz) | ancora **ideal clock** |
| CTS after (lesson 05) | 828 µm² / **48.3%** | −0.04 ns, clock **propagato** |

Resizer already ate ~55 µm² before CTS. The 45 buffers from lesson 05 start here, not from zero.

## The problem matematico (intuizione)

Global placement minimizza circa:

```
wirelength + penalty_density + (optional) penalty_timing
```

soggetto a: celle nel core, non troppo ammassate.

This is not NP-hard che *tu* risolvi a mano: RePlAce (in OpenROAD) itera. Tu scegli **density target** e **padding**.

## Sub-stages placement ORFS

| Step | What it does | Why esiste |
|---|---|---|
| 3_1_place_gp_skip_io | GP senza IO | before stima interna |
| 3_2_place_iop | I/O placement | pin sul bordo |
| 3_3_place_gp | GP completo | wirelength + density |
| 3_4_place_resized | RSZ buffer/upsize/clone | timing pre-CTS |
| 3_5_place_dp | Detailed placement | legalizzazione site/row |

L'ordine IO → GP is importante: i pin fissati **tirano** the cells verso i bordi.

## Global vs detailed — analogia

- **GP:** sistema i mobili nella stanza “a spanne” (posare sovrapporsi un po' nel disegno)
- **DP:** aligns everything to tiles (sites). Nessun overlap. May worsen wirelength a bit.

Se in GUI `3_3` e `3_5` are identici, stai guardando the same file.

## Resizer (RSZ) — il vero costo del tight clock

After GP, OpenROAD stima parasitics da placement e:

- inserisce **buffer** su net lente / high fanout
- **upsize** celle (X1 → X2 → X4) per slew
- **clone** gate per split carichi
- swap pin

Every inserimento **aumenta area**. This is il ponte verso DPL-0038 in CTS.

Prefissi istanze (GUI Find):

| Prefisso | Role |
|---|---|
| `rebuffer*` | buffer timing |
| `fanout*` | split fanout |
| `hold*` | fix hold (rarer pre-CTS) |
| `max_cap*` / `max_length*` | vincoli capacitance/length |

## Metrics da monitorare

| Metric | Where | Soglia mental GCD |
|---|---|---|
| Overflow | `3_global_place.rpt` / log GP | → 0 |
| Density | heatmap / log | sotto 1.0 after DP |
| WNS/TNS | `3_resizer.rpt` | may be negative |
| Buffer count | log `3_4_place_resized` | cresce se SDC stretto |
| Utilizzazione istanze | log DP | << 100% se vuoi CTS facile |

## GUI — cosa osservare

Sequenza required (15 min ciascuna):

1. `gui_3_2_place_iop.odb` — pin sul die edge
2. `gui_3_3_place_gp.odb` — blob, possible visual overlap
3. `gui_3_4_place_resized.odb` — search for buffer nuovi
4. `gui_3_5_place_dp.odb` — rows allineate

Heatmap **Placement Density**: red = full. If all red at util 55% + tight SDC, lesson 05 will fail.

Pixel e PNG: `learn/reference/gui-atlas.md` §5.5–5.6. Menu: `gui-openroad.md`.

## Esperimento controllato

Un parayardstick per run:

- Solo `PLACE_DENSITY_LB_ADDON` 0.10 vs 0.20
- Solo SDC relaxed vs default
- Non entrambi

Table nel notebook: density addon | overflow | buffer | WNS.

## Power & SPICE chain

Il placement fissa **dove** every cella alimenta the mesh (`ITermNode_*` in `write_pg_spice`). See [`spice-power-chain.md`](../../reference/spice-power-chain.md#lesson-04-placement).

| Link | Where |
|---|---|
| FlowLab | [place](/flusso?phase=place) |
| Mesh (post L07) | `pdn/pg_vdd_bumps.sp` |

## Estimated duration

- README + walkthrough: 45 min
- LAB: 90 min
- GUI confrontata: 45 min
- **Totale: ~3 ore**
