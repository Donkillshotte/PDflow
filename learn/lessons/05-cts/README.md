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

## Skew, latency, NDR (definizioni operative)

- **Latency** di un sink: ritardo dal pin `clk` del blocco al pin `CK` del FF (attraverso l’albero).
- **Skew**: differenza di latency tra due sink. Setup “mangia” lo skew *peggiorativo*; hold odia lo skew *invertito*.
- **Ideal clock** (pre-CTS): STA assume latency 0 di rete. È una bugia utile.
- **Propagated clock** (post-CTS): OpenSTA usa i delay dei `CLKBUF*`.
- **NDR** (`CTS_NDR_0` in Inspector sulla net `clk`): regola di routing più larga/spazio sul clock, così il segnale è meno fragile. Non significa “clock ancora ideale”.

Un albero batte uno stellare (un filo dal pin a tutti i FF) perché lo stellare ha RC e slew inaccettabili già a poche decine di sink.

## Relazione con lezione 01 e 04

Clock stretto (01) + resizer (04) + core piccolo (03) = utilization effettiva > 100% al CTS.

Non è un bug di OpenROAD. È fisica. I buffer CTS **occupano site** come le `AND2`: il detailed placement post-CTS è lo stesso motore della lezione 04, con meno aria.

## Metriche

| Metrica | File |
|---|---|
| Skew / latency | `4_cts_final.rpt` |
| Buffer clock | GUI filter `CLKBUF*` vs `3_place.odb` |
| Utilizzazione al fail | log `4_1_cts.log` riga DPL-0006 / DPL-0038 |

## GUI

`gui_4_cts.odb`: `select -name "clk" -type Net` (Inspector: Signal type CLOCK).  
PNG: `gui-shots/win_cts.png`. Dettagli: `gui-atlas.md` §5.7.

## Durata

README+walkthrough 40 min, LAB 90–120 min (include debug intenzionale), **totale ~3 ore**.
