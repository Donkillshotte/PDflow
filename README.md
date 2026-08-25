# OpenROAD + OpenSTA — ambiente locale di physical design

Ambiente locale completo per il physical design digitale (RTL → GDSII) basato su:

| Tool | Versione | Provenienza |
| --- | --- | --- |
| [OpenROAD](https://github.com/The-OpenROAD-Project/OpenROAD) | 26Q2 (binari Precision Innovations) | pacchetto `.deb` da [VaultLink](https://vaultlink.precisioninno.com/) |
| [OpenSTA](https://github.com/parallaxsw/OpenSTA) | 3.1.0 | compilato dai sorgenti (con CUDD) |
| [OpenROAD-flow-scripts](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts) (ORFS) | 26Q2 | tag corrispondente a OpenROAD |
| [yosys](https://github.com/YosysHQ/yosys) | submodule pinnato da ORFS | compilato dai sorgenti (CMake) |
| [KLayout](https://www.klayout.de/) | 0.30.11 | pacchetto `.deb` ufficiale |

Testato su **Ubuntu 24.04** (funziona anche su 22.04).

## Installazione

Gli script vanno eseguiti in ordine (richiedono `sudo` per i pacchetti apt):

```bash
./scripts/01_install_openroad.sh   # OpenROAD dai binari precompilati
./scripts/02_install_opensta.sh    # CUDD + OpenSTA dai sorgenti
./scripts/03_install_klayout.sh    # KLayout (per il GDS finale)
./scripts/04_setup_orfs.sh         # clone ORFS + build di yosys
```

Lo script ORFS ricava automaticamente il tag trimestrale dalla versione di
OpenROAD installata (per esempio `26Q2-...` → `26Q2`), così tool e flow restano
allineati. Il tag può essere sovrascritto con `ORFS_TAG=...`.

Tutto ciò che viene compilato o clonato finisce in `tools/` (ignorato da git):

```
tools/
├── OpenROAD-flow-scripts/   # ORFS: flusso, PDK (nangate45, sky130, asap7...), design di esempio
├── src/                     # sorgenti di OpenSTA e CUDD
├── cudd/                    # install di CUDD (libreria BDD)
├── opensta/                 # install di OpenSTA  → symlink /usr/local/bin/sta
└── yosys/                   # install di yosys    → symlink /usr/local/bin/yosys
```

`openroad` e `klayout` sono installati a livello di sistema dai `.deb`.

## Verifica rapida

```bash
openroad -version        # 26Q2-1164-g08f67ee5ec
sta -version             # 3.1.0
yosys -V
klayout -v

# Smoke test OpenSTA: timing min/max su un piccolo design Nangate45
./scripts/run_opensta_example.sh
```

## Corso hands-on Physical Design (consigliato per imparare)

Percorso guidato **fase per fase** (constraints → synth → floorplan → place → CTS → route → GDS)
con teoria, LAB da 60–120 min, walkthrough Tcl, workbook e GUI.
Studio attivo stimato: **20–28 ore** (il wrapper `--auto` non sostituisce lo studio).

```bash
./scripts/learn_physical_design.sh --check    # verifica prerequisiti
./scripts/learn_physical_design.sh --list     # indice 8 lezioni
./scripts/learn_physical_design.sh --deep --lesson 01-constraints
./scripts/learn_physical_design.sh --resume   # riprendi progresso
./scripts/test_course.sh                     # smoke test struttura + lezione 00
```

Documentazione: [learn/README.md](learn/README.md) e [learn/CURRICULUM.md](learn/CURRICULUM.md).
Verifica pipeline: [learn/EVIDENCE.md](learn/EVIDENCE.md).

Per la GUI usa il pulsante **Desktop** su [cursor.com/agents](https://cursor.com/agents) (non le card Preview).

## Flusso completo RTL → GDS (design di esempio `gcd`)

```bash
./scripts/run_gcd_flow.sh
```

Esegue con ORFS il flusso completo sul design `gcd` con il PDK open **Nangate45**:
sintesi (yosys) → floorplan → placement → clock tree synthesis → routing →
finishing (GDSII via KLayout). Output in
`tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/`:

Il launcher usa una core utilization del 35% per lasciare spazio al repair
timing richiesto dal vincolo aggressivo di 0,46 ns dell'esempio 26Q2. È possibile
sovrascriverla, per esempio con `CORE_UTILIZATION=45`.

- `6_final.gds` — layout finale
- `6_final.odb` / `6_final.def` — database e DEF finali
- report di timing/area/potenza in `flow/reports/nangate45/gcd/`

Per altri design o PDK:

```bash
DESIGN_CONFIG=./designs/sky130hd/gcd/config.mk ./scripts/run_gcd_flow.sh
```

Per aprire il risultato nella GUI di OpenROAD (serve un display/X11):

```bash
./scripts/run_gcd_flow.sh gui_final
```

## Uso interattivo

```bash
# Shell Tcl di OpenROAD
openroad

# Shell di OpenSTA
sta
```

## Note

- I binari OpenROAD di Precision Innovations includono già OpenSTA al loro
  interno (comandi `report_checks`, `report_wns`, ecc.); l'installazione
  standalone di OpenSTA serve per usare lo STA da solo, fuori dal flusso.
- Il launcher `run_gcd_flow.sh` passa a ORFS i percorsi di `openroad`, `sta` e
  `yosys` trovati nel `PATH`. ORFS, fuori da un ambiente Nix, cerca altrimenti
  i binari nella propria directory `tools/install`.
- Lo script di setup installa `tcl-dev`: l'integrazione Tcl di yosys è
  necessaria perché ORFS esegue gli script di sintesi con l'opzione `-c`.
- La GUI di OpenROAD (`openroad -gui`) richiede Qt/X11: in ambiente headless
  usare `Xvfb` oppure lavorare da riga di comando.
