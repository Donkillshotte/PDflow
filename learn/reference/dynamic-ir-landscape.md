# Landscape Dynamic IR / PDN (open-source)

Domanda: *c’è un RedHawk Dynamic open-source?* Risposta onesta: **no**.
Il “flow definitivo” **non** si costruisce intorno a un singolo progetto esistente.
È un **sistema ibrido**: frontend fisico OpenROAD, motore di corrente dedicato,
più solver a fedeltà diversa, screening attività, gold esterni.

Questa slice **implementa** SA-AMG (Solver B), il timestep BE nativo con companion R+L e \(i_L\), Δt adattivo, MOR rational Krylov **descriptor RLC** (Solver C, \(x=[v;i_L]\)), **RAS Schwarz** (Solver D) sull’operatore BE **e** su \(K\) descriptor (kind=2, grafo undirected), e **dual-rail VSS** (`write_pg_spice -net VSS`, pair Sink-for, TRAN return senza toccare il gold VDD).
Interpolatore CCS su Liberty sintetica (`pdn_current`) **e** nel loop TRAN Python (lagged \(I(\mathrm{slew},V^n)\)); sul GCD Nangate resta il triangolo. kind=3 = Eigen BiCGSTAB+ILUT (CPU, unsymmetric). **Non** Ginkgo/GPU. Non forkare vyges-em-ir, EMSim o OpenROAD PSM.

## Verdetto (piattaforma, non un clone)

| Pezzo | Ruolo | In questa slice |
|---|---|---|
| OpenROAD / ODB / `write_pg_spice` | frontend fisico | READY |
| Liberty CCS/ECSM + VCD/FSDB + STA | domanda di corrente vera | STA t50 READY (OpenSTA `report_arrival`); CCS **e** ECSM interpolator READY su `.lib` sintetico; Nangate NLDM = triangolo; VCD RTL = GAP name-join |
| Scenario / window engine | non simulare 100k cicli | L3 READY/PARTIAL — BE sulle finestre `I_tot` (restart isolato solo se L=0; con pkg L si taglia il trailing idle) |
| **Solver A** direct BE + LU | gold di validazione | READY (~4k nodi GCD) |
| **Solver B** SA-AMG + CG (`libdpn` C++) | workhorse | **READY** (5 livelli, \|A−B\| ≪ 1 mV; setup ~0.4 s nativo vs ~3 s Python) |
| **Solver C** rational Krylov MOR | riuso tra scenari | **READY** · m=96 · \|A−C\| 0.401 mV sul GCD clock STA (descriptor RLC); ranking scenari = Solver A |
| **Solver D** RAS Schwarz | decomposizione di dominio | **READY** · ndom=8 · \|A−D\| 0.013 mV sul GCD clock STA (grafo undirected, non stripe). kind=2 su \(K\) descriptor = 32-nodo R+L, **non** il default GCD |
| Dual-rail VSS | return path | **READY** extract+TRAN (Sink-for inst pair, MNA block-diagonal). Non sostituisce il gold VDD |
| kind=3 BiCGSTAB | Krylov CPU su \(A\) non simmetrica | **READY** (Eigen ILUT; non Ginkgo). Non è il gold N3 GCD |
| libdpn Index | mesh n/nnz | **READY** int64 (C API + Eigen StorageIndex); SciPy fallback può restare int32 |
| Ginkgo | backend sparso CPU/GPU | **GAP** |
| Xyce | gold parallelo medio | **GAP** in VM (deck R/L/C/K/PWL/.TRAN è il contratto) |
| ngspice | unit test fisico 1-nodo RC e R+L | READY |
| MAVIREC / PowerNet / IR-Hunter | ML solo screening | **GAP** — mai dentro il physics |
| vyges-em-ir | bootstrap + check simultaneous-switch | INTEGRATED, **non** il core |

Killer feature **già nel codice**: modello ridotto rational Krylov (stessi G, C, L, molti `I(t)`).
Il gold resta Solver A con \(i_L\). C riduce il descriptor \(E\dot x+Ax=u\) allineato al companion; sul GCD clock \|A−C\| ≈ 0.13 mV. Ranking extra \(I(t)\) = Solver A.

## Matrice (ciò che esiste davvero)

| Tool | Static IR | Dynamic / transient | EM | PDN da DEF | Switching | Note sul GCD Nangate45 |
|---|---|---|---|---|---|---|
| OpenROAD PSM / PDNSim | sì | **no** (docs: static IR analyzer) | current density | sì (ODB) | I_avg da liberty/activity | `analyze_power_grid` + `write_pg_spice` |
| **vyges-em-ir** | sì (CG+Jacobi) | sì, BE, **un** `switch_t_ns` | sì (se `emlimit`) | DEF+LEF upstream; qui mesh SPICE | eventi, tutti allineati | bootstrap / validazione; no waveform |
| **Questo corso `dynamic_ir`** | sì | A LU + B SA-AMG + C RLC MOR + D RAS + N4, I(t) per pin | \(J\) da LEF RPERSQ·L/R, TTF relativo | mesh OpenROAD + tech LEF | simultaneous / spatial / **clock** + ranking | waveform + heatmap |
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

## Quattro solver (non uno)

| Solver | Formulazione | Ruolo | Stato GCD |
|---|---|---|---|
| **A — Direct BE** | \((G + C/\Delta t) V_{n+1} = \mathrm{rhs}\) · LU sparso | gold, lento, indispensabile per validare | **READY** |
| **B — SA-AMG** | V-cycle Jacobi + CG, LU sul coarse | workhorse (ESPSim-class) | **READY** |
| **C — rational Krylov** | RC: \(C_r \dot z + G_r z = -V^\top I\); RLC: \(E_r \dot z + A_r z = V^\top u\), \(x=[v;i_L]\) | tante TRAN sulla stessa PDN | **READY** sul GCD (\|A−C\| 0.401 mV, m=96) |
| **D — RAS Schwarz** | subdomain LU + RAS + GMRES su \(A\) e su \(K\) | domain decomposition, grafo \(A\cup A^\top\), non stripe | **READY** sul GCD companion (\|A−D\| 0.013 mV, ndom=8); descriptor kind=2 su catena 32 nodi |

Sul GCD (~4k nodi) LU è più veloce: A è l’oracle, B è il path che scala. Non si scrive una GPU fork: un giorno `LinearSolver` → Ginkgo.

## Livelli di rete (già nel codice, etichette oneste)

Il prototipo stampava \(L/\Delta t\) memoryless. N3 ora è un **companion BE serie R+L** con stato \(i_L\) (SPD, AMG ok). L on-die è Grover **stimata** (partial self + mutual cutoff); il TRAN descriptor resta opt-in.

| Livello | Contenuto | GCD oggi |
|---|---|---|
| **N1 R** | \(GV = I\) | READY — `solve_static` |
| **N2 R+C** | decap lumpato sui tap | READY — `c_decap` |
| **N3 R+C+pkg** | R/L package sui bump | READY — \(g_\mathrm{eq}=1/(R+L/\Delta t)\) + \(i_L\); Grover L+M on-die stimata (descriptor `--on-die-l`, sparse \(E\), non AMG) |
| **N4 on-die + pkg + bumps + VRM** | gerarchia completa | **READY** nativo (`libdpn` descriptor BE, \|N3−N4\| ≈ 23 nV sul clock STA GCD). Il load-step µs VRM resta `system_pdn` ngspice |

## Tre livelli di prodotto

| Livello | Intento | GCD oggi |
|---|---|---|
| **FAST** | vectorless + AMG + timestep grosso · placement/routing | **READY** — STA arrival t50 (clock) + Solver B |
| **ACCURATE** | VCD/FSDB + waveform cella + AMG + Δt adattivo · IR closure | **GAP** |
| **SIGNOFF** | RLC + MOR + spot-check diretti + EM + package | **GAP** |

## Current engine (il salto qualitativo — GAP onesto)

Non: `toggle=1` → impulso arbitrario.
Sì: `I_cell(t) = f(cell, arc, slew, load, state)` da Liberty CCS/ECSM quando c’è.

Nangate45 è **NLDM**. Questa slice usa triangoli da `I_avg` nel mesh GCD.
`pdn_current.py` interpola `output_current_*` quando le tabelle ci sono (test su Liberty sintetica).
**Non** si sintetizza CCS da NLDM. VCD pin-accurate sul netlist gate resta GAP (il VCD RTL `tb_gcd` non nomina gli ITerm). STA `report_arrival` fornisce t50 in clock mode — **non** si riscala `I_avg` con l’activity Hz di OpenSTA (sarebbe un double-count rispetto a `report_power` / spice). SAIF `TC` name-join azzera gli impulsi idle; **non** inventa t50 e **non** riscala `I_avg` da `TC`. FSDB resta GAP (binario proprietario). Path delay: OpenSTA worst max path, solo i gate (Q/ZN/…) scalati con \(V_\mathrm{inst}\) a \(t_\mathrm{worst}\); net delay resta nominal. Non è una seconda liberty a Vmin / CCS delay.

CircuitNet (instance power + toggle + arrival windows + IR) conferma la separazione
power + timing window + PDN — non è un dataset di sign-off dynamic.

## Scenario engine (non 100k cicli ciechi)

Heuristics → ranking (un giorno ML) → fisica solo sulle top windows.
MAVIREC è il riferimento filosofico (screening, non sostituto del solver).
Qui: L3 esegue Solver A sulle finestre di `I_tot(t)` di **questo** run.
Restart UIC isolato solo se \(L=0\) (o idle \(\gg L/R\)); con package L si conserva \(i_L\) (prefix \([0,t_\mathrm{cut}]\) o identità se la finestra copre l’orizzonte). Non è uno scan da 100k cicli.

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
| 1 PDN extract | ODB → R/C/via | OpenROAD `write_pg_spice` VDD+VSS + tech LEF; SPEF PG C from PG `*D_NET` (GCD OpenRCX = GAP); Grover on-die L+M estimated (descriptor `--on-die-l`); dual-rail Sink-for pair |
| 2 Power model | Liberty CCS/ECSM I(t) | I_avg da mesh + leak_frac (NLDM); interpolatori CCS+ECSM su `.lib` sintetico |
| 3 Activity | VCD/SAIF/vectorless windows | STA `report_arrival` t50 in clock; SAIF TC name-join (idle-zero, no t50); extra I(t) ranking sintetico; VCD RTL name-join = GAP |
| 4 Current engine | I_cell(t) per arco | triangolo per ITerm; CCS \(I(\mathrm{slew},V)\) o ECSM \(\|C\mathrm{d}V/\mathrm{d}t\|\) solo con tabelle |
| 5 Solver | B AMG + C Krylov MOR + D RAS + A gold + sparse-E descriptor | **A + B + C + D READY**; N4 descriptor BE nativo (sparse \(E\), \(n_\mathrm{iv}\)); kind=3 BiCGSTAB workhorse; RAS kind=2 su \(K\) unsymmetric; Δt adattivo descriptor; MOR gen sparse-\(E\) (compact/strap, non default GCD); VSS return TRAN |
| 6 Analysis | map, Vmin, EM, timing, thermal | JSON + CSV + SVG + \(J\) da RPERSQ·L/R + TTF relativo + **mesh termica strap+via+ILD/Si** + R(T) N1 + path STA delay (NLDM typical-V × \((V_\mathrm{dd}/V)^\alpha\)); 3D CFD = GAP |

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
| HSpice TRAN | Solver A LU + Solver B SA-AMG; ngspice gold 1-nodo | gold ≠ full-chip |

```text
A  Quanto assorbe la cella?     PARTIAL (triangolo da I_avg; CCS interpolator su .lib sintetico)
B  Cosa fa la PDN?              READY   (A gold + B SA-AMG + C descriptor RLC MOR)
```

## Cosa non fare

- Non forkare vyges-em-ir, EMSim o OpenROAD PSM.
- Non spacciare LU a 4k nodi come prova che AMG è inutile a full-chip.
- Non mettere ML *dentro* il solver: solo “cosa simulare”.
- Non scaffoldare `power-integrity/` vuoto in questo repo.
- Non spacciare il shared-A come rational Krylov / CCS / Ginkgo GPU.
- Non spacciare MOR RC-only (senza \(i_L\)) come gold quando \(L>0\).
- Non fingere correlazione commerciale.

Riferimenti concettuali (non dipendenze): ESPSim, MATEX, Raptor, Ginkgo, Xyce.

Performance-critical numerics live in `engine/` (`libdpn.so`, Eigen SparseLU + SA-AMG). Python orchestrates extraction and I(t).
