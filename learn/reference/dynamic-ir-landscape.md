# Landscape Dynamic IR / PDN (open-source)

Domanda: *c’è un RedHawk Dynamic open-source?* Risposta onesta: **no**. Ci sono pezzi riutilizzabili e un’architettura che ha senso. Questo corso **non** costruisce AMG, rational Krylov, CCS, GPU, né un fork di vyges / EMSim / OpenROAD PSM.

## Matrice (ciò che esiste davvero)

| Tool | Static IR | Dynamic / transient | EM | PDN da DEF | Switching | Note sul GCD Nangate45 |
|---|---|---|---|---|---|---|
| OpenROAD PSM / PDNSim | sì | **no** (docs: static IR analyzer) | current density | sì (ODB) | I_avg da liberty/activity | `analyze_power_grid` + `write_pg_spice` |
| **vyges-em-ir** | sì (CG+Jacobi) | sì, BE, **un** `switch_t_ns` | sì (se `emlimit`) | DEF+LEF upstream; qui mesh SPICE | eventi, tutti allineati | prototipo; no waveform |
| **Questo corso `dynamic_ir`** | sì | sì, BE LU, I(t) per pin | no | mesh OpenROAD | simultaneous / spatial / **clock** | waveform + heatmap |
| `pdn_transient.py` | sì | load-step globale | no | mesh OpenROAD | peak_factor | laboratorio CSV |
| ngspice | sì | sì | possibile | da costruire | PWL | **gold 1-nodo**, non full-chip |
| Xyce | sì | sì (MPI) | — | da costruire | sì | **GAP** in questa VM |
| [EMSim](https://github.com/jinyier/EMSim) | sì | sì (PWL → TRAN) | sì | Calibre xRC | PrimeTime PX | **VCS / Calibre / PT-PX / HSpice** — non drop-in OSS |
| VoltSpot | arch-level | arch | — | no gate PDN | arch traces | non è cell-level |
| IREDGe / PowerNet / MAVIREC | ML IR | screening | — | feature IR | vettori | **non** physics sign-off |
| RedHawk / Voltus / Totem | sì | sì | sì | sì | sì | commerciale |

OpenROAD PSM resta **static IR**. vyges-em-ir è il prototipo BE più vicino a un mini-RedHawk, con tre limiti dichiarati: switch simultaneo, timestep interno, niente waveform.

## Architettura di riferimento (EMSim), frontend OpenROAD

EMSim ha già la split giusta:

```text
cell current (transient) → PWL → rete PDN → TRAN → V(t)/I(t)
```

Dipendenze commerciali: non si “portano” nel corso. Al loro posto:

| Ruolo EMSim | Equivalente qui |
|---|---|
| DEF/GDS + xRC | OpenROAD ODB + `write_pg_spice` |
| PrimeTime PX | OpenSTA `report_power` + Liberty NLDM (non CCS I(t)) |
| HSpice | ngspice **oracle** su RC piccolo; questo BE sul mesh GCD |
| VCS | Icarus VCD — **non** mappa pin gate |

## Sei livelli (prodotto futuro vs slice attuale)

| Livello | Prodotto “RedHawk-like” | Cosa gira **oggi** sul GCD |
|---|---|---|
| 1 PDN extract | ODB → R/C/via | OpenROAD `write_pg_spice` |
| 2 Power model | Liberty CCS/ECSM I(t) | I_avg da mesh + leak_frac (NLDM) |
| 3 Activity | VCD/SAIF/vectorless windows | modi sintetici clock/spatial; VCD RTL non è pin-accurate |
| 4 Current engine | I_cell(t) per arco | triangolo per ITerm |
| 5 Solver | AMG + Krylov/MOR + BE gold | **BE + sparse LU** (GCD ~4k nodi) |
| 6 Analysis | map, Vmin, EM, timing | JSON + CSV + SVG heatmap |

vyges resta il **check simultaneous-switch** (binario Apache-2.0). Questo engine è il path I(t)+waveform. ngspice non è il motore full-chip.

## Cosa non fare (questa slice e oltre, nel repo)

- Non forkare vyges-em-ir, EMSim o PSM per farci AMG/CCS/GPU.
- Non spacciare BE+PCG (o questo LU) come cuore di un prodotto SoC.
- Non mettere ML (MAVIREC/PowerNet) *dentro* il solver: solo screening, se un giorno serve.
- Non fingere correlazione commerciale.

Riferimenti concettuali (non dipendenze): ESPSim (SA-AMG), MATEX/Raptor (rational Krylov / MOR), Ginkgo (backend sparso), Xyce (gold parallelo).

Come lanciare lo slice: [dynamic-ir.md](./dynamic-ir.md).
