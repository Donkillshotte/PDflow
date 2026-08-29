# Dynamic IR sul GCD (I(t) per pin + Solver A gold + Solver B SA-AMG)

Slice eseguibile di una **piattaforma ibrida**, non un RedHawk e non un fork.
Frontend: OpenROAD `write_pg_spice`. **Solver A** (BE + LU + \(i_L\)) è l’oracle. **Solver B** (SA-AMG + CG) è il workhorse sulla stessa \(A=G+C/\Delta t+g_\mathrm{eq}\). **Solver C** è MOR: RC su \(\delta v\), o descriptor RLC su \(x=[v;i_L]\) (stessa fisica del companion). **Solver D** è RAS Schwarz (partizione sul grafo, LU locali, GMRES). vyges-em-ir è bootstrap.

```text
6_final.odb
    │  OpenROAD PDNSim  write_pg_spice -source_type BUMPS
    ▼
pg_vdd_bumps.sp                 R + I_avg + bump V
inst_power_map.json             placement, seq vs combo (opzionale)
    │
    ▼
pdn_dynamic.py
    per-ITerm triangle I(t)     clock: STA arrival t50; spatial/simultaneous synthetic
    VCD name-join only          RTL tb_gcd → GAP (no silent pin map)
    A = G + C/Δt                setup una volta (indipendente da I(t))
    Solver A: LU                gold
    Solver B: SA-AMG + CG       workhorse, |A−B| sul GCD < 1 µV
    Solver C: rational Krylov MOR  descriptor RLC (o RC se L=0)
    Solver D: RAS Schwarz (grafo, LU locali, GMRES)
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
| **L2 VCD dynamic** | tempi reali di pin | **GAP** — VCD RTL ≠ ITerm gate; name-join only (READY su VCD sintetico nei test) |
| **L3 Windowed** | simula solo finestre ad alta corrente | READY/PARTIAL — BE su finestre `I_tot` (isolato se L=0; con pkg L prefix/`i_L`) |

Il salto qualitativo restante è il modello **cella → I(t)** sul GCD (Nangate è NLDM).
L’interpolatore CCS esiste (`pdn_current.py`) e si testa su Liberty sintetica — **non** si inventa un mapping NLDM→CCS.
I solver A/B/C/D ci sono. **Non** si forka vyges, EMSim o PSM. Ginkgo GPU resta GAP.

## Solver A / B / C / D e livelli prodotto

| Solver | Ruolo | GCD |
|---|---|---|
| **A** direct BE + LU | golden | READY (~3 ms setup, più veloce a 4k nodi) |
| **B** SA-AMG + CG in `libdpn` | workhorse | READY · 5 livelli · \|A−B\| ≪ 1 mV · nativo |
| **C** rational Krylov MOR | reduced ODE, tanti `I(t)` | **READY** · m=96 · \|A−C\| 0.129 mV (descriptor RLC, \(x=[v;i_L]\)); ranking resta A |
| **D** RAS Schwarz | domain decomposition su \(A\) | **READY** · ndom=8 · 59.929 mV · \|A−D\| **0.004 mV** · nativo (LU resta più veloce a 4k nodi) |

| Rete | Equazione | GCD |
|---|---|---|
| N1 R | \(GV=I\) | READY |
| N2 R+C | + `c_decap` | READY |
| N3 + pkg R/L | companion \(g_\mathrm{eq}=1/(R+L/\Delta t)\) + \(i_L\) | READY (L on-die non estratta) |
| N4 + VRM | on-die + lumped VRM descriptor | **READY** (native descriptor BE; \|N3−N4\| ≈ 18 nV on this 0.46 ns window — 47 µF is stiff). Full VRM µs load-step resta `system_pdn` |

FAST = vectorless + AMG = **READY** (STA t50 in clock). ACCURATE e SIGNOFF = GAP.

Sul GCD Nangate45 LU è più veloce di AMG e di RAS (4k nodi). AMG/RAS sono i path che tengono su mesh enormi; A resta l’oracle. RAS setup 3.6 ms, TRAN ~2.9 s vs LU TRAN ~7.5 ms.

## Pipeline a 6 livelli (oggi)

| # | Livello | Oggi | Gap onesto |
|---|---|---|---|
| 1 | PDN extract | OpenROAD `write_pg_spice` + tech LEF | SPEF PG C never mapped from signal nets |
| 2 | Power model | I_avg nel `.sp` (NLDM) | interpolatore CCS READY su Liberty sintetica; GCD Nangate = GAP |
| 3 | Activity | STA `report_arrival` t50 (clock) | VCD RTL name-join GAP; ranking extra I(t) resta sintetico |
| 4 | Current waveform | triangolo per ITerm | CCS lagged \(I(\mathrm{slew},V^n)\) in Python TRAN se tabelle + slew; Nangate = GAP |
| 5 | Transient solver | **A** LU gold + **B** SA-AMG + **C** descriptor RLC Krylov + **D** RAS + **N4** descriptor BE nativo | ngspice = gold 1-nodo RC, R+L, VRM+die |
| 6 | Analysis | heatmap, finestre, ranking, delay scaling, \(J=I/(wt)\) | TTF relativo (no A foundry); R(T) lumpato one-shot N1, non mesh 3D |

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
| t50 | STA arrival (clock) / spatial / simultaneous | simultaneo | n/a | n/a |
| CCS Liberty / VCD pin | **no** (Nangate è NLDM); VCD name-join GAP sul GCD | no | no | no |
| Waveform | **CSV** Vmin(t) | no | CSV | no |
| Heatmap t_worst | **SVG + CSV** | no | no | PNG statico ORFS |
| Gold | ngspice 1-nodo RC + serie R+L | — | — | — |

Non è sign-off Ansys RedHawk / Cadence Voltus. Nangate45 non ha tabelle CCS di corrente. Il VCD RTL (`tb_gcd`, 10 ns) **non** nomina i pin gate del netlist 0.46 ns — non si finge un mapping. t50 clock = OpenSTA `report_arrival` (join sul nome istanza).

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
| **questo engine `clock` + \(i_L\)** | **17.52 mV** | **59.925 mV (5.45%) @ 0.33 ns** · I_peak 21.7 mA · native_hist |
| Solver B SA-AMG | — | 59.925 mV · \|A−B\| ≪ 1 µV · L5 native |
| Solver C Krylov MOR | — | 60.054 mV · m=96 · \|A−C\| **0.129 mV** · descriptor RLC |
| Solver D RAS Schwarz | — | **59.929 mV** · ndom=8 · \|A−D\| **0.004 mV** · native_hist |

Ranking Solver A (gold): simultaneous 67.25 mV > clock 59.93 mV > spatial 55.31 mV.
Con \(i_L\), lo spike simultaneo è il peggiore (I_peak 52 mA vs 22 mA clock) — il contrario della slice memoryless.

Gold ngspice: **1 nodo RC** `|V_BE−V_ng| ≈ 0.032 mV`; **1 nodo pad–R–L–C** ≈ 0.056 mV (`gear maxord=1`, soglia 5 mV). Non è il chip.

EM: \(I=(V_a-V_b)/R\) e \(J=I/(w t)\) con \(w=\max(\mathrm{RPERSQ}\cdot L/R,\,\mathrm{WIDTH}_\min)\) dal tech LEF. TTF relativo \((J_\mathrm{ref}/J)^n\), \(n=2\), \(J_\mathrm{ref}=10^{10}\,\mathrm{A/m^2}\) — **non** ore foundry. \(\Delta T=R_\mathrm{th} I^2 R\) lumpato, restamp N1 \(R(T)\).

GCD clock: \|I\|_max ≈ 3.04 mA (via M3–M4, no J). \(J_\max\) ≈ \(2.68\times10^{11}\,\mathrm{A/m^2}\) su metal1 (w clampato a 0.07 µm; \(I\) ≈ 2.44 mA) · TTF_rel ≈ \(1.39\times10^{-3}\) · \(\Delta T\) lumpato ≈ 20 mK · \(\Delta\)IR \(R(T)\) ≈ 0.63 µV. \(i_L\) bump max ≈ 2.38 mA. Path STA (delay su un path timed) = GAP. t50 clock = STA arrival (i numeri di droop **sopra** sono il run sintetico pre-STA; il run STA aggiorna droop e t_worst).

## File

| Path | Ruolo |
|---|---|
| `learn/scripts/pdn_dynamic.py` | orchestrazione + report |
| `learn/scripts/pdn_extract.py` | layer extract: SPICE + tech LEF + probe SPEF (C PG = GAP) |
| `learn/scripts/pdn_em.py` | J da RPERSQ·L/R, TTF relativo, restamp R(T) lumpato |
| `learn/scripts/pdn_current.py` | triangolo + probe/interpolatore CCS |
| `learn/scripts/pdn_activity.py` | t50 sintetici + STA `report_arrival` + VCD name-join + finestre I_tot |
| `learn/scripts/export_sta_arrivals.py` | OpenSTA → JSON `by_inst` (rise/fall ns) |
| `learn/scripts/pdn_solvers.py` | A/B/C/D + N4 descriptor (libdpn ctypes + SciPy) |
| `learn/scripts/run_dynamic_ir.sh` | GCD + stamp `.dynamic_ir.ok` |
| `learn/scripts/pdn_vrm.py` | N4 descriptor: VRM + bump R+L + mesh |
| `engine/` | `libdpn` LU / SA-AMG / RAS / BE hist / descriptor N4 / RLC MOR |

Limiti in aula: triangolo ≠ CCS; AMG sul GCD è più lento di LU (4k nodi); package R/L lumpato; pad PDNSim su metal4.

Piattaforma ibrida: [dynamic-ir-landscape.md](./dynamic-ir-landscape.md).

Cross-ref: [vyges-em-ir.md](./vyges-em-ir.md) · [spice-chip-mesh.md](./spice-chip-mesh.md) · [vectorless-power.md](./vectorless-power.md) · [oss-integrations.md](./oss-integrations.md)
