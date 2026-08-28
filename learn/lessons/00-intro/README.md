# Lezione 00 — Introduzione al Physical Design

Benvenuto nel corso hands-on di **physical design digitale** con OpenROAD.

Questa lezione non è un riassunto da scorrere. È la **mappa mentale** che userai per 6–10 ore. Se salti i paragrafi, le lezioni 03–07 sembreranno magia nera.

## Obiettivi

- Capire la mappa **RTL → GDSII** come catena di *contratti* (file in, file out)
- Orientarsi in ORFS senza perderti tra 2000 file
- Sapere quali **file** e quali **comandi GUI** userai in ogni fase
- Distinguere **tool** (OpenROAD, Yosys, OpenSTA, KLayout) dai **script** (ORFS)
- Eseguire un primo smoke test della toolchain

## Letture obbligatorie (prima degli esercizi)

1. Questo README (~15 min)
2. `learn/reference/glossary.md` — sezioni C, F, P, S, T (~20 min)
3. `learn/reference/file-formats.md` (~20 min)
4. `learn/reference/gui-openroad.md` — solo sezione Avvio (~10 min)
5. `learn/reference/golden-metrics.md` — cos'è un run di riferimento (~10 min)
6. `learn/lessons/00-intro/LAB.md` (~60 min di pratica)

## Cosa significa “physical design”

Il **logical design** (RTL) dice *cosa* calcola il chip.  
Il **physical design** dice *dove* stanno transistor e fili, *quanto* ritardano, *se* la fabbrica può stamparli.

OpenROAD automatizza la seconda parte. Tu devi capire abbastanza da:
- dare constraints realistici
- leggere un fallimento
- non accettare un GDS “verde” senza guardare WNS e DRC

## Il flusso come catena di contratti

```
Verilog + SDC
    → Synthesis     contratto: netlist gate-level + liberty delay
    → Floorplan     contratto: die/core/rows/PDN (ancora senza celle piazzate)
    → Placement     contratto: ogni cella ha (x,y) legale
    → CTS           contratto: clock distribuito con skew controllato
    → Routing       contratto: ogni net ha geometria DRC-clean
    → Finish        contratto: GDS + SPEF + report signoff
```

Ogni fase **rompe** il contratto precedente in modo controllato (aggiunge buffer, sposta celle) e ne scrive uno nuovo su disco (`.odb`).

## Chi fa cosa (tool vs ORFS)

| Componente | Ruolo |
|---|---|
| **Yosys** | Synthesis logica (RTL → gate) |
| **OpenROAD** | Floorplan, place, CTS, route, GUI, STA integrata |
| **OpenSTA** | Timing analysis (anche standalone `sta`) |
| **KLayout** | GDS merge/view |
| **ORFS** | Makefile + Tcl che *orchestrano* i tool |

Senza ORFS dovresti scrivere 50 script Tcl. Con ORFS hai target `make floorplan`. Il corso ti fa **aprire** quegli script, non nasconderli.

## Struttura ORFS (cartelle chiave)

| Cartella | Contenuto |
|---|---|
| `flow/designs/` | Config design (`config.mk`), constraints (`constraint.sdc`), RTL |
| `flow/platforms/nangate45/` | PDK: LEF, LIB, regole tecnologiche |
| `flow/scripts/` | Script Tcl di ogni fase (`floorplan.tcl`, `global_place.tcl`, …) |
| `flow/results/.../learn/` | Snapshot `.odb` del corso (variante `learn`) |
| `flow/logs/.../learn/` | Log dettagliati di ogni step |
| `flow/reports/.../learn/` | Report timing, area, DRC |

**Regola d’oro:** se non capisci un risultato, apri il **log** della stessa fase prima della GUI.

## Design didattico: GCD

Il **GCD** (Greatest Common Divisor) è un piccolo core (~250 celle) su **Nangate45** (PDK open, 45 nm educativo).

Perché GCD e non un RISC-V:
- un run completo dura **minuti**, non ore
- CTS e routing sono comunque reali
- puoi fare sweep SDC/utilization nello stesso pomeriggio

Limite: non imparerai macro SRAM, hierarchical floorplan, o MCMM. Va bene: prima il flusso, poi la scala.

## Due modalità di apprendimento

1. **File / Makefile** — capisci input/output, modifichi parametri, rileggi report
2. **GUI OpenROAD** — ispezioni visivamente layout, timing path, congestione, clock tree

Entrambe sono obbligatorie. Solo file = non “vedi” congestion. Solo GUI = non sai riprodurre.

> Per la GUI usa il pulsante **Desktop** su [cursor.com/agents](https://cursor.com/agents) (non le card Preview della chat). Dettagli: `learn/reference/gui-openroad.md`.

## Artefatti per fase (riferimento rapido)

| Fase | Target make | Snapshot GUI tipico | Walkthrough Tcl |
|---|---|---|---|
| Synth | `synth` | `gui_1_synth.odb` | `reference/walkthrough-synth.tcl.md` |
| Floorplan | `floorplan` | `gui_2_1_floorplan.odb`, `gui_2_4_floorplan_pdn.odb` | `walkthrough-floorplan.tcl.md` |
| Place | `place` | `gui_3_3_place_gp.odb`, `gui_3_5_place_dp.odb` | `walkthrough-global_place.tcl.md` |
| CTS | `cts` | `gui_4_1_cts.odb` | `walkthrough-cts.tcl.md` |
| Route | `route` | `gui_5_1_grt.odb`, `gui_5_2_route.odb` | `walkthrough-route.tcl.md` |
| Finish | `finish` | `gui_final` | `walkthrough-finish.tcl.md` |

## Errori che farai (e va bene)

- Lancio `make` senza `FLOW_VARIANT=learn` e sporchi `base`
- Modifichi SDC e utilization insieme e non sai chi ha rotto CTS
- Guardi solo la GUI e ignori `DPL-0038` nel log
- Usi Preview invece di Desktop e pensi che OpenROAD sia crashato
- Credi che `make finish` verde = 2.17 GHz chiusi (guarda `period_min` in `golden-metrics.md`)

Il playbook: `learn/reference/debug-playbook.md`.

## Catena power & SPICE

Questa lezione è il **primo anello** della catena integrità di alimentazione documentata in [`spice-power-chain.md`](../../reference/spice-power-chain.md#lezione-00-intro).

| Collegamento | Dove |
|---|---|
| FlowLab | [fase RTL](/flusso?phase=rtl) · azione `rtl_sim` |
| Output | `learn/sim/gcd/gcd.vcd` (toggle → activity futura) |
| Lezione seguente power | 02 synthesis (liberty) → 07 finish (`report_power`, [`signoff-matrix`](../../reference/signoff-matrix.md)) |

## Durata stimata

- README + glossario: 45–60 min
- LAB 00: 60 min
- **Totale lezione 00: ~2 ore** se fatto bene
