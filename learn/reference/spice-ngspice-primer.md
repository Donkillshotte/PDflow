# ngspice · reading System PDN simulations

Studio uses **ngspice-42** in batch for the PKG phase. This guide explains netlists, commands, and how to read the reports.

## Installation (already in VM)

```bash
ngspice -v
# ngspice-42
```

Upstream documentation: [ngspice.sourceforge.io](http://ngspice.sourceforge.io/docs.html)

---

## System PDN netlist (ladder)

Demo files: `learn/sim/spice/system_pdn_tran_demo.sp`

Typical structure:

```spice
* VRM
V_VRM n_vrm_src 0 DC 1.1
R_VRM n_vrm_src n_vrm 0.015
L_VRM n_vrm n_vrm_l 2e-09
C_VRM n_vrm_l 0 4.7e-05

* ... board, package ...

* Die
C_DIE n_die 0 5e-10
I_DIE n_die 0 PULSE(Iidle Ipeak 20n 2n 2n 80n 1)

.control
tran 0.1n 200n
wrdata tran_out v(n_die)
quit
.endc
.end
```

| Element | Physical meaning |
|---|---|
| `V_*` | Ideal regulator (1.1 V) |
| `R_*`, `L_*` | Package ESR/ESL, plane, VRM |
| `C_*` | Bulk/HF decap, VRM Cout, C_die |
| `I_DIE PULSE(...)` | Load-step at the die (idle → peak) |

---

## Two separate runs (TRAN + AC)

`system_pdn_hier.py` generates **two netlists** (ngspice does not handle `alter` mid-simulation well):

1. **TRAN** — load-step → temporal droop on VRM/board/pkg/die
2. **AC** — `I_AC n_die 0 AC 1` → \|Z(f)\| = \|V(n_die)\| with 1 A AC

Batch command:

```bash
ngspice -b -o log.txt system_pdn_tran_demo.sp
```

---

## Reading the JSON report

`learn/sim/reports/system_pdn_flowlab.json`:

| Field | Meaning |
|---|---|
| `transient.droop_mv` | Vdd − min(V_die) at the load-step |
| `impedance.z_max_mohm` | Peak \|Z(f)\| at the die |
| `impedance.f_at_zmax_hz` | Ladder resonance frequency |
| `i_die_avg_a` | Average current used (from activity_power) |

Typical GCD flowlab: droop ~6 mV, Zmax ~9 Ω @ ~224 MHz (package/board L-C resonance — **lumped model**, not a real measurement).

Educational target in config: `z_target_mohm: 50`.

---

## Cells vs ladder — two SPICE worlds

| | Chip mesh (`write_pg_spice`) | System ladder (ngspice) |
|---|---|---|
| Nodes | Thousands (M1 grid + ITerm) | ~15 lumped |
| R | From layout straps/vias | JSON parameters |
| Sources | I per cell/instance | PULSE at die |
| Engine | Python sparse / PDNSim | ngspice |
| Question | On-die IR | VRM→board→pkg |

Standard **cells** are not simulated transistor-by-transistor: OpenROAD injects **equivalent DC currents** on ITerm pins. For an educational SPICE inverter see `nangate_inverter_demo.sp`.

---

## Exercises

1. Modify `learn/system_pdn/default.json` → double `c_bulk` → rerun PKG → compare Zmax and droop
2. Open `tran.sp` in `results/.../system_pdn/` and identify every VRM/board/pkg block
3. Run manually: `ngspice -b learn/sim/spice/system_pdn_tran_demo.sp`

---

## Phase links

See [spice-power-chain.md](./spice-power-chain.md) for the full RTL→PKG flow.
