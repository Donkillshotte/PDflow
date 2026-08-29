# SPICE chip mesh · write_pg_spice e analisi celle

OpenROAD esporta la power grid on-die come **rete resistiva** con sorgenti di corrente per ogni pin di alimentazione cella. Questo documento spiega la netlist e come collegarla alle fasi Place/Finish.

## Da dove nasce la netlist

Dopo **finish**, con ODB e liberty:

```tcl
set_power_activity -global -activity 0.2 -duty 0.5
report_power
set_pdnsim_source_settings -bump_dx 140 -bump_dy 140 \
  -external_resistance 0.05
analyze_power_grid -net VDD -source_type BUMPS
write_pg_spice -net VDD -source_type BUMPS pdn/pg_vdd_bumps.sp
```

Script Studio: `learn/scripts/run_chip_pdn_ir.sh`

Output tipico (flowlab): **~6700 resistori**, file ~430 KB.

---

## Anatomia di pg_vdd_bumps.sp

```spice
* Netlist for VDD on default

* Resistive network
R0 Node_metal1_2400_5600 ITermNode_metal1_2470_5345 R=1.000000e-03
R42 Node_metal1_2540_5600 Node_metal1_8740_5600 R=6.929448e+00
...

* Current sources (per cell instance pin)
I0 ITermNode_metal1_2470_5345 0 DC 1.234567e-05
...

* Voltage sources (bumps / straps)
V0 Node_bump_0 0 DC 1.100000e+00
```

| Prefisso nodo | Origine |
|---|---|
| `Node_metal*` | Griglia strap/via (coordinate DBU) |
| `ITermNode_*` | Pin VDD di un'**istanza cella** piazzata |
| `Node_bump_*` | Sorgente package (pattern BUMPS) |

**Resistenza R:** estratta da shape metal reale (width, length, sheet R).

**Corrente I:** da `report_power` ripartita sui pin (activity × capacità/leakage/switching liberty).

---

## Collegamento placement → correnti

1. **Synth** istanzia celle (`DFF_X1`, `NAND2_X1`, …)
2. **Place** fissa coordinate → ogni ITerm ha posizione `(x,y)` nel nome nodo
3. **Finish** `report_power` → mA totali per tipo cella
4. PDNSim → corrente DC per ITerm proporzionale al power

Non vedi il nome cella nel nodo SPICE, ma la mappa `ir_bumps.csv` + DEF collegano posizione → istanza.

---

## Engine transient Studio

`pdn_transient.py`:

1. Parse R, I, V da `.sp`
2. Matrice sparsa G·V = I (static)
3. Backward-Euler: C_decap · dV/dt + G·V = I(t) con load-step

Validazione GCD: static ≈ OpenROAD ±2%.

Report: `pdn_chip_ir_<variant>.json`

Engine reale **vyges-em-ir** (stesso `.sp`): [vyges-em-ir.md](./vyges-em-ir.md). Static IR coincide (~0.4 %); il droop dinamico no (waveform diversa).

---

## Confronto con System PDN

| | Chip mesh | System ladder |
|---|---|---|
| File | `pg_vdd_bumps.sp` | `system_pdn/tran.sp` |
| Nodi | ~1000+ | ~12 |
| Package | `external_resistance` + bump pattern | RLC lumped esplicito |
| Board/VRM | Assente | VRM + plane + decap |

Il mesh risponde: *dove* sul die c'è droop. Il ladder risponde: *la catena di alimentazione esterna* regge il load-step.

---

## Lab: esplorare la netlist

```bash
FLOW_VARIANT=flowlab ./learn/scripts/export_spice_lab.sh
```

Crea in `learn/sim/spice/`:

- `pg_vdd_header.sp` — prime ~120 righe annotate
- symlink/copia mesh completa (se presente)
- `mesh_stats.json` — conteggio R/I/V

Conta resistori:

```bash
rg -c '^R' learn/sim/spice/pg_vdd_bumps.sp
rg -c '^I' learn/sim/spice/pg_vdd_bumps.sp
```

---

## Limiti

- Modello **resistivo statico** (no L di power grid on-die in export base)
- Correnti DC, non forme d'onda per-pin da VCD
- BUMPS sintetici su GCD (no LEF package reale)

Vedi [spice-power-chain.md](./spice-power-chain.md) per l'ordine delle fasi.
