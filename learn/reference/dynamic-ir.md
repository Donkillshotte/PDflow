# Dynamic IR on the GCD (I(t) per pin + Solver A current_run + Solver B SA-AMG)

Executable slice of a **hybrid platform**, not a RedHawk and not a fork.
Frontend: OpenROAD `write_pg_spice`. **Solver A** (BE + LU + \(i_L\)) writes **current_run** `dynamic_ir_<variant>_direct.json`. The locked gold **45.298 mV** stays in `dynamic_ir_flowlab.json` on another mesh. **Solver B** (SA-AMG + CG) is the workhorse on the same \(A=G+C/\Delta t+g_\mathrm{eq}\). **Solver C** is MOR: RC on \(\delta v\), or descriptor RLC on \(x=[v;i_L]\) (same physics as the companion). **Solver D** is RAS Schwarz (graph partition, local LU, GMRES). vyges-em-ir is bootstrap.

```text
6_final.odb
    │  OpenROAD PDNSim  write_pg_spice -source_type BUMPS
    ▼
pg_vdd_bumps.sp                 R + I_avg + bump V
pg_vss_bumps.sp                 return-path mesh (Sink-for inst pair; VDD gold unchanged)
inst_power_map.json             placement, seq vs combo (optional)
    │
    ▼
pdn_dynamic.py
    per-ITerm triangle I(t)     clock: STA arrival t50; spatial/simultaneous synthetic
    VCD/SAIF name-join only     RTL tb_gcd → GAP (no silent pin map); SAIF idle-zeros TC=0
    Path STA delay              OpenSTA worst max path on finish SPEF, gate delays × (Vdd/V_inst)^α
    A = G + C/Δt                setup once (independent of I(t))
    Solver A: LU                current_run (`_direct.json`); gold 45.298 is another mesh
    Solver B: SA-AMG + CG       workhorse, |A−B| on the GCD < 1 µV
    Solver C: rational Krylov MOR  descriptor RLC (or RC if L=0)
    Solver D: RAS Schwarz (undirected graph A∪Aᵀ, local LU, GMRES)
    Dual-rail VSS: I(t) copied to coupled sinks; MNA block-diagonal by default;
    C_rr opt-in (`--rail-c`) on instance pin; Cox strap opt-in (`--rail-c-geom`,
    lateral + ILD plate, not gold GCD)
    Native BE loop in libdpn (R+L companion + i_L)
    ▼
sim/reports/dynamic_ir_<variant>.json
                  .wave.csv     Vmin(t), I_tot(t)
                  .map.csv      V, IR per tap
                  .svg          heatmap ITerm
```

## Simulation hierarchy (L0–L3)

vyges-em-ir today is essentially **L1 simultaneous** (all the cells a `switch_t_ns`). Here:

| Level | Idea | GCD status |
|---|---|---|
| **L0 Static** | \(G V = I_\mathrm{avg}\) | READY — same mesh as PDNSim |
| **L1 Vectorless dynamic** | t50 from STA arrival (clock) or synthetic | READY — OpenSTA `report_arrival` rise, folded in SDC period; I_avg not rescaled |
| **L2 VCD/SAIF dynamic** | real times / idle | **GAP** on RTL VCD (`tb_gcd` ≠ ITerm); name-join READY on synthetic VCD/SAIF in tests. SAIF does not invent t50 and does not rescale \(I_\mathrm{avg}\) from TC; TC=0 zeroes the impulse (idle). FSDB = GAP (proprietary binary) |
| **L3 Windowed** | simulates only high-current windows | READY/PARTIAL — BE on windows `I_tot` (isolated if L=0; with pkg L prefix/`i_L`) |

Remaining qualitative leap is **cell → I(t)** model on the GCD (Nangate is NLDM).
The CCS interpolator exists (`pdn_current.py`) and is tested on synthetic Liberty — **does not** invent NLDM→CCS mapping.
Solvers A/B/C/D exist. kind=3 is BiCGSTAB CPU for **non-symmetric** operators (descriptor). **Do not** fork vyges, EMSim or PSM. Ginkgo GPU remains GAP.
Native indices: `int64_t` (`dpn_index_width()==64`). SciPy fallback may stay int32.

## Solver A / B / C / D and product levels

| Solver | Role | GCD |
|---|---|---|
| **A** direct BE + LU | golden | READY (~3 ms setup, faster at 4k nodes) |
| **B** SA-AMG + CG in `libdpn` | workhorse | READY · 5 levels · \|A−B\| ≪ 1 mV · native |
| **C** rational Krylov MOR | reduced ODE, many `I(t)` | **READY** · m=96 · \|A−C\| 0.401 mV (descriptor RLC, \(x=[v;i_L]\)); ranking remains A |
| **D** RAS Schwarz | domain decomposition on \(A\) and on descriptor \(K\) | **READY** companion GCD · ndom=8 · 45.284 mV · \|A−D\| **0.013 mV**; kind=2 on unsymmetric \(K\) (32-node R+L, not the default GCD) |

| Network | Equation | GCD |
|---|---|---|
| N1 R | \(GV=I\) | READY |
| N2 R+C | + `c_decap` | READY |
| **N3 R+C+pkg** | R/L package on bumps | READY — \(g_\mathrm{eq}=1/(R+L/\Delta t)\) + \(i_L\); Grover L on-die **estimated** (Σ partial self, not loop L) + partial mutual cutoff \(d\le 2\,\mu\mathrm{m}\); descriptor TRAN only with `--on-die-l` / `ON_DIE_L=1` (sparse \(E\), \(n_\mathrm{iv}\) bump, not AMG) |
| N4 + VRM | on-die + lumped VRM descriptor | **READY** (native descriptor BE; \|N3−N4\| ≈ 23 nV on this STA-clock window — 47 µF is stiff). Full VRM µs load-step remains `system_pdn` |
| Dual-rail VSS | return path, same \(I(t)\) | **READY** extract+TRAN: `write_pg_spice -net VSS`, pair `* Sink for inst/pin`, bounce = −Vmin; **does not** change gold VDD 45.298 mV; C rail-to-rail **opt-in**: instance pin (`--rail-c` / `RAIL_C=1`, scenario F) and/or strap Cox (`--rail-c-geom` / `RAIL_C_GEOM=1`, ε0εr lateral + ILD plate, not PEX foundry). GCD extract: **6591** lateral pairs, **0** plate (PDN almost all metal1; metal4 is not adjacent), \(C_\Sigma=3.37\,\mathrm{fF}\) — not in default TRAN |

FAST = vectorless + AMG = **READY** (STA t50 in clock). ACCURATE and SIGNOFF = GAP.

On GCD Nangate45 LU is faster than AMG and RAS (4k nodes). AMG/RAS are paths that scale to huge meshes; A remains the oracle. RAS setup 3.6 ms, TRAN ~2.9 s vs LU TRAN ~7.5 ms.

## 6-level pipeline (today)

| # | Level | Today | Honest gap |
|---|---|---|---|
| 1 | PDN extract | OpenROAD `write_pg_spice` VDD+VSS + tech LEF + SPEF PG C name-join + Grover on-die L+M + opt-in strap Cox | GCD OpenRCX SPEF has no VDD `*D_NET` (GAP); signal nets never mapped; on-die L default is estimate-only; mutual is cutoff/partial, not PEEC; dual-rail default is block-diagonal; instance-pin \(C_{rr}\) and overlapping-strap Cox are opt-in, not GCD gold |
| 2 | Power model | I_avg in `.sp` (NLDM) | CCS **and** ECSM interpolators READY on synthetic Liberty; GCD Nangate = GAP (no tables) |
| 3 | Activity | STA `report_arrival` t50 (clock) + SAIF TC name-join | VCD RTL name-join GAP; ranking extra I(t) remains synthetic; SAIF does not invent t50 |
| 4 | Current waveform | triangle per ITerm | CCS lagged \(I(\mathrm{slew},V^n)\) or ECSM \(\|C\mathrm{d}V/\mathrm{d}t\|\) if tables + slew/c_load; Nangate = GAP |
| 5 | Transient solver | **A** LU gold + **B** SA-AMG + **C** descriptor RLC Krylov + **D** RAS (companion GCD; kind=2 on unsymmetric \(K\)) + **N4** native descriptor BE (sparse \(E\), \(n_\mathrm{iv}\)) + kind=3 BiCGSTAB workhorse + adaptive Δt on descriptor + MOR gen sparse-\(E\) (opt-in on-die L, not GCD gold) + VSS return TRAN + opt-in coupled \(C_{rr}\) / strap Cox (sparse \(C\), native `hist_cmat`) | ngspice = gold 1-node RC, R+L, VRM+die, strap K, 1-node thermal analogue, **2-node \(C_{rr}\)/Cox**; Xyce = GAP in VM (deck contract); Native int64 index; Ginkgo GPU = GAP |
| 6 | Analysis | heatmap, windows, ranking, path STA delay, \(J=I/(wt)\), **thermal mesh** strap+via+ILD/Si lumped + **native thermal BE** (max \(\Delta T\)) + **R(T) TRAN** one-shot (Solver A, not gold) | relative TTF (no foundry A); 3D FEM/package CFD = GAP; skin δ reported not printed in G; path = NLDM typical-V; N1 restamp + TRAN weakly-coupled (Si excluded from metric \(\Delta T\)); gold TRAN remains **45.298 mV** |

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_dynamic_ir.sh
# Studio: dynamic_ir action  ·  /tools?tab=run&action=dynamic_ir
# Env: DYNAMIC_IR_MODE=clock|spatial|simultaneous
```

## What it does (and what it does not)

| Piece | This engine | vyges-em-ir | `pdn_transient.py` | PDNSim |
|---|---|---|---|---|
| Static IR | yes (same G) | yes (CG) | yes | yes |
| I(t) | **per pin**, triangle leak+switch | **one** `switch_t_ns` for all | global load-step × peak_factor | I_avg DC |
| t50 | STA arrival (clock) / spatial / simultaneous; SAIF idle-zero | simultaneous | n/a | n/a |
| CCS Liberty / VCD pin | **no** (Nangate is NLDM); VCD name-join GAP on the GCD; SAIF READY only if names join | no | no | no |
| Waveform | **CSV** Vmin(t) | no | CSV | no |
| Heatmap t_worst | **SVG + CSV** | no | no | static ORFS PNG |
| Gold | ngspice 1-node RC + R+L series | — | — | — |

This is not sign-off Ansys RedHawk / Cadence Voltus. Nangate45 does not have CCS current tables. RTL VCD (`tb_gcd`, 10 ns) **does not** name gate pins of the 0.46 ns netlist — no fake mapping. t50 clock = OpenSTA `report_arrival` (join on instance name). Dump STA by default **with** the finish `6_final.spef` (same parasitics as `sta_signoff`; unset `STA_SPEF` only for an ideal-RC experiment). Path delay scales only gates NLDM typical-V, not a liberty at Vmin. An ideal-RC MET overlay is not a WNS close.

## I(t) modes

For every load ITerm: \(I_\mathrm{leak}=f_\mathrm{leak}\,I_\mathrm{avg}\), triangular impulse of duration `DUR_NS` with charge about \((I_\mathrm{avg}-I_\mathrm{leak})\,T_\mathrm{clk}\), clip to `PEAK_FACTOR·I_avg`.

| `DYNAMIC_IR_MODE` | When it switches |
|---|---|
| `simultaneous` | all at `T50_NS` — upper bound, comparable to vyges |
| `spatial` | stagger on X axis |
| `clock` (default) | flip-flop and combo: t50 = rise arrival OpenSTA (folded in period); synthetic fallback if the name does not join |

## GCD flowlab numbers (verified)

Same `pg_vdd_bumps.sp` (~3985 nodes, 13 pad, 601 load, Vdd = 1.1 V, SDC period 0.46 ns).
N3 = companion BE with history of \(i_L\) (not \(L/\Delta t\) memoryless). Droop is no longer 74.715 mV.

| Engine | Static IR | Dynamic droop |
|---|---|---|
| `pdn_transient.py` | 17.52 mV | 154 mV (step ×8 + pkg R/L memoryless) |
| vyges-em-ir 0.1.33 | 17.46 mV | 78.8 mV @ 1.016 ns (simultaneous) |
| **this engine `clock` + STA t50 + \(i_L\)** | **17.52 mV** | **45.298 mV (4.12%) @ 0.27 ns** · I_peak 10.96 mA · STA 601/601 · native_hist |
| Solver B SA-AMG | — | 45.298 mV · \|A−B\| ≪ 1 µV · L5 native |
| Solver C Krylov MOR | — | 44.896 mV · m=96 · \|A−C\| **0.401 mV** · descriptor RLC |
| Solver D RAS Schwarz | — | **45.284 mV** · ndom=8 · \|A−D\| **0.013 mV** · native_hist |
| Dual-rail VSS return | — | **26.707 mV bounce** @ 0.21 ns · 601/601 Sink-for pairs · 3381 nodes / 12 pad (mesh VSS, not VDD) · native_hist. **Not** the gold VDD 45.298 mV |

Ranking Solver A (gold): simultaneous 67.25 mV > spatial 55.31 mV > **clock STA 45.30 mV**.
Extra I(t) (spatial/simultaneous) remains synthetic — the ranking is not STA-vs-stagger.
With \(i_L\), the simultaneous spike is the worst (I_peak 52 mA vs 11 mA clock STA).
The previous synthetic clock (59.925 mV) did not join ITerms (800 dbu radius < VDD pin offset ~1.2 µm).

Gold ngspice: **1 RC node** `|V_BE−V_ng| ≈ 0.032 mV`; **1 pad–R–L–C node** ≈ 0.056 mV (`gear maxord=1`, 5 mV threshold). This is not the chip.

EM: \(I=(V_a-V_b)/R\) and \(J=I/(w t)\) with \(w=\max(\mathrm{RPERSQ}\cdot L/R,\,\mathrm{WIDTH}_\min)\) from tech LEF. Relative TTF \((J_\mathrm{ref}/J)^n\), \(n=2\), \(J_\mathrm{ref}=10^{10}\,\mathrm{A/m^2}\) — **not** foundry hours. \(\Delta T\) **metal-graph** \(G_\mathrm{th}=k_{\mathrm{Cu}}A/L\) on strap **and** adjacent vias (LEF `HEIGHT`/`CUT`) **plus** ILD \(G_\mathrm{ild}=k_{\mathrm{ox}}(w L)/\mathrm{HEIGHT}\) toward a lumped Si node \(G_\mathrm{vert}=k_{\mathrm{Si}}A_\mathrm{die}/t_\mathrm{wafer}\) (\(t=300\,\mu\mathrm{m}\), not GDS) that stars on pads. Without HEIGHT and without via stack remains GAP. Lumped \(R_{\mathrm{th}}I^2R\) remains comparison. This is not an FEM 3D / CFD package. Skin \(\delta\) reported; metal1 Nangate \(t\ll\delta\) at clock GCD \(\Rightarrow R_\mathrm{ac}/R_\mathrm{dc}\approx 1\) (not stamped in \(G\)).

GCD clock STA: \|I\|_max ≈ 2.25 mA (via / strap). \(J_\max\) ≈ \(1.48\times10^{11}\,\mathrm{A/m^2}\) on metal1 (w clamped to 0.07 µm; \(I\) ≈ 1.35 mA) · TTF_rel ≈ \(4.56\times10^{-3}\) · lumped \(\Delta T\) ≈ 11 mK. Thermal mesh on TRAN \(t_\mathrm{worst}\): 5153 strap + 39 via + **ILD→Si** (5153 \(G_\mathrm{ild}\), 1 wafer node \(t=300\,\mu\mathrm{m}\)) + 13 pad · \(\Delta T_\mathrm{mesh}\approx 0.66\,\mathrm{K}\) (metal) · \(\Delta T_\mathrm{Si}\approx 0.057\,\mathrm{K}\) · pad \(\approx 0.028\,\mathrm{K}\) · N1 restamp \(\Delta\)IR \(\approx 0.019\,\mathrm{mV}\) · **R(T) TRAN 45.311 mV (\(\Delta\) +0.013 mV)** one-shot weakly coupled (steady-state \(T\) from \(I_\mathrm{avg}\), then Solver A on \(R(T)\); **does not** enter gold TRAN **45.298 mV**). Thermal tau ≫ \(\Delta t\) electric — is not electro-thermal DAE at step. Without ILD/Si far-node metal-only was ~320 K — wrong path, not gold. Skin \(\delta\approx 1.4\,\mu\mathrm{m}\), \(R_\mathrm{ac}/R_\mathrm{dc}=1\). \(i_L\) bump max ≈ 1.67 mA. Path STA: OpenSTA worst max path, delay gate \(\times(V_\mathrm{dd}/V_\mathrm{inst})^{1.3}\) (NLDM typical-V, not a second liberty at Vmin). L3 prefix BE 38/74 step, \|A−W\|=0 (L/R ≈ 4 ns ≫ 0.74 ns horizon — no isolated restart).

## Files

| Path | Role |
|---|---|
| `learn/scripts/pdn_dynamic.py` | orchestrates extraction + report |
| `learn/scripts/pdn_extract.py` | layer extract: SPICE + tech LEF + probe SPEF (C PG = GAP) |
| `learn/scripts/pdn_em.py` | J from RPERSQ·L/R, relative TTF, thermal mesh strap+via+ILD/Si, skin δ, restamp R(T) N1 |
| `learn/scripts/pdn_dynamic.py` `electrothermal_timestep_be` | one-shot Solver A TRAN on \(R(T)\) (not gold) |
| `learn/scripts/pdn_current.py` | triangle + CCS and ECSM interpolators (never from NLDM) |
| `learn/scripts/pdn_activity.py` | synthetic t50 + STA `report_arrival` + VCD/SAIF name-join + I_tot windows |
| `learn/scripts/export_sta_arrivals.py` | OpenSTA → JSON `by_inst` (rise/fall ns) + `worst_path` (`report_checks -format full`); finish SPEF by default |
| `learn/scripts/pdn_solvers.py` | A/B/C/D + N4 descriptor (libdpn ctypes + SciPy) |
| `learn/scripts/run_dynamic_ir.sh` | GCD + stamp `.dynamic_ir.ok` |
| `learn/scripts/pdn_vrm.py` | N4 descriptor: VRM + bump R+L + mesh |
| `engine/` | `libdpn` LU / SA-AMG / RAS / BE hist / descriptor N4 / RLC MOR / sparse-E gen MOR / descriptor adaptive |

Classroom limits: triangle ≠ CCS; AMG on the GCD is slower than LU (4k nodes); lumped package R/L; PDNSim pads on metal4.

Hybrid platform: [dynamic-ir-landscape.md](./dynamic-ir-landscape.md).

Cross-ref: [vyges-em-ir.md](./vyges-em-ir.md) · [spice-chip-mesh.md](./spice-chip-mesh.md) · [vectorless-power.md](./vectorless-power.md) · [oss-integrations.md](./oss-integrations.md)
