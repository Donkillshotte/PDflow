# Bake-off: DSE winners through the same `make finish`

Eseguito il piano in `handoff_finish_plan.md`. Stesso forno del finish
`flowlab` (SDC 0.46 ns, `CORE_UTILIZATION=35`, tutorial config). Solo il
netlist gate-level cambia. Yosys saltato (`SYNTH_NETLIST_FILES`).
Variant isolate: `flowlab_dse_small`, `flowlab_dse_fast`. Il tree
`flowlab/` non è stato toccato (sha 6_report / 6_final.odb identici al freeze).

## Verdetto in tre righe

1. **A resta il piatto.** WNS finish −37 ps contro B −338 ps e C −187 ps.
2. **B è più piccolo** (610 vs 940 µm²) ma non in orario — non è un win di prodotto.
3. **C**, la ricetta “veloce” sulla carta, finisce più lenta e con **più**
   buffer di riparazione (198 vs 132). Area 963 µm², non più piccola.

Pareggio/regressione sul prodotto. La ricerca DSE resta utile come
laboratorio; su GCD **non** batte la ricetta ORFS una volta cotta per intero.

## Tabella (stesso `6_report.json`)

| Asse | A flowlab | B small (`sub_twos_complement`) | C fast (`abc_speed`) |
|---|---|---|---|
| WNS setup | **−37.2 ps** | −338 ps | −187 ps |
| TNS setup | **−0.595 ns** | −13.09 ns | −5.98 ns |
| Stdcell | 940 µm² / 680 | **610 µm² / 439** | 963 µm² / 660 |
| Repair buf | **132** | 126 | 198 |
| Clk buf | 7 | 7 | 7 |
| Power | 3.93 mW | 2.43 mW | 5.53 mW |
| Util finish | 54.9% | 53.7% | 56.8% |
| Die | 1970 µm² | 1305 µm² | 1941 µm² |
| Place WNS | **+12 ps** | −314 ps | −117 ps |
| PSM VDD drop | 6.67 mV | 3.33 mV | 8.26 mV |

Place già dice il risultato: A era meeting dopo DP. B e C arrivano al
piazzamento già in ritardo; i buffer di fine flusso non recuperano fino ad A.

PSM IR **non** è il confronto DirectLU. Die diversi → reti diverse. Fase 2
DirectLU saltata (non bloccante). Oro 45.298 unrestampato.

Il 55% di A è util **dopo** i repair, non il knob. Il knob comune è 35%.

## Cosa non è successo

- Nessun `make finish` dal controller DSE.
- Nessun AES / Krylov.
- Nessuna cucitura di ABC di cono.
- Crash: nessuno. Entrambe le cotture `errors=0`.

## Dopo

Cucire i coni ABC o mettere il handoff nel loop DSE **non** è giustificato
da questo GCD. Se si ripete, il candidato da cucinare è uno che a *place*
sia già meeting, non solo più piccolo sulla carta.
