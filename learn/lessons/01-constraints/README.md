# Lezione 01 — Constraints e configurazione design

## Obiettivi

- Leggere e scrivere un file **SDC** (Synopsys Design Constraints)
- Capire `config.mk`: utilization, PDK, file RTL
- Vedere l'effetto dei constraints sul timing finale
- Collegare constraints → synthesis → timing analysis

## Cos'è l'SDC?

L'SDC descrive le **regole temporali** del design:

| Comando | Significato |
|---|---|
| `create_clock` | Definisce il periodo del clock (target di frequenza) |
| `set_input_delay` | Quanto tardano i segnali in ingresso rispetto al clock |
| `set_output_delay` | Quanto presto devono uscire i segnali verso il mondo esterno |
| `set_false_path` | Percorsi che il timing analyzer deve ignorare |
| `set_multicycle_path` | Percorsi che possono usare più cicli |

## File del corso

```
learn/designs/nangate45/gcd-tutorial/
├── config.mk              # parametri del flusso ORFS
├── constraint.sdc         # default (0.46 ns)
├── constraint_relaxed.sdc # esercizio facile (2.0 ns)
└── constraint_tight.sdc   # esercizio difficile (0.25 ns)
```

## config.mk — parametri che influenzano il fisico

| Variabile | Effetto |
|---|---|
| `CORE_UTILIZATION` | Percentuale del core occupata dalle celle |
| `SDC_FILE` | Quale file di constraints usare |
| `PDN_TCL` | Strategia power grid (floorplan) |
| `PLACE_DENSITY_LB_ADDON` | Margine densità per il placement |
| `FLOW_VARIANT` | Sottocartella risultati (`learn` vs `base`) |

## Concetto chiave: timing closure

- Clock **rilassato** (2 ns) → facile da chiudere, pochi buffer, area minore
- Clock **stretto** (0.25 ns) → difficile, resizer inserisce buffer/upsize, area esplode
- **Utilization alta** + clock stretto → rischio overflow (>100% area) al CTS

## Esercizi

### 1-A — Leggi l'SDC default
Apri `constraint.sdc` e identifica clock period e I/O delay.

### 1-B — Clock rilassato
Copia `constraint_relaxed.sdc` → `constraint.sdc`, rilancia `place` e confronta slack.

### 1-C — Clock aggressivo
Usa `constraint_tight.sdc`, osserva buffer al CTS e utilization.

### 1-D — GUI timing
Apri `gui_3_place.odb` → pannello Charts → Endpoint Slack.

## Durata stimata

60–90 minuti.
