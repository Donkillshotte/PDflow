# Lezione 05 — Clock Tree Synthesis (CTS)

CTS è dove il corso **insegna il debug**. Se tutto passa al primo colpo, provoca un fallimento (LAB parte 4).

## Obiettivi

- Spiegare skew e perché un albero batte un clock stellare
- Contare buffer clock pre/post
- Usare Clock Tree Viewer
- Risolvere DPL-0038 con un solo parametro

## Letture

- Questo README
- `walkthrough-cts.tcl.md`
- `debug-playbook.md` sezione CTS
- LAB 05

## Il problema

N flip-flop, un pin `clk`. Se colleghi tutti i FF allo stesso pin senza buffer:
- slew pessimo
- delay RC enorme
- skew incontrollato

CTS costruisce un albero di `CLKBUF*` / inverter con **latenza simile** verso i sink.

## Sequenza TritonCTS in ORFS

1. `repair_clock_inverters`
2. `clock_tree_synthesis -sink_clustering_enable -repair_clock_nets`
3. `estimate_parasitics -placement`
4. `detailed_placement` ← **punto di rottura area**
5. `repair_timing` setup/hold

Se il passo 4 fallisce: `save_progress 4_1_error` → `gui_4_1_error.odb`.

## Relazione con lezione 01 e 04

Clock stretto (01) + resizer (04) + core piccolo (03) = utilization effettiva > 100% al CTS.

Non è un bug di OpenROAD. È fisica.

## Metriche

| Metrica | File |
|---|---|
| Skew / latency | `4_cts_final.rpt` |
| Buffer clock | GUI filter `CLKBUF*` vs `3_place.odb` |
| Utilizzazione al fail | log `4_1_cts.log` riga DPL-0006 / DPL-0038 |

## GUI

`gui_4_cts.odb`: Nets → Clock only. View → Clock Tree Viewer.  
Dettagli: `gui-openroad.md`.

## Durata

README+walkthrough 40 min, LAB 90–120 min (include debug intenzionale), **totale ~3 ore**.
