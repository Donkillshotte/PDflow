# Corso Physical Design — OpenROAD + ORFS

Percorso **hands-on completo** per imparare ogni fase del physical design digitale.
Non è un tutorial da 10 minuti: è strutturato per **20–28 ore di studio attivo**
(LAB + reference + workbook + GUI), con materiali da leggere, esercizi da eseguire,
GUI da ispezionare e workbook da compilare. Il wrapper `--auto` verifica i tool,
non sostituisce lo studio.

## Livelli di contenuto

| Livello | Cosa | Tempo indicativo |
|---|---|---|
| `run.sh` | Guida interattiva rapida per fase | ~30–45 min/lezione |
| `LAB.md` | Laboratorio esteso con esercizi misurabili | ~60–120 min/lezione |
| `reference/` | Glossario, debug, walkthrough Tcl, **golden-metrics** | ~3–4 ore totali |
| `workbook/` | Esercizi con soluzioni e quaderno | ~3–4 ore totali |

**Modalità consigliata:** `./scripts/learn_physical_design.sh --deep --lesson 01`

## Avvio rapido

```bash
# UI grafica (consigliata)
./scripts/run_studio.sh
# → http://127.0.0.1:43217

# Verifica toolchain (CLI)
./scripts/learn_physical_design.sh --check

# Indice lezioni
./scripts/learn_physical_design.sh --list

# Una lezione (interattiva, con pause)
./scripts/learn_physical_design.sh --lesson 03-floorplan

# Modalità approfondita (legge LAB.md, più pause)
./scripts/learn_physical_design.sh --deep --lesson 03-floorplan

# Percorso completo
./scripts/learn_physical_design.sh --deep --all

# Riprendi dove avevi lasciato
./scripts/learn_physical_design.sh --resume

# Modalità automatica (senza pause — utile per test)
./scripts/learn_physical_design.sh --auto --lesson 00
```

Lo **Studio** web (`studio/`) espone lezioni, materiali e azioni ORFS senza
dover ricordare i one-liner `make`. Il CLI resta disponibile e invariato.

## Struttura

```
learn/
├── README.md              ← questo file
├── CURRICULUM.md          ← syllabus dettagliato
├── EVIDENCE.md            ← verifica pipeline + smoke
├── lib/                   ← ui, orfs, progress, validate
├── reference/             ← glossario, debug, walkthrough Tcl, atlante GUI
│   └── gui-shots/         ← PNG Qt + canvas OpenROAD
├── workbook/              ← esercizi, quiz, progetto finale
├── designs/               ← config e SDC del design didattico
└── lessons/
    ├── 00-intro/
    │   ├── README.md      ← teoria
    │   ├── LAB.md         ← laboratorio 60–120 min
    │   └── run.sh         ← guida rapida interattiva
    ...
```

## Design didattico

- **RTL**: `gcd.v` (Greatest Common Divisor, ~250 celle)
- **PDK**: Nangate45 (open)
- **Variante flusso**: `FLOW_VARIANT=learn` → risultati in `results/.../gcd/learn/` (non tocca i run `base`)

## Dopo le lezioni 00–07: power & SPICE

Modulo **consigliato** (non obbligatorio per completare il corso):

1. Leggi [`reference/spice-power-chain.md`](reference/spice-power-chain.md) — mappa esaustiva lezioni ↔ FlowLab ↔ netlist
2. Apri FlowLab [RTL → PKG](http://127.0.0.1:43217/flusso) e la catena sotto la pipeline
3. Post-`make finish`: `./learn/scripts/run_power_chain.sh` (variante `learn` o `flowlab`)
4. Esplora netlist in `learn/sim/spice/` · hub [/pkg](http://127.0.0.1:43217/pkg)

Ogni lezione README ha sezione **«Catena power & SPICE»** con link alla sezione corrispondente.

## Due modalità di studio

| Modalità | Strumenti |
|---|---|
| **File** | `config.mk`, `constraint.sdc`, log, report, Makefile ORFS |
| **GUI** | `gui_*` target, OpenROAD Qt, KLayout per GDS |

### Aprire la GUI

Usa il pulsante **Desktop** nella pagina agente Cursor ([cursor.com/agents](https://cursor.com/agents)).
Le card **Preview** nella chat non funzionano per applicazioni Qt/VNC.

Guida pixel-level (screenshot Qt reali, anatomia A–G, galleria synth→GDS):
[learn/reference/gui-atlas.md](./reference/gui-atlas.md).

Metriche del run tutorial (WNS, `period_min`, area, DRC): [golden-metrics.md](./reference/golden-metrics.md).  
Matrice signoff 4 pilastri (STA/DRC/LVS/power): [signoff-matrix.md](./reference/signoff-matrix.md) · soglie in [`signoff/golden-gcd.json`](./signoff/golden-gcd.json).  
Definition of Done per pilastro: script + JSON report + gate golden + test + doc (vedi checklist in signoff-matrix).  
`make finish` verde **non** significa 2.17 GHz chiusi: a signoff `period_min` è ~0.50 ns (~2.01 GHz).

Poi, sul desktop remoto:

```bash
cd /workspace/tools/OpenROAD-flow-scripts/flow
make DESIGN_CONFIG=./designs/nangate45/gcd-tutorial/config.mk \
     FLOW_VARIANT=learn CORE_UTILIZATION=35 gui_3_place.odb
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
| 07 | Finish | 60–90 min | GDS, SPEF, signoff; fmax vs SDC |

Dettaglio completo: [CURRICULUM.md](./CURRICULUM.md)

## Dopo il corso

1. Cambia PDK: `DESIGN_CONFIG=./designs/sky130hd/gcd/config.mk`
2. Porta il tuo Verilog in `flow/designs/src/`
3. Leggi e modifica `flow/scripts/*.tcl` un comando alla volta
4. Usa `make help` in `flow/` per tutti i target GUI

## Note

- Gli esercizi con clock **molto stretto** possono fallire al CTS: è intenzionale per imparare il debug (**DPL-0038**). **RSZ-0062** sul run default è un warning di timing, non quel crash.
- Usa `clean_*` per rifare una fase senza ricominciare da zero.
- Consulta [golden-metrics.md](./reference/golden-metrics.md) prima di gridare al bug.
- Consulta la [documentazione ORFS](https://openroad-flow-scripts.readthedocs.io/) per approfondire.
