# ngspice · come leggere le simulazioni System PDN

Studio usa **ngspice-42** in batch per la fase PKG. Questa guida spiega netlist, comandi e come interpretare i report.

## Installazione (già in VM)

```bash
ngspice -v
# ngspice-42
```

Documentazione upstream: [ngspice.sourceforge.io](http://ngspice.sourceforge.io/docs.html)

---

## Netlist System PDN (ladder)

File demo: `learn/sim/spice/system_pdn_tran_demo.sp`

Struttura tipica:

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

| Elemento | Significato fisico |
|---|---|
| `V_*` | Regolatore ideale (1.1 V) |
| `R_*`, `L_*` | ESR/ESL package, plane, VRM |
| `C_*` | Bulk/HF decap, Cout VRM, C_die |
| `I_DIE PULSE(...)` | Load-step al die (idle → peak) |

---

## Due run separati (TRAN + AC)

`system_pdn_hier.py` genera **due netlist** (ngspice non gestisce bene alter mid-simulation):

1. **TRAN** — load-step → droop temporale su VRM/board/pkg/die
2. **AC** — `I_AC n_die 0 AC 1` → \|Z(f)\| = \|V(n_die)\| con 1 A AC

Comando batch:

```bash
ngspice -b -o log.txt system_pdn_tran_demo.sp
```

---

## Interpretare il JSON report

`learn/sim/reports/system_pdn_flowlab.json`:

| Campo | Significato |
|---|---|
| `transient.droop_mv` | Vdd − min(V_die) al load-step |
| `impedance.z_max_mohm` | Picco \|Z(f)\| al die |
| `impedance.f_at_zmax_hz` | Frequenza della risonanza ladder |
| `i_die_avg_a` | Corrente media usata (da activity_power) |

Su GCD flowlab tipico: droop ~6 mV, Zmax ~9 Ω @ ~224 MHz (risonanza L-C package/board — **modello lumped**, non misura reale).

Target educativo in config: `z_target_mohm: 50`.

---

## Celle vs ladder — due mondi SPICE

| | Chip mesh (`write_pg_spice`) | System ladder (ngspice) |
|---|---|---|
| Nodi | Migliaia (M1 grid + ITerm) | ~15 lumped |
| R | Da layout straps/vias | Parametri JSON |
| Sorgenti | I per cella/instance | PULSE al die |
| Engine | Python sparse / PDNSim | ngspice |
| Domanda | IR on-die | VRM→board→pkg |

Le **celle standard** non sono simulate transistor-per-transistor: OpenROAD inietta **correnti DC equivalenti** sui pin ITerm. Per un inverter SPICE didattico vedi `nangate_inverter_demo.sp`.

---

## Esercizi

1. Modifica `learn/system_pdn/default.json` → raddoppia `c_bulk` → rilancia PKG → confronta Zmax e droop
2. Apri `tran.sp` in `results/.../system_pdn/` e identifica ogni blocco VRM/board/pkg
3. Esegui manualmente: `ngspice -b learn/sim/spice/system_pdn_tran_demo.sp`

---

## Collegamento fasi

Vedi [spice-power-chain.md](./spice-power-chain.md) per il flusso RTL→PKG completo.
