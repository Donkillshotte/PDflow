# System PDN & packaging analysis — tool landscape

Vedi anche la **catena completa fasi**: [spice-power-chain.md](./spice-power-chain.md).

## Due analisi distinte

| Livello | Domanda | Cosa usa Studio |
|---|---|---|
| **Chip PDN** | Griglia on-die regge IR statico / droop mesh? | OpenROAD **PDNSim** + `write_pg_spice` + `pdn_transient.py` + **vyges-em-ir** |
| **System PDN** | Catena VRM → board → package → die: Z(f) e load-step? | **ngspice** ladder gerarchico → `run_system_pdn.sh` / FlowLab **PKG** |

Non sono la stessa cosa: package R su PDNSim è ancora un modello *chip-centric*.
System PDN simula la catena di alimentazione fuori dal die.

## System PDN (fase PKG)

`run_system_pdn.sh` / azione `system_pdn`:

1. Legge `learn/system_pdn/default.json` (VRM, board plane/decap, package RLC/bumps, C_die)
2. Stima `I_die` da `activity_power` / report, oppure `I_DIE_AVG=`
3. **ngspice TRAN** — load-step al die → droop su VRM / board / pkg / die
4. **ngspice AC** — \|Z(f)\| visto al die (Iac=1A)

Report: `learn/sim/reports/system_pdn_<variant>.json`  
Work: `results/.../system_pdn/` (netlist + wrdata)

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_system_pdn.sh
# oppure
I_DIE_AVG=0.002 FLOW_VARIANT=flowlab ./learn/scripts/run_system_pdn.sh
```

## Chip PDN IR (opzionale)

```bash
FLOW_VARIANT=flowlab PKG_R=0.05 PKG_L=2e-10 PEAK_FACTOR=8 \
  ./learn/scripts/run_chip_pdn_ir.sh
```

Report: `learn/sim/reports/pdn_chip_ir_<variant>.json`  
(e copia legacy `pdn_transient_<variant>.json`)

Validazione GCD flowlab: static IR engine ≈ **4.56 mV** vs OpenROAD ≈ **4.47 mV**.

## Tool open / academic rilevanti

1. **OpenROAD PDNSim** — static IR on-die, `write_pg_spice`
2. **ngspice** — System PDN AC/TRAN sul ladder (quello usato in PKG)
3. **vyges-em-ir** — engine Apache-2.0 (binario) sulla stessa mesh: azione `vyges_em_ir`. `pdn_transient.py` resta il solver di laboratorio con waveform. Dettagli: [vyges-em-ir.md](./vyges-em-ir.md)
4. Board SI/PI full-wave — tipicamente tool commerciali (ADS, SIwave, …)

## Limiti onesti

- System PDN = modello *lumped* educativo (non S-parameter board reale)
- Chip PDN transient = worst-case simultaneous switching, non VCD-accurate
- Nessun LEF bump/RDL reale su nangate45 GCD
- Non sostituisce Voltus / RedHawk per tapeout
