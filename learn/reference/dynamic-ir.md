# Dynamic IR sul GCD (I(t) per pin + Solver A gold + Solver B SA-AMG)

Slice eseguibile di una **piattaforma ibrida**, non un RedHawk e non un fork.
Frontend: OpenROAD `write_pg_spice`. **Solver A** (BE + LU + \(i_L\)) è l’oracle. **Solver B** (SA-AMG + CG) è il workhorse sulla stessa \(A=G+C/\Delta t+g_\mathrm{eq}\). **Solver C** è MOR: RC su \(\delta v\), o descriptor RLC su \(x=[v;i_L]\) (stessa fisica del companion). **Solver D** è RAS Schwarz (partizione sul grafo, LU locali, GMRES). vyges-em-ir è bootstrap.

```text
6_final.odb
    │  OpenROAD PDNSim  write_pg_spice -source_type BUMPS
    ▼
pg_vdd_bumps.sp                 R + I_avg + bump V
pg_vss_bumps.sp                 return-path mesh (Sink-for inst pair; VDD gold unchanged)
inst_power_map.json             placement, seq vs combo (opzionale)
    │
    ▼
pdn_dynamic.py
    per-ITerm triangle I(t)     clock: STA arrival t50; spatial/simultaneous synthetic
    VCD/SAIF name-join only     RTL tb_gcd → GAP (no silent pin map); SAIF idle-zeros TC=0
    Path STA delay              OpenSTA worst max path, gate delays × (Vdd/V_inst)^α
    A = G + C/Δt                setup una volta (indipendente da I(t))
    Solver A: LU                gold
    Solver B: SA-AMG + CG       workhorse, |A−B| sul GCD < 1 µV
    Solver C: rational Krylov MOR  descriptor RLC (o RC se L=0)
    Solver D: RAS Schwarz (grafo undirected A∪Aᵀ, LU locali, GMRES)
    Dual-rail VSS: I(t) copiato sui sink accoppiati; MNA block-diagonal di default;
    C_rr opt-in (`--rail-c`) su pin istanza; Cox strap opt-in (`--rail-c-geom`,
    laterale + piastra ILD, non gold GCD)
    Native BE loop in libdpn (R+L companion + i_L)
    ▼
sim/reports/dynamic_ir_<variant>.json
                  .wave.csv     Vmin(t), I_tot(t)
                  .map.csv      V, IR per tap
                  .svg          heatmap ITerm
```

## Gerarchia di simulazione (L0–L3)

vyges-em-ir oggi è essenzialmente **L1 simultaneous** (tutte le celle a `switch_t_ns`). Qui:

| Livello | Idea | Stato GCD |
|---|---|---|
| **L0 Static** | \(G V = I_\mathrm{avg}\) | READY — stesso mesh di PDNSim |
| **L1 Vectorless dynamic** | t50 da STA arrival (clock) o sintetici | READY — OpenSTA `report_arrival` rise, folded nel periodo SDC; I_avg non riscalato |
| **L2 VCD/SAIF dynamic** | tempi reali / idle | **GAP** sul VCD RTL (`tb_gcd` ≠ ITerm); name-join READY su VCD/SAIF sintetici nei test. SAIF non inventa t50 e non riscala \(I_\mathrm{avg}\) da TC; TC=0 azzera l’impulso (idle). FSDB = GAP (binario proprietario) |
| **L3 Windowed** | simula solo finestre ad alta corrente | READY/PARTIAL — BE su finestre `I_tot` (isolato se L=0; con pkg L prefix/`i_L`) |

Il salto qualitativo restante è il modello **cella → I(t)** sul GCD (Nangate è NLDM).
L’interpolatore CCS esiste (`pdn_current.py`) e si testa su Liberty sintetica — **non** si inventa un mapping NLDM→CCS.
I solver A/B/C/D ci sono. kind=3 è BiCGSTAB CPU per operatori **non simmetrici** (descriptor). **Non** si forka vyges, EMSim o PSM. Ginkgo GPU resta GAP.
Indici nativi: `int64_t` (`dpn_index_width()==64`). SciPy fallback può restare int32.

## Solver A / B / C / D e livelli prodotto

| Solver | Ruolo | GCD |
|---|---|---|
| **A** direct BE + LU | golden | READY (~3 ms setup, più veloce a 4k nodi) |
| **B** SA-AMG + CG in `libdpn` | workhorse | READY · 5 livelli · \|A−B\| ≪ 1 mV · nativo |
| **C** rational Krylov MOR | reduced ODE, tanti `I(t)` | **READY** · m=96 · \|A−C\| 0.401 mV (descriptor RLC, \(x=[v;i_L]\)); ranking resta A |
| **D** RAS Schwarz | domain decomposition su \(A\) e su \(K\) descriptor | **READY** companion GCD · ndom=8 · 45.284 mV · \|A−D\| **0.013 mV**; kind=2 su \(K\) unsymmetric (32-nodo R+L, non il default GCD) |

| Rete | Equazione | GCD |
|---|---|---|
| N1 R | \(GV=I\) | READY |
| N2 R+C | + `c_decap` | READY |
| **N3 R+C+pkg** | R/L package sui bump | READY — \(g_\mathrm{eq}=1/(R+L/\Delta t)\) + \(i_L\); Grover L on-die **stimata** (Σ partial self, non loop L) + mutual parziale cutoff \(d\le 2\,\mu\mathrm{m}\); descriptor TRAN solo con `--on-die-l` / `ON_DIE_L=1` (sparse \(E\), \(n_\mathrm{iv}\) bump, non AMG) |
| N4 + VRM | on-die + lumped VRM descriptor | **READY** (native descriptor BE; \|N3−N4\| ≈ 23 nV on this STA-clock window — 47 µF is stiff). Full VRM µs load-step resta `system_pdn` |
| Dual-rail VSS | return path, same \(I(t)\) | **READY** extract+TRAN: `write_pg_spice -net VSS`, pair `* Sink for inst/pin`, bounce = −Vmin; **non** cambia il gold VDD 45.298 mV; C rail-to-rail **opt-in**: pin istanza (`--rail-c` / `RAIL_C=1`, scenario F) e/o Cox di strap (`--rail-c-geom` / `RAIL_C_GEOM=1`, ε0εr laterale + piastra ILD, non PEX foundry). GCD extract: **6591** coppie laterali, **0** piastra (PDN quasi tutto metal1; metal4 non è adiacente), \(C_\Sigma=3.37\,\mathrm{fF}\) — non entra nel TRAN default |

FAST = vectorless + AMG = **READY** (STA t50 in clock). ACCURATE e SIGNOFF = GAP.

Sul GCD Nangate45 LU è più veloce di AMG e di RAS (4k nodi). AMG/RAS sono i path che tengono su mesh enormi; A resta l’oracle. RAS setup 3.6 ms, TRAN ~2.9 s vs LU TRAN ~7.5 ms.

## Pipeline a 6 livelli (oggi)

| # | Livello | Oggi | Gap onesto |
|---|---|---|---|
| 1 | PDN extract | OpenROAD `write_pg_spice` VDD+VSS + tech LEF + SPEF PG C name-join + Grover on-die L+M + opt-in strap Cox | GCD OpenRCX SPEF has no VDD `*D_NET` (GAP); signal nets never mapped; on-die L default is estimate-only; mutual is cutoff/partial, not PEEC; dual-rail default is block-diagonal; instance-pin \(C_{rr}\) and overlapping-strap Cox are opt-in, not GCD gold |
| 2 | Power model | I_avg nel `.sp` (NLDM) | interpolatori CCS **e** ECSM READY su Liberty sintetica; GCD Nangate = GAP (no tabelle) |
| 3 | Activity | STA `report_arrival` t50 (clock) + SAIF TC name-join | VCD RTL name-join GAP; ranking extra I(t) resta sintetico; SAIF non inventa t50 |
| 4 | Current waveform | triangolo per ITerm | CCS lagged \(I(\mathrm{slew},V^n)\) o ECSM \(\|C\mathrm{d}V/\mathrm{d}t\|\) se tabelle + slew/c_load; Nangate = GAP |
| 5 | Transient solver | **A** LU gold + **B** SA-AMG + **C** descriptor RLC Krylov + **D** RAS (companion GCD; kind=2 su \(K\) unsymmetric) + **N4** descriptor BE nativo (sparse \(E\), \(n_\mathrm{iv}\)) + kind=3 BiCGSTAB workhorse + Δt adattivo sul descriptor + MOR gen sparse-\(E\) (opt-in on-die L, non il gold GCD) + VSS return TRAN + opt-in coupled \(C_{rr}\) / strap Cox (sparse \(C\), native `hist_cmat`) | ngspice = gold 1-nodo RC, R+L, VRM+die, strap K, 1-nodo thermal analogue, **2-nodo \(C_{rr}\)/Cox**; Xyce = GAP in VM (deck contract); Index nativo int64; Ginkgo GPU = GAP |
| 6 | Analysis | heatmap, finestre, ranking, path STA delay, \(J=I/(wt)\), **mesh termica** strap+via+ILD/Si lumpato + **BE termico nativo** (max \(\Delta T\)) + **R(T) TRAN** one-shot (Solver A, non gold) | TTF relativo (no A foundry); 3D FEM/package CFD = GAP; skin δ riportato non stampato in G; path = NLDM typical-V; restamp N1 + TRAN weakly-coupled (Si escluso dalla metrica \(\Delta T\)); gold TRAN resta **45.298 mV** |

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_dynamic_ir.sh
# Studio: azione dynamic_ir  ·  /strumenti?tab=run&action=dynamic_ir
# Env: DYNAMIC_IR_MODE=clock|spatial|simultaneous
```

## Cosa fa (e cosa no)

| Pezzo | Questo engine | vyges-em-ir | `pdn_transient.py` | PDNSim |
|---|---|---|---|---|
| Static IR | sì (stesso G) | sì (CG) | sì | sì |
| I(t) | **per pin**, triangolo leak+switch | **un** `switch_t_ns` per tutte | load-step globale × peak_factor | I_avg DC |
| t50 | STA arrival (clock) / spatial / simultaneous; SAIF idle-zero | simultaneo | n/a | n/a |
| CCS Liberty / VCD pin | **no** (Nangate è NLDM); VCD name-join GAP sul GCD; SAIF READY solo se i nomi join-ano | no | no | no |
| Waveform | **CSV** Vmin(t) | no | CSV | no |
| Heatmap t_worst | **SVG + CSV** | no | no | PNG statico ORFS |
| Gold | ngspice 1-nodo RC + serie R+L | — | — | — |

Non è sign-off Ansys RedHawk / Cadence Voltus. Nangate45 non ha tabelle CCS di corrente. Il VCD RTL (`tb_gcd`, 10 ns) **non** nomina i pin gate del netlist 0.46 ns — non si finge un mapping. t50 clock = OpenSTA `report_arrival` (join sul nome istanza). Dump STA di default **senza SPEF** (interconnect ideale; `STA_SPEF` per OpenRCX). Path delay scala solo i gate NLDM typical-V, non una liberty a Vmin.

## Modi I(t)

Per ogni load ITerm: \(I_\mathrm{leak}=f_\mathrm{leak}\,I_\mathrm{avg}\), impulso triangolare di durata `DUR_NS` con carica circa \((I_\mathrm{avg}-I_\mathrm{leak})\,T_\mathrm{clk}\), clip a `PEAK_FACTOR·I_avg`.

| `DYNAMIC_IR_MODE` | Quando commuta |
|---|---|
| `simultaneous` | tutte a `T50_NS` — upper bound, confrontabile con vyges |
| `spatial` | stagger sull’asse X |
| `clock` (default) | flip-flop e combo: t50 = rise arrival OpenSTA (folded nel periodo); fallback sintetico se il nome non join-a |

## Numeri GCD flowlab (verificati)

Stesso `pg_vdd_bumps.sp` (~3985 nodi, 13 pad, 601 load, Vdd = 1.1 V, periodo SDC 0.46 ns).
N3 = companion BE con storia di \(i_L\) (non \(L/\Delta t\) memoryless). Il droop **non** è più 74.715 mV.

| Engine | Static IR | Dynamic droop |
|---|---|---|
| `pdn_transient.py` | 17.52 mV | 154 mV (step ×8 + pkg R/L memoryless) |
| vyges-em-ir 0.1.33 | 17.46 mV | 78.8 mV @ 1.016 ns (simultaneous) |
| **questo engine `clock` + STA t50 + \(i_L\)** | **17.52 mV** | **45.298 mV (4.12%) @ 0.27 ns** · I_peak 10.96 mA · STA 601/601 · native_hist |
| Solver B SA-AMG | — | 45.298 mV · \|A−B\| ≪ 1 µV · L5 native |
| Solver C Krylov MOR | — | 44.896 mV · m=96 · \|A−C\| **0.401 mV** · descriptor RLC |
| Solver D RAS Schwarz | — | **45.284 mV** · ndom=8 · \|A−D\| **0.013 mV** · native_hist |
| Dual-rail VSS return | — | **26.707 mV bounce** @ 0.21 ns · 601/601 Sink-for pairs · 3381 nodi / 12 pad (mesh VSS, non VDD) · native_hist. **Non** è il gold VDD 45.298 mV |

Ranking Solver A (gold): simultaneous 67.25 mV > spatial 55.31 mV > **clock STA 45.30 mV**.
Extra I(t) (spatial/simultaneous) resta sintetico — il ranking non è STA-vs-stagger.
Con \(i_L\), lo spike simultaneo è il peggiore (I_peak 52 mA vs 11 mA clock STA).
Il clock sintetico precedente (59.925 mV) non join-ava gli ITerm (raggio 800 dbu < offset pin VDD ~1.2 µm).

Gold ngspice: **1 nodo RC** `|V_BE−V_ng| ≈ 0.032 mV`; **1 nodo pad–R–L–C** ≈ 0.056 mV (`gear maxord=1`, soglia 5 mV). Non è il chip.

EM: \(I=(V_a-V_b)/R\) e \(J=I/(w t)\) con \(w=\max(\mathrm{RPERSQ}\cdot L/R,\,\mathrm{WIDTH}_\min)\) dal tech LEF. TTF relativo \((J_\mathrm{ref}/J)^n\), \(n=2\), \(J_\mathrm{ref}=10^{10}\,\mathrm{A/m^2}\) — **non** ore foundry. \(\Delta T\) **metal-graph** \(G_\mathrm{th}=k_{\mathrm{Cu}}A/L\) su strap **e** via adiacenti (LEF `HEIGHT`/`CUT`) **più** ILD \(G_\mathrm{ild}=k_{\mathrm{ox}}(w L)/\mathrm{HEIGHT}\) verso un nodo Si lumpato \(G_\mathrm{vert}=k_{\mathrm{Si}}A_\mathrm{die}/t_\mathrm{wafer}\) (\(t=300\,\mu\mathrm{m}\), non GDS) che stella sui pad. Senza HEIGHT e senza via lo stack resta GAP. Lumped \(R_{\mathrm{th}}I^2R\) resta confronto. Non è un FEM 3D / CFD package. Skin \(\delta\) riportato; metal1 Nangate \(t\ll\delta\) al clock GCD \(\Rightarrow R_\mathrm{ac}/R_\mathrm{dc}\approx 1\) (non stampato in \(G\)).

GCD clock STA: \|I\|_max ≈ 2.25 mA (via / strap). \(J_\max\) ≈ \(1.48\times10^{11}\,\mathrm{A/m^2}\) su metal1 (w clampato a 0.07 µm; \(I\) ≈ 1.35 mA) · TTF_rel ≈ \(4.56\times10^{-3}\) · \(\Delta T\) lumpato ≈ 11 mK. Mesh termica sul TRAN \(t_\mathrm{worst}\): 5153 strap + 39 via + **ILD→Si** (5153 \(G_\mathrm{ild}\), 1 nodo wafer \(t=300\,\mu\mathrm{m}\)) + 13 pad · \(\Delta T_\mathrm{mesh}\approx 0.66\,\mathrm{K}\) (metal) · \(\Delta T_\mathrm{Si}\approx 0.057\,\mathrm{K}\) · pad \(\approx 0.028\,\mathrm{K}\) · restamp N1 \(\Delta\)IR \(\approx 0.019\,\mathrm{mV}\) · **R(T) TRAN 45.311 mV (\(\Delta\) +0.013 mV)** one-shot weakly coupled (\(T\) stazionario da \(I_\mathrm{avg}\), poi Solver A su \(R(T)\); **non** entra nel gold TRAN **45.298 mV**). Tau termica ≫ \(\Delta t\) elettrico — non è un DAE elettrotermico al passo. Senza ILD/Si il far-node metal-only era ~320 K — path sbagliato, non un gold. Skin \(\delta\approx 1.4\,\mu\mathrm{m}\), \(R_\mathrm{ac}/R_\mathrm{dc}=1\). \(i_L\) bump max ≈ 1.67 mA. Path STA: OpenSTA worst max path, delay gate \(\times(V_\mathrm{dd}/V_\mathrm{inst})^{1.3}\) (NLDM typical-V, non una seconda liberty a Vmin). L3 prefix BE 38/74 step, \|A−W\|=0 (L/R ≈ 4 ns ≫ orizzonte 0.74 ns — niente restart isolato).

## File

| Path | Ruolo |
|---|---|
| `learn/scripts/pdn_dynamic.py` | orchestrazione + report |
| `learn/scripts/pdn_extract.py` | layer extract: SPICE + tech LEF + probe SPEF (C PG = GAP) |
| `learn/scripts/pdn_em.py` | J da RPERSQ·L/R, TTF relativo, mesh termica strap+via+ILD/Si, skin δ, restamp R(T) N1 |
| `learn/scripts/pdn_dynamic.py` `electrothermal_timestep_be` | one-shot Solver A TRAN su \(R(T)\) (non gold) |
| `learn/scripts/pdn_current.py` | triangolo + interpolatori CCS e ECSM (mai da NLDM) |
| `learn/scripts/pdn_activity.py` | t50 sintetici + STA `report_arrival` + VCD/SAIF name-join + finestre I_tot |
| `learn/scripts/export_sta_arrivals.py` | OpenSTA → JSON `by_inst` (rise/fall ns) + `worst_path` (`report_checks -format full`) |
| `learn/scripts/pdn_solvers.py` | A/B/C/D + N4 descriptor (libdpn ctypes + SciPy) |
| `learn/scripts/run_dynamic_ir.sh` | GCD + stamp `.dynamic_ir.ok` |
| `learn/scripts/pdn_vrm.py` | N4 descriptor: VRM + bump R+L + mesh |
| `engine/` | `libdpn` LU / SA-AMG / RAS / BE hist / descriptor N4 / RLC MOR / sparse-E gen MOR / descriptor adaptive |

Limiti in aula: triangolo ≠ CCS; AMG sul GCD è più lento di LU (4k nodi); package R/L lumpato; pad PDNSim su metal4.

Piattaforma ibrida: [dynamic-ir-landscape.md](./dynamic-ir-landscape.md).

Cross-ref: [vyges-em-ir.md](./vyges-em-ir.md) · [spice-chip-mesh.md](./spice-chip-mesh.md) · [vectorless-power.md](./vectorless-power.md) · [oss-integrations.md](./oss-integrations.md)
