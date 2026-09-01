# Valutazione vs flow base ORFS (GCD `flowlab`)

Stesso esame: ORFS `make finish`, SDC 0.46 ns, tutorial nangate45.
A = baseline **non rilanciato**. Ainj / B / Bfix / C sono variant isolate.
Proxy DSE (F3, mapped area) **non** sono finish. Nessun overwrite di `flowlab`.

## Verdetto

A resta. Nessuna cottura DSE batte il WNS finish ORFS. A-injected è bit-identical. B sul die di A è ancora in ritardo. Nessuno è timing-closed a 0.46 ns.

- A resta: **True**
- A-injected riproduce A (WNS + sha): **True**
- Qualcuno timing-closed (WNS≥0 a finish): **False**
- Qualcuno feasible Next Level: **False**
- Funnel avrebbe saltato B/C/Bfix: **True**
- Freeze A intatto: **True**
- A constraint-dominates B: **True**; C: **True**
- Pareto feasibility-first: `['A', 'Ainj']`

## Finish vs A

| Cook | Variant | WNS | ΔWNS vs A | TNS | Area | ΔArea | Repair | Die | Place WNS | Funnel | Closed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| A | `flowlab` | -37.2 ps | 0 | -0.595 | 940.3 | 0 | 132 | 1970.0 | +12.3 ps | F6 | False |
| Ainj | `flowlab_dse_ainj` | -37.2 ps | +0.0 ps | -0.595 | 940.3 | +0.0 | 132 | 1970.0 | +12.3 ps | F6 | False |
| B | `flowlab_dse_small` | -338.3 ps | -301.1 ps | -13.090 | 609.9 | -330.4 | 126 | 1304.7 | -313.6 ps | place_wns_-0.3136_below_0.0 | False |
| Bfix | `flowlab_dse_fixedb` | -349.5 ps | -312.3 ps | -13.025 | 635.5 | -304.8 | 129 | 1970.0 | -317.5 ps | place_wns_-0.3175_below_0.0 | False |
| C | `flowlab_dse_fast` | -186.9 ps | -149.7 ps | -5.981 | 963.5 | +23.1 | 198 | 1940.8 | -116.7 ps | place_wns_-0.1167_below_0.0 | False |

## Progressione WNS (floorplan → place → CTS → GRT → finish)

| Cook | FP | Place | CTS | GRT | Finish | Place→finish |
|---|---:|---:|---:|---:|---:|---:|
| A | +43.4 ps | +12.3 ps | -39.6 ps | -48.7 ps | -37.2 ps | -49.5 ps |
| Ainj | +43.4 ps | +12.3 ps | -39.6 ps | -48.7 ps | -37.2 ps | -49.5 ps |
| B | -365.2 ps | -313.6 ps | -348.9 ps | -355.6 ps | -338.3 ps | -24.7 ps |
| Bfix | -365.2 ps | -317.5 ps | -356.4 ps | -367.9 ps | -349.5 ps | -32.0 ps |
| C | -90.3 ps | -116.7 ps | -186.0 ps | -197.5 ps | -186.9 ps | -70.2 ps |

## Cosa la DSE *credeva* (proxy, non finish)

Memoria `memory_flowlab.jsonl`: 140 righe, 137 ok.

- `B_arch` `54142494d890` architecture/F1: area mapped 407.512 µm², wns_cost 0.5215.
- `C_synth` `52e0ecacb19b` synthesis/F1: area mapped 618.982 µm², wns_cost 0.1142.
- Best logic `wns_cost`: `5c3846870699` 0.2088 @ 553.28 µm² (None).

Quei numeri **non** battono A. Mapped 407 µm² ≠ finish 610/940. Ideal STA ≠ 6_report.

## Lettura onesta

1. **Il flow base vince il chip.** WNS −37 ps. Nessun netlist DSE è più in orario.
2. **A-injected è il controllo del forno.** Stesso netlist Yosys di A, cottura isolata, WNS e sha identici → il confronto B/C non è rumore di tool.
3. **B è più piccolo e più lento**, anche sul die di A (−349 ps). Il die piccolo non era la causa.
4. **C “fast” è più lento e più grasso** (−187 ps, 963 µm², 198 repair vs 132).
5. **Place predice il finish.** A era meeting a DP (+12 ps). B/C/Bfix no. Il funnel Next Level avrebbe evitato di pagare finish su B e C.
6. **Nessuno è timing-closed** a 0.46 ns (2.17 GHz). A è il migliore tra gli aperti, non un chip verde.
7. **PSM IR non è DirectLU** e non è confrontabile tra die diversi. Il win PDN onesto resta 6.075 → 4.156 mV sullo stesso extract di A.
8. **Gold 45.298 unrestampato.** AES Krylov rifiutato. `flowlab/` non toccato.

