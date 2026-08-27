# Lezione 05 — Clock Tree Synthesis (CTS)

CTS è dove il corso **insegna il debug**. Se tutto passa al primo colpo, provoca un fallimento (LAB parte 4).

Sul GCD `learn` (util 35, SDC 0.46 ns) un run reale ha fatto:

| Istante | Core | Area istanze | Util | Note |
|---|---|---|---|---|
| DPL pre-repair CTS | 1712.5 µm² | 693 µm² | **40.5%** | buffer clock appena inseriti |
| Dopo `repair_timing` CTS | 1712.5 µm² | 828 µm² | **48.3%** | `Inserted 45 buffers`, **RSZ-0062** |
| WNS CTS final | | | | **−0.04 ns**, 32 violazioni setup |
| Setup skew | | | | ~**0.00 ns** (albero corto) |
| Finish (confronto) | | | | WNS **−0.04 ns**, TNS −0.60, fmax ~2.01 GHz |

Non è “timing chiuso”: RSZ-0062 dice che **non** ha riparato tutto. GCD è abbastanza piccolo da routare comunque. Su un design grosso qui ti fermeresti a ripensare SDC/util.

## Obiettivi

- Skew vs latency vs NDR, con numeri
- Contare `CLKBUF*` pre/post
- Leggere il **Clock Tree Viewer** (PNG `orfs_cts_clock_tree.png`)
- Risolvere DPL-0038 con **un** parametro

## Letture

- Questo README
- `walkthrough-cts.tcl.md`
- `debug-playbook.md` sezione CTS
- LAB 05
- Atlante §5.7 e §9 (heatmap ORFS)

## Il problema

N flip-flop, un pin `clk`. Stellare (un filo a tutti i CK):

- slew pessimo (il clock non è uno square wave)
- delay RC enorme
- skew incontrollato

CTS costruisce un albero di `CLKBUF*` / inverter con **latenza simile** verso i sink.

Nel viewer (`orfs_cts_clock_tree.png`) sul GCD vedi circa:

- root (triangolo) → 1 buffer → **fanout 4** → foglie (FF) intorno a **0.07 ns** di latency
- foglie quasi allineate in Y → skew piccolo (coerente con report ~0)

## Sequenza TritonCTS in ORFS

1. `repair_clock_inverters`
2. `clock_tree_synthesis -sink_clustering_enable -repair_clock_nets`
3. `estimate_parasitics -placement`
4. `detailed_placement` ← **punto di rottura area** (DPL-0038)
5. `repair_timing` setup/hold (qui nascono i 45 buffer e RSZ-0062)
6. secondo `detailed_placement` + `check_placement`

Se il passo 4 fallisce: `save_progress 4_1_error` → `gui_4_1_error.odb`.

## Skew, latency, NDR

- **Latency** sink: ritardo pin `clk` del blocco → `CK` del FF.
- **Skew**: differenza di latency. Setup mangia lo skew peggiorativo; hold odia lo skew invertito.
- **Ideal clock** (pre-CTS): STA finge latency di rete = 0.
- **Propagated clock** (post-CTS): delay dei `CLKBUF*`. Per questo WNS può **peggiorare** da place (+0.01) a CTS (−0.04) anche senza fili di segnale.
- **NDR** `CTS_NDR_0`: regola più larga sul clock. Inspector su net `clk` dopo il route.

Un albero batte uno stellare perché lo stellare ha RC/slew inaccettabili già a poche decine di sink (qui 35 `DFF_X1` in synth, più bit-blast).

## Relazione 01 + 03 + 04

```
clock stretto → RSZ pre-CTS gonfia area
core piccolo (util alta) → pochi site liberi
CTS inserisce CLKBUF + ancora RSZ
detailed_placement: util > 100% → DPL-0038
```

Nel run sano sei al **48%** post-CTS. DPL-0038 arriva quando questa colonna supera 100. Non è un bug di OpenROAD.

## Metriche da annotare

| Metrica | File |
|---|---|
| Skew / latency | `4_cts_final.rpt` (`report_clock_skew`) |
| WNS/TNS / viol count | stesso report |
| Buffer inseriti | log `4_1_cts.log` `Inserted N buffers` |
| Util DPL | log `DPL-0006` |
| Albero | `reports/.../cts_core_clock.webp.png` (copiato in `gui-shots/orfs_cts_clock_tree.png`) |

## GUI

```tcl
select -name "clk" -type Net
select -name "clkbuf*" -type Inst
```

PNG finestra: `win_cts.png`. Viewer: `orfs_cts_clock_tree.png`.  
View → Clock Tree Viewer se il menu risponde; altrimenti il PNG ORFS è la stessa informazione.

## Catena power & SPICE

CTS inserisce buffer clock → aumenta **gruppo Clock** in `report_power`. Vedi [`spice-power-chain.md`](../../reference/spice-power-chain.md#lezione-05-cts).

| Collegamento | Dove |
|---|---|
| FlowLab | [cts](/flusso?phase=cts) |

## Durata

README+walkthrough 50–70 min, LAB 90–120 min (include debug intenzionale), **totale ~3 ore**.
