# Dynamic IR sul GCD (I(t) per pin + Solver A golden)

Slice eseguibile di una **piattaforma ibrida**, non un RedHawk e non un fork.
Frontend: OpenROAD `write_pg_spice`. Motore: **Solver A** (backward Euler + LU sparso) come **gold**, non come workhorse.
Solver B (SA-AMG) e Solver C (rational Krylov / MOR) sono GAP. vyges-em-ir è bootstrap / check simultaneous-switch.

```text
6_final.odb
    │  OpenROAD PDNSim  write_pg_spice -source_type BUMPS
    ▼
pg_vdd_bumps.sp                 R + I_avg + bump V
inst_power_map.json             placement, seq vs combo (opzionale)
    │
    ▼
pdn_dynamic.py
    per-ITerm triangle I(t)     simultaneous | spatial | clock
    Solver A: (G + C/Δt) V_{n+1} = I_{n+1} + (C/Δt) V_n
    sparse LU una volta, poi timestep   ← gold, non AMG/MOR
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
| **L1 Vectorless dynamic** | t50 sintetici (clock / spatial / simultaneous) | READY — non finestre STA |
| **L2 VCD dynamic** | tempi reali di pin | **GAP** — VCD RTL ≠ ITerm gate |
| **L3 Windowed** | simula solo finestre ad alta corrente | PARTIAL — finestre su `I_tot(t)` di **questo** run |

Il salto qualitativo del prodotto è il modello **cella → I(t)** (CCS/arco/slew/load), non il solver.
Solver A sul GCD è il **gold**. Il workhorse futuro è B (AMG); il riuso multi-scenario è C (MOR).
**Non** si forka vyges, EMSim o PSM. **Non** si implementa AMG/CCS/GPU in questa slice.

## Solver A / B / C e livelli prodotto

| Solver | Ruolo | GCD |
|---|---|---|
| **A** direct BE + LU | golden | READY |
| **B** SA-AMG | workhorse full-chip | GAP |
| **C** Krylov/MOR | stessa PDN, tanti `I(t)` | GAP |

| Rete | Equazione | GCD |
|---|---|---|
| N1 R | \(GV=I\) | READY |
| N2 R+C | + `c_decap` | READY |
| N3 + pkg R/L | `pkg_r` / `pkg_l` sui bump | READY (L on-die non estratta) |
| N4 + VRM | on-die + package + VRM | PARTIAL (`system_pdn` non accoppiato) |

FAST = vectorless+AMG (PARTIAL: abbiamo t50 sintetici + A). ACCURATE e SIGNOFF = GAP.

## Pipeline a 6 livelli (oggi)

| # | Livello | Oggi | Gap onesto |
|---|---|---|---|
| 1 | PDN extract | OpenROAD `write_pg_spice` | non DEF+LEF nativo vyges su Nangate |
| 2 | Power model | I_avg nel `.sp` (NLDM) | no CCS I(t) |
| 3 | Activity | clock/spatial/simultaneous | no VCD pin, no SAIF |
| 4 | Current waveform | triangolo per ITerm | no slew/load/arc |
| 5 | Transient solver | **Solver A** BE + LU | B AMG / C MOR = GAP; ngspice = gold 1-nodo |
| 6 | Analysis | heatmap, Vmin(t), finestre, hotspot seq/combo | no EM, no delay vs V |

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
| t50 | clock / spatial / simultaneous | simultaneo | n/a | n/a |
| Waveform | **CSV** Vmin(t) | no | CSV | no |
| Heatmap t_worst | **SVG + CSV** | no | no | PNG statico ORFS |
| Gold | ngspice 1-nodo (gear BE) | — | — | — |
| CCS Liberty / VCD pin | **no** (Nangate è NLDM) | no | no | no |

Non è sign-off Ansys RedHawk / Cadence Voltus. Nangate45 non ha tabelle CCS di corrente. Il VCD RTL (`tb_gcd`, 10 ns) **non** nomina i pin gate del netlist 0.46 ns — non si finge un mapping.

## Modi I(t)

Per ogni load ITerm: \(I_\mathrm{leak}=f_\mathrm{leak}\,I_\mathrm{avg}\), impulso triangolare di durata `DUR_NS` con carica circa \((I_\mathrm{avg}-I_\mathrm{leak})\,T_\mathrm{clk}\), clip a `PEAK_FACTOR·I_avg`.

| `DYNAMIC_IR_MODE` | Quando commuta |
|---|---|
| `simultaneous` | tutte a `T50_NS` — upper bound, confrontabile con vyges |
| `spatial` | stagger sull’asse X |
| `clock` (default) | flip-flop sul fronte; combo ritardata + stagger X |

## Numeri GCD flowlab (verificati)

Stesso `pg_vdd_bumps.sp` (~3972 nodi, 13 pad, 601 load, Vdd = 1.1 V, periodo SDC 0.46 ns).

| Engine | Static IR | Dynamic droop |
|---|---|---|
| `pdn_transient.py` | 17.52 mV | 154 mV (step ×8 + pkg R/L) |
| vyges-em-ir 0.1.33 | 17.46 mV | 78.8 mV @ 1.016 ns (simultaneous) |
| **questo engine `clock`** | **17.52 mV** | **~75 mV @ ~0.34 ns** (stagger; I_peak ~22 mA) |

Lo statico coincide. Il dinamico `clock` è **sotto** vyges simultaneous perché i t50 non sono allineati. Non è un FAIL di tapeout: è un laboratorio di droop.

Gold ngspice: circuito **1 nodo** RC + triangolo (non il chip). `|V_BE − V_ngspice| ≈ 0.03 mV` sul GCD run con `method=gear maxord=1` (soglia 5 mV).

## File

| Path | Ruolo |
|---|---|
| `learn/scripts/pdn_dynamic.py` | I(t) + BE + SVG |
| `learn/scripts/run_dynamic_ir.sh` | GCD + stamp `.dynamic_ir.ok` |
| `sim/reports/dynamic_ir_<variant>.*` | JSON / wave / map / SVG |

Limiti in aula: triangolo ≠ CCS; Solver A ≠ workhorse; nessun AMG/Krylov/GPU; package R/L come in `pdn_transient`; pad PDNSim su metal4.

Piattaforma ibrida (A/B/C, FAST/ACCURATE/SIGNOFF, perché **non** forkare): [dynamic-ir-landscape.md](./dynamic-ir-landscape.md).

Cross-ref: [vyges-em-ir.md](./vyges-em-ir.md) · [spice-chip-mesh.md](./spice-chip-mesh.md) · [vectorless-power.md](./vectorless-power.md) · [oss-integrations.md](./oss-integrations.md)
