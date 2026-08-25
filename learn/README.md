# Corso Physical Design — OpenROAD + ORFS

Percorso **hands-on completo** per imparare ogni fase del physical design digitale:
constraints, synthesis, floorplan, placement, CTS, routing e signoff GDS.

Pensato per essere seguito **con calma** (6–10 ore totali), con teoria, esercizi,
file da leggere e ispezione GUI ad ogni step.

## Avvio rapido

```bash
# Verifica toolchain
./scripts/learn_physical_design.sh --check

# Indice lezioni
./scripts/learn_physical_design.sh --list

# Una lezione (interattiva, con pause)
./scripts/learn_physical_design.sh --lesson 03-floorplan

# Percorso completo
./scripts/learn_physical_design.sh --all

# Riprendi dove avevi lasciato
./scripts/learn_physical_design.sh --resume

# Modalità automatica (senza pause — utile per test)
./scripts/learn_physical_design.sh --auto --lesson 00
```

## Struttura

```
learn/
├── README.md              ← questo file
├── CURRICULUM.md          ← syllabus dettagliato
├── lib/                   ← librerie wrapper (ui, orfs, progress, validate)
├── designs/               ← config e SDC del design didattico
│   └── nangate45/gcd-tutorial/
└── lessons/
    ├── 00-intro/
    ├── 01-constraints/
    ├── 02-synthesis/
    ├── 03-floorplan/
    ├── 04-placement/
    ├── 05-cts/
    ├── 06-routing/
    └── 07-finish/
        ├── README.md      ← teoria approfondita
        └── run.sh         ← esercizi guidati interattivi
```

## Design didattico

- **RTL**: `gcd.v` (Greatest Common Divisor, ~250 celle)
- **PDK**: Nangate45 (open)
- **Variante flusso**: `FLOW_VARIANT=learn` → risultati in `results/.../gcd/learn/` (non tocca i run `base`)

## Due modalità di studio

| Modalità | Strumenti |
|---|---|
| **File** | `config.mk`, `constraint.sdc`, log, report, Makefile ORFS |
| **GUI** | `gui_*` target, OpenROAD Qt, KLayout per GDS |

### Aprire la GUI

Usa il pulsante **Desktop** nella pagina agente Cursor ([cursor.com/agents](https://cursor.com/agents)).
Le card **Preview** nella chat non funzionano per applicazioni Qt/VNC.

Poi, sul desktop remoto:

```bash
cd /workspace/tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn gui_3_place.odb
```

## Progresso

Il file `learn/.progress.json` traccia le lezioni completate.

```bash
./scripts/learn_physical_design.sh --status
```

## Syllabus (sintesi)

| # | Lezione | Durata | Output chiave |
|---|---|---|---|
| 00 | Introduzione | 45–60 min | Mappa RTL→GDS, smoke synth |
| 01 | Constraints | 60–90 min | SDC, config.mk, effetto clock |
| 02 | Synthesis | 45–75 min | `1_2_yosys.v`, `1_synth.odb` |
| 03 | Floorplan | 60–90 min | die/core, PDN |
| 04 | Placement | 75–90 min | global/dp, resizer |
| 05 | CTS | 60–90 min | clock tree, skew |
| 06 | Routing | 75–90 min | guide, DRC, wire |
| 07 | Finish | 60–90 min | GDS, SPEF, signoff |

Dettaglio completo: [CURRICULUM.md](./CURRICULUM.md)

## Dopo il corso

1. Cambia PDK: `DESIGN_CONFIG=./designs/sky130hd/gcd/config.mk`
2. Porta il tuo Verilog in `flow/designs/src/`
3. Leggi e modifica `flow/scripts/*.tcl` un comando alla volta
4. Usa `make help` in `flow/` per tutti i target GUI

## Note

- Gli esercizi con clock **molto stretto** possono fallire al CTS: è intenzionale per imparare il debug.
- Usa `clean_*` per rifare una fase senza ricominciare da zero.
- Consulta la [documentazione ORFS](https://openroad-flow-scripts.readthedocs.io/) per approfondire.
