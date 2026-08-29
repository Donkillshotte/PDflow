# Landscape Dynamic IR / PDN (open-source)

Domanda: *c’è un RedHawk Dynamic open-source?* Risposta onesta: **no**.
Il “flow definitivo” **non** si costruisce intorno a un singolo progetto esistente.
È un **sistema ibrido**: frontend fisico OpenROAD, motore di corrente dedicato,
più solver a fedeltà diversa, screening attività, gold esterni.

Questa slice del corso **non** implementa AMG, rational Krylov, CCS, Ginkgo, GPU,
né uno scaffold `power-integrity/`. Non forkare vyges-em-ir, EMSim o OpenROAD PSM.

## Verdetto (piattaforma, non un clone)

| Pezzo | Ruolo | In questa slice |
|---|---|---|
| OpenROAD / ODB / `write_pg_spice` | frontend fisico | READY |
| Liberty CCS/ECSM + VCD/FSDB + STA | domanda di corrente vera | GAP (NLDM + t50 sintetici) |
| Scenario / window engine | non simulare 100k cicli | PARTIAL (`I_tot(t)` di questo run) |
| **Solver A** direct BE + LU | gold di validazione | READY (~4k nodi GCD) |
| **Solver B** SA-AMG (ESPSim) | workhorse full-chip | **GAP** |
| **Solver C** rational Krylov / MOR (MATEX, Raptor) | riuso tra scenari | **GAP** |
| Ginkgo | backend sparso CPU/GPU | **GAP** |
| Xyce | gold parallelo medio | **GAP** in VM |
| ngspice | unit test fisico 1-nodo | READY |
| MAVIREC / PowerNet / IR-Hunter | ML solo screening | **GAP** — mai dentro il physics |
| vyges-em-ir | bootstrap + check simultaneous-switch | INTEGRATED, **non** il core |

Killer feature futura (GAP): **stesso modello ridotto della PDN**, molti `I(t)` di scenario.
Non è “un simulatore Dynamic IR”: è un engine di power integrity multi-fedeltà,
activity-aware.

## Matrice (ciò che esiste davvero)

| Tool | Static IR | Dynamic / transient | EM | PDN da DEF | Switching | Note sul GCD Nangate45 |
|---|---|---|---|---|---|---|
| OpenROAD PSM / PDNSim | sì | **no** (docs: static IR analyzer) | current density | sì (ODB) | I_avg da liberty/activity | `analyze_power_grid` + `write_pg_spice` |
| **vyges-em-ir** | sì (CG+Jacobi) | sì, BE, **un** `switch_t_ns` | sì (se `emlimit`) | DEF+LEF upstream; qui mesh SPICE | eventi, tutti allineati | bootstrap / validazione; no waveform |
| **Questo corso `dynamic_ir`** | sì | Solver A BE LU, I(t) per pin | no | mesh OpenROAD | simultaneous / spatial / **clock** | waveform + heatmap |
| `pdn_transient.py` | sì | load-step globale | no | mesh OpenROAD | peak_factor | laboratorio CSV |
| ngspice | sì | sì | possibile | da costruire | PWL | **gold 1-nodo**, non full-chip |
| Xyce | sì | sì (MPI) | — | da costruire | sì | **GAP** in questa VM |
| [EMSim](https://github.com/jinyier/EMSim) | sì | sì (PWL → TRAN) | sì | Calibre xRC | PrimeTime PX | **VCS / Calibre / PT-PX / HSpice** — non drop-in OSS |
| VoltSpot | arch-level | arch | — | no gate PDN | arch traces | non è cell-level |
| IREDGe / PowerNet / MAVIREC | ML IR | screening | — | feature IR | vettori | **non** physics sign-off |
| RedHawk / Voltus / Totem | sì | sì | sì | sì | sì | commerciale |

OpenROAD PSM resta **static IR** e il frontend. vyges-em-ir è un prototipo BE
(switch simultaneo, timestep interno, niente waveform) — **non** la fondazione.
Lo split da copiare è quello di EMSim *current analysis*, non il passo EM probe.

## Tre solver (non uno)

| Solver | Formulazione | Ruolo | Stato GCD |
|---|---|---|---|
| **A — Direct BE** | \((G + C/\Delta t) V_{n+1} = \mathrm{rhs}\) · LU sparso | gold, lento, indispensabile per validare | **READY** |
| **B — SA-AMG** | iterativo, mesh PDN ~ ellittica | workhorse full-chip (ESPSim: DC+TRAN, 0.13M–63.4M nodi) | **GAP** |
| **C — Rational Krylov / MOR** | \(E\dot x = Ax + Bu(t)\) ridotto | molte TRAN sulla **stessa** PDN (MATEX, Raptor) | **GAP** |

Backward Euler + PCG/LU **non** è il cuore di prodotto. Qui è solo A.
Non si scrive una “GPU version” a parte: un giorno `LinearSolver` → Ginkgo.

## Livelli di rete (già nel codice, etichette oneste)

Il prototipo può restare \(GV + C\dot V = I(t)\). Il design finale è MNA RLC.

| Livello | Contenuto | GCD oggi |
|---|---|---|
| **N1 R** | \(GV = I\) | READY — `solve_static` |
| **N2 R+C** | decap lumpato sui tap | READY — `c_decap` |
| **N3 R+C+pkg** | R/L package sui bump | READY — `pkg_r` + `pkg_l/Δt` (non L on-die estratta) |
| **N4 on-die + pkg + bumps + VRM** | gerarchia completa | PARTIAL — bump come V in `write_pg_spice`; VRM = `system_pdn` **non** accoppiato in questa TRAN |

## Tre livelli di prodotto

| Livello | Intento | GCD oggi |
|---|---|---|
| **FAST** | vectorless + AMG + timestep grosso · placement/routing | **PARTIAL** — t50 sintetici + Solver A (manca AMG) |
| **ACCURATE** | VCD/FSDB + waveform cella + AMG + Δt adattivo · IR closure | **GAP** |
| **SIGNOFF** | RLC + MOR + spot-check diretti + EM + package | **GAP** |

## Current engine (il salto qualitativo — GAP onesto)

Non: `toggle=1` → impulso arbitrario.
Sì: `I_cell(t) = f(cell, arc, slew, load, state)` da Liberty CCS/ECSM quando c’è.

Nangate45 è **NLDM**. Questa slice usa triangoli da `I_avg` nel mesh.
CCS/ECSM/LVF, VCD pin-accurate e STA windows restano GAP.
EMSim conferma lo split A (correnti) / B (rete); il repo dipende da VCS/Calibre/PT-PX/HSpice.

CircuitNet (instance power + toggle + arrival windows + IR) conferma la separazione
power + timing window + PDN — non è un dataset di sign-off dynamic.

## Scenario engine (non 100k cicli ciechi)

Heuristics → ranking (un giorno ML) → fisica solo sulle top windows.
MAVIREC è il riferimento filosofico (screening, non sostituto del solver).
Qui: finestre su `I_tot(t)` di **questo** run = L3 PARTIAL.

## Architettura di riferimento (EMSim), frontend OpenROAD

```text
cell current (transient) → PWL → rete PDN → TRAN → V(t)/I(t)
```

| Ruolo EMSim | Equivalente qui |
|---|---|
| DEF/GDS + xRC | OpenROAD ODB + `write_pg_spice` |
| PrimeTime PX | OpenSTA `report_power` + Liberty NLDM (non CCS I(t)) |
| HSpice | ngspice **oracle** su RC piccolo; Solver A sul mesh GCD |
| VCS | Icarus VCD — **non** mappa pin gate |

## Sei livelli (prodotto futuro vs slice attuale)

| Livello | Prodotto “RedHawk-like” | Cosa gira **oggi** sul GCD |
|---|---|---|
| 1 PDN extract | ODB → R/C/via | OpenROAD `write_pg_spice` |
| 2 Power model | Liberty CCS/ECSM I(t) | I_avg da mesh + leak_frac (NLDM) |
| 3 Activity | VCD/SAIF/vectorless windows | modi sintetici clock/spatial; VCD RTL non è pin-accurate |
| 4 Current engine | I_cell(t) per arco | triangolo per ITerm |
| 5 Solver | B AMG + C Krylov/MOR + A gold | **solo Solver A** (GCD ~4k nodi) |
| 6 Analysis | map, Vmin, EM, timing | JSON + CSV + SVG heatmap |

## Classifica reale

| Approccio | Voto | Perché |
|---|---|---|
| **Piattaforma ibrida** (OpenROAD + A/B/C + current engine) | ⭐⭐⭐⭐⭐ | Destinazione. Oggi solo frontend + A + I(t) triangolo |
| **Architettura EMSim** (current → PWL → PDN TRAN) | ⭐⭐⭐⭐⭐ | Split A/B corretto. Fine dichiarato: **emanazione EM** (TIFS 2023). README: **VCS, Calibre xRC, PrimeTime PX, HSpice** |
| **OpenROAD + Solver A I(t)+BE** | ⭐⭐⭐⭐⭐ | Unico path *eseguibile* OSS su questo GCD (`dynamic_ir`) |
| vyges-em-ir | ⭐⭐⭐⭐ | Bootstrap BE; simultaneous `switch_t_ns`; **non** il core |
| OpenROAD + ngspice | ⭐⭐⭐ | Unit test fisico, non il motore a 10M nodi |

Non si parte da vyges. Non si clona EMSim (servirebbero le quattro licenze).
Non si forka PSM. Si **sostituiscono** i pezzi commerciali uno a uno.

| EMSim (README) | Sostituto qui | Fedeltà |
|---|---|---|
| Calibre xRC → DSPF power grid | OpenROAD `write_pg_spice` | R mesh PDNSim, non DSPF cell-internal |
| VCS VCD gate-level | Icarus `tb_gcd` | **GAP** pin ITerm |
| PrimeTime PX time-based + `logic_cell_modeling.py` | I_avg nel `.sp` + triangolo | **PARTIAL** — non waveform PT-PX |
| `logic_cell_to_current_source.py` PWL | 601 PWL per ITerm | forma triangolo, non report PX |
| HSpice TRAN | Solver A LU sul mesh; ngspice gold 1-nodo | gold ≠ full-chip |

```text
A  Quanto assorbe la cella?     PARTIAL (triangolo da I_avg)
B  Cosa fa la PDN?              READY   (Solver A + heatmap + waveform)
```

## Cosa non fare

- Non forkare vyges-em-ir, EMSim o OpenROAD PSM.
- Non spacciare BE+PCG/LU come workhorse SoC.
- Non mettere ML *dentro* il solver: solo “cosa simulare”.
- Non scaffoldare `power-integrity/` vuoto in questo repo.
- Non implementare AMG / Krylov / CCS / Ginkgo in questa slice.
- Non fingere correlazione commerciale.

Riferimenti concettuali (non dipendenze): ESPSim, MATEX, Raptor, Ginkgo, Xyce.

Come lanciare lo slice: [dynamic-ir.md](./dynamic-ir.md).
