# Lezione 01 — Constraints e configurazione design

Questa è la lezione più importante del corso. Se l'SDC è sbagliato, **tutto** il fisico è un ottimizzatore che insegue un obiettivo falso.

## Obiettivi

- Leggere e scrivere un file **SDC** capendo ogni riga
- Capire `config.mk` come interfaccia verso ORFS (non come magia)
- Vedere l'effetto dei constraints su **area** e **buffer count**, non solo su WNS
- Collegare constraints → synthesis → placement → CTS (catena, non silos)

## Letture obbligatorie

1. Questo README
2. `LAB.md` di questa lezione (90–120 min)
3. `learn/workbook/README.md` capitolo A
4. `learn/reference/golden-metrics.md` (tabella maestra)
5. `learn/reference/gui-openroad.md` sezione Charts

## Cos'è l'SDC?

L'SDC è il **contratto temporale** tra chi ha scritto l'RTL e chi fa il fisico.

Static Timing Analysis **non simula** vettori. Propaga delay worst-case sui path. Senza clock, STA non sa cosa è “in tempo”.

| Comando | Significato | Quando lo userai |
|---|---|---|
| `create_clock` | Periodo e pin del clock | Sempre |
| `set_input_delay` | Arrivo dati dai pin vs clock | Quasi sempre |
| `set_output_delay` | Budget verso il mondo esterno | Quasi sempre |
| `set_false_path` | Path da ignorare | Reset asincroni, CDC |
| `set_multicycle_path` | Path su N cicli | ALU lente, rare su GCD |
| `set_clock_uncertainty` | Margine jitter/skew extra | Signoff, non in lezione 01 |
| `set_clock_latency` | Latenza source/network | Pre-CTS vs post-CTS |

GCD del corso usa solo clock + I/O delay. È intenzionale: impara questi tre comandi a memoria.

## Anatomia del nostro SDC

File: `learn/designs/nangate45/gcd-tutorial/constraint.sdc`

```tcl
set clk_period 0.46          ;# ns → ~2.17 GHz
set clk_io_pct 0.2           ;# 20% del periodo ai pin
create_clock -name core_clock -period $clk_period [get_ports clk]
set_input_delay  [expr $clk_period * $clk_io_pct] -clock core_clock [all_inputs -no_clocks]
set_output_delay [expr $clk_period * $clk_io_pct] -clock core_clock [all_outputs]
```

**Calcolo obbligatorio:** `0.46 * 0.2 = 0.092 ns` di input e output delay.

Interpretazione setup su un path registro-registro:
- Tempo disponibile ≈ `clk_period - setup_lib - uncertainty` (semplificato)
- Se il combinatorio + wire > disponibile → WNS negativo

I/O path: l'input delay **mangia** parte del periodo prima ancora della logica interna.

## File del corso

```
learn/designs/nangate45/gcd-tutorial/
├── config.mk              # parametri del flusso ORFS
├── constraint.sdc         # default (0.46 ns)
├── constraint_relaxed.sdc # esercizio facile (2.0 ns)
└── constraint_tight.sdc   # esercizio difficile (0.25 ns)
```

Tre SDC = tre **ipotesi di prodotto**. Non tre “numeri a caso”.

| File | Ipotesi | Cosa ti aspetti |
|---|---|---|
| relaxed 2.0 ns | chip lento, facile | pochi buffer, WNS comodo |
| default 0.46 ns | target realistico GCD ORFS 26Q2 | qualche violazione pre-route |
| tight 0.25 ns | overclock didattico | RSZ esplode, CTS può fallire |

## config.mk — parametri che influenzano il fisico

| Variabile | Effetto | Accoppiamento con SDC |
|---|---|---|
| `CORE_UTILIZATION` | % die per il core | Clock stretto richiede più spazio |
| `SDC_FILE` | Quale constraints | Diretto |
| `PDN_TCL` | Power grid | IR drop, poco timing diretto |
| `PLACE_DENSITY_LB_ADDON` | Margine densità GP | Clock stretto + density alta = male |
| `FLOW_VARIANT` | Cartella risultati | Sempre `learn` nel corso |

**Anti-pattern:** cambiare SDC *e* utilization nello stesso esperimento.

## Concetto chiave: timing closure è un problema di area

Catena causale da memorizzare:

```
clock più stretto
  → slack più negativo
    → resizer inserisce buffer e upsize
      → area istanze cresce
        → stessa CORE_UTILIZATION diventa “piena”
          → detailed placement CTS: DPL-0038
```

Quindi SDC **non è solo timing**. È un input di **floorplan**.

## OpenSTA vs OpenROAD

- `sta` legge liberty + verilog + sdc → slack **senza** wire reali
- OpenROAD dopo place stima RC da placement
- Dopo route, SPEF è la stima migliore

Non confrontare slack synth con slack finish come se fossero la stessa metrica.

## Run di riferimento (tabella d’oro)

File: `learn/reference/golden-metrics.md`.

Sul default del corso (util 35, 0.46 ns) a **place** worst slack è **+0.01 ns** e
`period_min` **0.45 ns**; a **finish** WNS **−0.04**, `period_min` **0.50 ns** (~2.01 GHz).
Il target SDC ~2.17 GHz **non** è chiuso. Lo sweep relaxed/tight della LAB misura
quanto l’SDC sposta questi numeri, non “se make è verde”.

## Esercizi (sintesi — il dettaglio è nel LAB)

- 1-A Lettura SDC
- 1-B Clock rilassato + tabella
- 1-C Clock aggressivo + debug
- 1-D GUI Endpoint Slack
- 1-E OpenSTA standalone (LAB)

Quiz: `learn/workbook/quiz.md` sezione 01.

## Catena power & SPICE

SDC e `config.mk` definiscono **frequenza e margine** → influenzano switching power a finish. Vedi [`spice-power-chain.md`](../../reference/spice-power-chain.md#lezione-01-constraints).

| Collegamento | Dove |
|---|---|
| FlowLab | [synth](/flusso?phase=synth) (preset SDC) |
| Downstream | `report_power` a lezione 07 |

## Durata stimata

- README: 30–40 min
- LAB: 90–120 min
- Workbook A: 45–60 min
- **Totale: 3–3.5 ore**
