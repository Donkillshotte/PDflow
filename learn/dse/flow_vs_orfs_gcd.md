# Flow standard ORFS vs DSE (GCD, nangate45, SDC 0.46 ns)

Confronto su disco, non marketing. Stesso design (`gcd` FlowLab), stesso PDK.
Il flow standard è **una ricetta** `make finish`. La DSE è **una ricerca a
livelli** sulla stessa toolchain (Yosys / OpenSTA / OpenROAD), con memoria e
Pareto. Non è un sostituto del signoff.

Fonti: `tools/OpenROAD-flow-scripts/flow/logs/nangate45/gcd/flowlab/6_report.json`
e `3_5_place_dp.json`; memoria DSE `learn/sim/dse/memory_flowlab.jsonl`
(140 righe, 137 ok); DirectLU finish `learn/sim/reports/dynamic_ir_flowlab_direct.json`
(`n_r=5816`).

## Verdetto in una riga

ORFS vince il **chip chiuso** (timing dopo repair). La DSE vince la **ricerca
che ORFS non fa**: architettura, ABC per-cono, PDN sullo stesso extract, e
attributi (IR combo su `dpath` → ABC locale, non più ABC sul chip).

## Bake-off finish (eseguito 2026-09-01)

Stesso `make finish`, solo il netlist DSE. Dettaglio:
[`handoff_finish_bakeoff.md`](handoff_finish_bakeoff.md).

**A resta.** B più piccolo ma WNS −338 ps. C “veloce” WNS −187 ps e 198
repair buffer. Place A era +12 ps; B e C già in ritardo a DP.

## Cosa non è confrontabile

| Coppia | Perché no |
|---|---|
| Mapped DSE 407.5 µm² vs finish stdcell 940.3 µm² | Finish include CTS, 132 timing-repair buffer (130 µm²), fill/tap. Yosys mapped ≠ die legale. |
| F5-lite WNS −641 ps vs finish WNS −37 ps | F5 è 2 iter DRT + SPEF, **senza** `repair_timing`. Contratto esplicito: non è `make finish`. |
| Catalog IR 1.705 mV vs DirectLU finish 6.075 mV | Mesh diversa (strap/EM `n_r≈3.6k`, knobs `pkg_l`). Non è un win sul finish. |
| Leftover decap 3.942 mV vs finish 6.075 mV | Extract candidato `n_r=3432`, non il grafo finish. |
| Ingest F2 ORFS (area 858.9, WNS cost 0.039, HPWL 2810) | Snapshot vecchio. Il `6_report.json` vivo è la fonte finish. |
| OpenROAD PSM 6.667 mV vs DirectLU 6.075 mV | Stesso ordine di grandezza, **oracoli diversi**. |

Gold storico **45.298 mV** resta `reference_run` (sentinel). Current-run
DirectLU sul finish è **6.075 mV**. Non restampare l’oro.

## Tabella (stesso design, assi diversi)

| Asse | ORFS `make finish` | DSE (best onesto) | Chi vince |
|---|---|---|---|
| Setup WNS | **−37.2 ps** (signoff-ish, 38 viol) | Ideal STA **−114 ps** (`abc_speed` @ 619 µm²). F5-lite **−641 ps**. F5-local **−157 ps** (size-up, non un chip). | **ORFS** sul chip. DSE trova ABC che ORFS non cerca, ma non chiude il timing. |
| TNS setup | −595 ps | F1 `tns_cost` 6.67 (unità diverse; non TNS finish) | **ORFS** (metrica signoff). |
| Area stdcell | Place 684 µm² (604 inst, WNS **+12 ps**). Finish **940 µm²** (680 inst). | Mapped arch **407.5** (`sub_twos_complement`). Flatten 409.1. GPL liberty_default **450** (248 celle). | Arch DSE è un asse vero ma **non** è finish. Place ORFS già chiudeva; finish paga +256 µm² di CTS/repair. |
| Timing-repair buf | **132** (130 µm²) + 7 clk buf | F5-CTS: 6 clk buf, **0** repair | ORFS compra lo slack. DSE F5 non ha quel budget. |
| Power totale | 3.93 mW (leak 25.6 µW) | Mapped flatten 1.26 mW (leak ~8.6 µW a GRT) | Netlist diversi. Non dichiarare un win power. |
| Core util | 54.9% (die 1970, core 1712) | GPL a util 35 (contratto floorplan) | Ricette diverse. |
| HPWL | Ingest storico 2810 µm (non rimeasurato) | GPL DSE **1071 µm** su liberty_default | Stesso ordine solo se si rilancia GPL sullo stesso netlist. Oggi netlist diversi. |
| Dynamic IR, **stesso extract finish** (`n_r=5816`) | OpenROAD PSM **6.667 mV**. DirectLU DSE **6.075 mV**. | Decap 200 fF **4.156 mV** (stesso grafo). | **DSE PDN**: −1.92 mV vs DirectLU, senza restampare l’oro. |
| Dynamic IR, mesh **altra** | — | Catalog strap 1.705 mV; leftover 3.942 mV | Ricerca PDN reale, **non** confrontabile col finish. |
| Copertura | 1 ricetta | 140 candidati (F0–F5), Pareto per livello, campagna HV 257.09→257.79 | **DSE** come motore di search. |

Place DP ORFS era **già meeting** (+12 ps). Finish è −37 ps: CTS + route
peggiorano, i 132 buffer non recuperano tutto. `make finish` verde ≠ timing
chiuso a 2.17 GHz (fmax finish ≈ 2.01 GHz).

## Lati positivi della DSE (quelli veri)

1. **Search layered, non un vettore piatto.** ABC ≠ util ≠ density ≠ PDN.
   EHVI acquisisce; non sostituisce il fronte. Fingerprint salta i duplicati.
2. **PDN che ORFS non fa come DSE.** Stesso extract finish: DirectLU 6.075 →
   decap 4.156 mV. Poi leftover/region/strap come *altri* grafi, etichettati
   “not gold”. Attribution: hotspot combo su `dpath` → ABC di cono, non più
   ABC sul chip.
3. **Multi-fidelity.** F1/F3/GPL/F5-lite senza lanciare `make finish` ogni
   shot. Campagna: stop su HV (`hv_eps`), non bruciare il wall.
4. **Architettura e-graph.** 407.512 vs flatten 409.108 µm² (delta piccolo su
   GCD, asse esistente). Equiv PASS.
5. **ABC oltre la ricetta ORFS.** `abc_speed` −114 ps @ 619 µm² vs flatten
   −522 ps @ 409 µm². `boils_balance` (cono `dpath`) `wns_cost` **0.2088** @
   553 µm² — ORFS non esplora quel script sul cono.
6. **Onestà operativa.** Gold 45.298 unrestampato. F5 ≠ finish. AES Krylov su
   ~73k-R rifiutato. Missing ≠ 0.

## Dove il flow standard resta davanti

- Signoff timing e un ODB completo (CTS + repair + fill + route).
- Ricetta industriale ripetibile: un `make finish`.
- GCD è piccolo (~250–680 celle). AES F4 dinamico su 73k-R è ancora GAP
  (DirectLU refuse, AMG timeout).
- Campagna HV su GCD si è mossa poco (+0.70). I tetti default sono un tour,
  non un budget da tapeout.
- La DSE **non** è un Yosys migliore e **non** sostituisce `repair_timing`.

## Cosa servirebbe per “battere finish” sul WNS

Prendere un winner DSE (arch + ABC + eventuale PDN) e pagare un budget
ORFS-like di timing repair / CTS completo. Oggi è **fuori contratto** F5-lite.
Senza quel passo, confrontare −641 ps con −37 ps è un errore di categoria.

## Numeri ancora da non usare in una slide

- IR 1.705 mV come “meglio di finish 6.075”
- Mapped 407 vs finish 940 come “area metà”
- Ingest `wns_cost` −0.0435 (gold snapshot) come WNS DSE
- Leakage mapped vs finish senza stesso netlist
