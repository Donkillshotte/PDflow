# Landscape Dynamic IR / PDN (open-source)

Question: *c’is un RedHawk Dynamic open-source?* Honest answer: **no**.
Il “flow definitivo” **non** si costruisce around a single existing project.
It is a **hybrid system**: OpenROAD physical frontend, dedicated current engine,
more solvers at different fidelity, activity screening, external gold.

This slice **implements** SA-AMG (Solver B), native BE timestep with companion R+L e \(i_L\), adaptive Δt, MOR rational Krylov **descriptor RLC** (Solver C, \(x=[v;i_L]\)), **RAS Schwarz** (Solver D) sull’operatore BE **e** su \(K\) descriptor (kind=2, grafo undirected), e **dual-rail VSS** (`write_pg_spice -net VSS`, pair Sink-for, TRAN return without touching gold VDD).
Interpolatore CCS su Liberty sintetica (`pdn_current`) **and** in Python TRAN loop (lagged \(I(\mathrm{slew},V^n)\)); on the GCD Nangate remains the triangle. kind=3 = Eigen BiCGSTAB+ILUT (CPU, unsymmetric). **Non** Ginkgo/GPU. Do not fork vyges-em-ir, EMSim o OpenROAD PSM.

## Verdict (platform, not a clone)

| Piece | Role | In this slice |
|---|---|---|
| OpenROAD / ODB / `write_pg_spice` | frontend fisico | READY |
| Liberty CCS/ECSM + VCD/FSDB + STA | domanda di corrente vera | STA t50 READY (OpenSTA `report_arrival`); CCS **e** ECSM interpolator READY su `.lib` sintetico; Nangate NLDM = triangle; VCD RTL = GAP name-join |
| Scenario / window engine | does not simulate 100k cicli | L3 READY/PARTIAL — BE on `I_tot` windows (isolated restart only if L=0; with pkg L cuts trailing idle) |
| **Solver A** direct BE + LU | gold di validazione | READY (~4k nodi GCD) |
| **Solver B** SA-AMG + CG (`libdpn` C++) | workhorse | **READY** (5 livelli, \|A−B\| ≪ 1 mV; setup ~0.4 s nativo vs ~3 s Python) |
| **Solver C** rational Krylov MOR | reuse across scenarios | **READY** · m=96 · \|A−C\| 0.401 mV on the GCD clock STA (descriptor RLC); ranking scenari = Solver A |
| **Solver D** RAS Schwarz | domain decomposition | **READY** · ndom=8 · \|A−D\| 0.013 mV on the GCD clock STA (undirected graph, not stripe). kind=2 on \(K\) descriptor = 32-node R+L, **not** default GCD |
| Dual-rail VSS | return path | **READY** extract+TRAN (Sink-for inst pair, MNA block-diagonal). Does not replace the gold VDD |
| kind=3 BiCGSTAB | Krylov CPU on unsymmetric \(A\) | **READY** (Eigen ILUT; not Ginkgo). This is not gold N3 GCD |
| libdpn Index | mesh n/nnz | **READY** int64 (C API + Eigen StorageIndex); SciPy fallback may stay int32 |
| Ginkgo | sparse CPU/GPU backend | **GAP** |
| Xyce | medium parallel gold | **GAP** in VM (deck R/L/C/K/PWL/.TRAN is the contract) |
| ngspice | unit test fisico 1-nodo RC e R+L | READY |
| MAVIREC / PowerNet / IR-Hunter | ML screening only | **GAP** — never inside the physics |
| vyges-em-ir | bootstrap + check simultaneousus-switch | INTEGRATED, **non** the core |

Killer feature **already in code**: reduced rational Krylov model (same G, C, L, many `I(t)`).
Gold remains Solver A con \(i_L\). C reduces the descriptor \(E\dot x+Ax=u\) aligned to the companion; on the GCD clock \|A−C\| ≈ 0.13 mV. Ranking extra \(I(t)\) = Solver A.

## Matrix (what actually exists)

| Tool | Static IR | Dynamic / transient | EM | PDN da DEF | Switching | Notes on GCD Nangate45 |
|---|---|---|---|---|---|---|
| OpenROAD PSM / PDNSim | yes | **no** (docs: static IR analyzer) | current density | yes (ODB) | I_avg from liberty/activity | `analyze_power_grid` + `write_pg_spice` |
| **vyges-em-ir** | yes (CG+Jacobi) | yes, BE, one `switch_t_ns` | yes (if `emlimit`) | DEF+LEF upstream; here mesh SPICE | events, all aligned | bootstrap / validation; no waveform |
| **This course `dynamic_ir`** | yes | A LU + B SA-AMG + C RLC MOR + D RAS + N4, I(t) per pin | \(J\) da LEF RPERSQ·L/R, TTF relativo | mesh OpenROAD + tech LEF | simultaneousus / spatial / **clock** + ranking | waveform + heatmap |
| `pdn_transient.py` | yes | global load-step | no | mesh OpenROAD | peak_factor | lab CSV |
| ngspice | yes | yes | possible | to build | PWL | **gold 1-node**, not full-chip |
| Xyce | yes | yes (MPI) | — | to build | yes | **GAP** in this VM |
| [EMSim](https://github.com/jinyier/EMSim) | yes | yes (PWL → TRAN) | yes | Calibre xRC | PrimeTime PX | **VCS / Calibre / PT-PX / HSpice** — not drop-in OSS |
| VoltSpot | arch-level | arch | — | no gate PDN | arch traces | is not cell-level |
| IREDGe / PowerNet / MAVIREC | ML IR | screening | — | feature IR | vectors | **not** physics sign-off |
| RedHawk / Voltus / Totem | yes | yes | yes | yes | yes | commercial |

OpenROAD PSM remains **static IR** and the frontend. vyges-em-ir is a BE prototype
(switch simultaneous, timestep interno, no waveform) — **not** the foundation.
The split to copy is EMSim *current analysis*, not the EM probe step.

## Four solvers (not one)

| Solver | Formulation | Role | GCD status |
|---|---|---|---|
| **A — Direct BE** | \((G + C/\Delta t) V_{n+1} = \mathrm{rhs}\) · sparse LU | gold, slow, indispensable for validation | **READY** |
| **B — SA-AMG** | V-cycle Jacobi + CG, LU on coarse | workhorse (ESPSim-class) | **READY** |
| **C — rational Krylov** | RC: \(C_r \dot z + G_r z = -V^\top I\); RLC: \(E_r \dot z + A_r z = V^\top u\), \(x=[v;i_L]\) | many TRAN on same PDN | **READY** on the GCD (\|A−C\| 0.401 mV, m=96) |
| **D — RAS Schwarz** | subdomain LU + RAS + GMRES su \(A\) e su \(K\) | domain decomposition, grafo \(A\cup A^\top\), not stripe | **READY** on the GCD companion (\|A−D\| 0.013 mV, ndom=8); descriptor kind=2 on 32-node chain |

On the GCD (~4k nodes) LU is faster: A is the oracle, B is the scaling path. No GPU fork written: one day `LinearSolver` → Ginkgo.

## Network levels (already in code, honest labels)

The prototype printed \(L/\Delta t\) memoryless. N3 is now **companion BE R+L series** with state \(i_L\) (SPD, AMG ok). L on-die is Grover **stimata** (partial self + mutual cutoff); the TRAN descriptor remains opt-in.

| Level | Content | GCD today |
|---|---|---|
| **N1 R** | \(GV = I\) | READY — `solve_static` |
| **N2 R+C** | lumped decap on taps | READY — `c_decap` |
| **N3 R+C+pkg** | R/L package on bumps | READY — \(g_\mathrm{eq}=1/(R+L/\Delta t)\) + \(i_L\); Grover L+M on-die estimated (descriptor `--on-die-l`, sparse \(E\), not AMG) |
| **N4 on-die + pkg + bumps + VRM** | full hierarchy | **READY** nativo (`libdpn` descriptor BE, \|N3−N4\| ≈ 23 nV on clock STA GCD). The µs VRM load-step remains `system_pdn` ngspice |

## Three product levels

| Level | Intent | GCD today |
|---|---|---|
| **FAST** | vectorless + AMG + coarse timestep · placement/routing | **READY** — STA arrival t50 (clock) + Solver B |
| **ACCURATE** | VCD/FSDB + cell waveform + AMG + adaptive Δt · IR closure | **GAP** |
| **SIGNOFF** | RLC + MOR + direct spot-checks + EM + package | **GAP** |

## Current engine (qualitative leap — honest GAP)

Not: `toggle=1` → arbitrary impulse.
Yes: `I_cell(t) = f(cell, arc, slew, load, state)` from Liberty CCS/ECSM when available.

Nangate45 is **NLDM**. This slice uses triangles da `I_avg` in the GCD mesh.
`pdn_current.py` interpolates `output_current_*` when tables exist (test on synthetic Liberty).
**Do not** synthesize CCS from NLDM. VCD pin-accurate on gate netlist remains GAP (RTL VCD `tb_gcd` does not name ITerms). STA `report_arrival` provides t50 in clock mode — **does not** rescale `I_avg` with OpenSTA activity Hz (would double-count vs `report_power` / spice). SAIF `TC` name-join zeros idle impulses; **does not** invent t50 and **does not** rescale `I_avg` da `TC`. FSDB remains GAP (proprietary binary). Path delay: OpenSTA worst max path, only gates (Q/ZN/…) scalati con \(V_\mathrm{inst}\) a \(t_\mathrm{worst}\); net delay remains nominal. This is not a second liberty at Vmin / CCS delay.

CircuitNet (instance power + toggle + arrival windows + IR) confirms the separation
power + timing window + PDN — is not a dynamic sign-off dataset.

## Scenario engine (not blind 100k cycles)

Heuristics → ranking (one day ML) → physics only on top windows.
MAVIREC is the philosophical reference (screening, not a substitute for the solver).
Here: L3 runs Solver A on windows of `I_tot(t)` of **this** run.
Restart UIC isolated only if \(L=0\) (or idle \(\gg L/R\)); with package L preserves \(i_L\) (prefix \([0,t_\mathrm{cut}]\) or identity if the window covers the horizon). This is not a 100k-cycle scan.

## Reference architecture (EMSim), OpenROAD frontend

```text
cell current (transient) → PWL → rete PDN → TRAN → V(t)/I(t)
```

| Role EMSim | Equivalent here |
|---|---|
| DEF/GDS + xRC | OpenROAD ODB + `write_pg_spice` |
| PrimeTime PX | OpenSTA `report_power` + Liberty NLDM (non CCS I(t)) |
| HSpice | ngspice **oracle** on small RC; Solver A on GCD mesh |
| VCS | Icarus VCD — **non** mappa pin gate |

## Sei livelli (prodotto futuro vs slice attuale)

| Livello | Prodotto “RedHawk-like” | Cosa gira **oggi** on the GCD |
|---|---|---|
| 1 PDN extract | ODB → R/C/via | OpenROAD `write_pg_spice` VDD+VSS + tech LEF; SPEF PG C from PG `*D_NET` (GCD OpenRCX = GAP); Grover on-die L+M estimated (descriptor `--on-die-l`); dual-rail Sink-for pair |
| 2 Power model | Liberty CCS/ECSM I(t) | I_avg da mesh + leak_frac (NLDM); interpolatori CCS+ECSM su `.lib` sintetico |
| 3 Activity | VCD/SAIF/vectorless windows | STA `report_arrival` t50 in clock; SAIF TC name-join (idle-zero, no t50); extra I(t) ranking sintetico; VCD RTL name-join = GAP |
| 4 Current engine | I_cell(t) per arco | triangle per ITerm; CCS \(I(\mathrm{slew},V)\) o ECSM \(\|C\mathrm{d}V/\mathrm{d}t\|\) only with tables |
| 5 Solver | B AMG + C Krylov MOR + D RAS + A gold + sparse-E descriptor | **A + B + C + D READY**; N4 descriptor BE nativo (sparse \(E\), \(n_\mathrm{iv}\)); kind=3 BiCGSTAB workhorse; RAS kind=2 su \(K\) unsymmetric; adaptive Δt descriptor; MOR gen sparse-\(E\) (compact/strap, non default GCD); VSS return TRAN |
| 6 Analysis | map, Vmin, EM, timing, thermal | JSON + CSV + SVG + \(J\) da RPERSQ·L/R + TTF relativo + **thermal mesh strap+via+ILD/Si** + R(T) N1 + **R(T) TRAN** one-shot (not gold) + path STA delay (NLDM typical-V × \((V_\mathrm{dd}/V)^\alpha\)); 3D CFD = GAP |

## Real ranking

| Approccio | Voto | Why |
|---|---|---|
| **Hybrid platform** (OpenROAD + A/B/C + current engine) | ⭐⭐⭐⭐⭐ | Destination. Today only frontend + A + I(t) triangle |
| **EMSim architecture** (current → PWL → PDN TRAN) | ⭐⭐⭐⭐⭐ | Correct A/B split. Declared end: **emanazione EM** (TIFS 2023). README: **VCS, Calibre xRC, PrimeTime PX, HSpice** |
| **OpenROAD + Solver A I(t)+BE** | ⭐⭐⭐⭐⭐ | Unico path *eseguibile* OSS su this GCD (`dynamic_ir`) |
| vyges-em-ir | ⭐⭐⭐⭐ | Bootstrap BE; simultaneousus `switch_t_ns`; **non** the core |
| OpenROAD + ngspice | ⭐⭐⭐ | Physical unit test, not 10M-node engine |

Do not start from vyges. Do not clone EMSim (would require the four licenses).
Do not fork PSM. Si **sostituiscono** i pezzi commerciali one by one.

| EMSim (README) | Substitute here | Fidelity |
|---|---|---|
| Calibre xRC → DSPF power grid | OpenROAD `write_pg_spice` | R mesh PDNSim, non DSPF cell-internal |
| VCS VCD gate-level | Icarus `tb_gcd` | **GAP** pin ITerm |
| PrimeTime PX time-based + `logic_cell_modeling.py` | I_avg in `.sp` + triangle | **PARTIAL** — non waveform PT-PX |
| `logic_cell_to_current_source.py` PWL | 601 PWL per ITerm | triangle shape, not PX report |
| HSpice TRAN | Solver A LU + Solver B SA-AMG; ngspice gold 1-nodo | gold ≠ full-chip |

```text
A  How much does the cell draw?     PARTIAL (triangle from I_avg; CCS interpolator on synthetic .lib)
B  What does the PDN do?              READY   (A gold + B SA-AMG + C descriptor RLC MOR)
```

## What not to do

- Do not fork vyges-em-ir, EMSim o OpenROAD PSM.
- Do not pretend LU a 4k nodi as proof that AMG is useless a full-chip.
- Non mettere ML *dentro* il solver: solo “what to simulate”.
- Do not scaffold `power-integrity/` empty in this repo.
- Do not pretend shared-A as rational Krylov / CCS / Ginkgo GPU.
- Do not pretend MOR RC-only (without \(i_L\)) as gold when \(L>0\).
- Do not fake commercial correlation.

Riferimenti concettuali (non dipendenze): ESPSim, MATEX, Raptor, Ginkgo, Xyce.

Performance-critical numerics live in `engine/` (`libdpn.so`, Eigen SparseLU + SA-AMG). Python orchestrates extraction and I(t).
