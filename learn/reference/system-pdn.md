# System PDN & packaging analysis — tool landscape

## Cosa serve per analisi «vere»

| Livello | Domanda | Open-source maturo? |
|---|---|---|
| Chip PDN static IR | Griglia on-die regge la corrente media? | **Sì** — OpenROAD **PDNSim** (`analyze_power_grid`) |
| Package / bump model | Come entrano le alimentazioni (C4, strap)? | **Parziale** — `set_pdnsim_source_settings` + `source_type BUMPS\|STRAPS\|FULL` + `external_resistance` |
| Transient / dynamic IR | Droop al switching (IR + Ldi/dt)? | **Parziale** — PDNSim è **static-only**; servono engine esterni |
| Board SI/PI | Plane, VRM, S-parameter | Quasi solo tool commerciali (ADS, SIwave, …) |

## Tool open / academic rilevanti

1. **OpenROAD PDNSim** (integrato) — static IR, EM density base, `write_pg_spice`
2. **VoltSpot** (UVa) — transient PDN pre-RTL (IR + Ldi/dt + LC), SuperLU
3. **vyges-em-ir** — static + backward-Euler dynamic IR su rete resistiva / DEF
4. **Raptor / EMSpice** (research) — transient Krylov / multiphysics EM+IR (più pesanti da installare)
5. **ngspice** — può simulare netlist SPICE esportate (lente su mesh grandi)

## Cosa fa Studio adesso

`run_system_pdn.sh` / azione FlowLab **PKG** (`system_pdn`):

1. **Statico OpenROAD** con bump pitch, `external_resistance` (package R),
   STRAPS / FULL / BUMPS + mappa tensioni
2. **`write_pg_spice -source_type BUMPS`** → mesh reale del chip
3. **`pdn_transient.py`** — solve sparse diretto (SciPy) statico + **backward-Euler
   transient** con package R/L e decap, peak switching (upper bound)

Validazione sul GCD flowlab: static IR engine ≈ **4.56 mV** vs OpenROAD
≈ **4.47 mV** (accordo ~2%). Transient droop tipicamente **più alto** del static
(peak×N simultaneous switch) — comportamento atteso.

## Limiti onesti

- Nessun LEF bump/RDL reale su nangate45 GCD
- Transient = worst-case simultaneous switching, non VCD-accurate
- Board planes / VRM restano fuori scope
- Non sostituisce Voltus / RedHawk per tapeout

## Come rilanciare

```bash
FLOW_VARIANT=flowlab PKG_R=0.05 PKG_L=2e-10 PEAK_FACTOR=8 \
  ./learn/scripts/run_system_pdn.sh
```

Report: `learn/sim/reports/pdn_transient_<variant>.json`  
Wave: `learn/sim/reports/pdn_transient_<variant>.wave.csv`  
Spice: `results/.../pdn/pg_vdd_bumps.sp`
