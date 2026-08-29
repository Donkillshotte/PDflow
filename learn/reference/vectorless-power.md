# Vectorless e dynamic power/IR (GCD Nangate45)

OpenSTA/OpenROAD non hanno un “vectorless IR signoff” commerciale (PrimeTime PX vectorless, RedHawk-static). Qui il corso **implementa** i due pezzi che i paper definiscono, e li gira sul GCD routed.

## Letteratura (metodo, non codice copiato)

1. **F. Najm**, *A survey of power estimation techniques in VLSI circuits*, Proc. IEEE 1994.  
   Probabilità di transizione \(P_{01} = p(1-p)\) con \(p=0.5\) combinazionale e \(p=0.1\) sequenziale.
2. **D. Kouroussis & F. Najm**, *A static pattern-independent technique for power grid voltage integrity verification*, DAC 2003.  
   Correnti di istanza in \([0, I_{\max}]\), budget di chip (non tutte le porte commutano a \(I_{\max}\) insieme), stima IR **senza vettore**.

## Due modi nello stesso ODB

| Modo | Attività | Script / TCL |
|---|---|---|
| **Vectorless** | `set_power_activity -global -activity 0.5` | `POWER_MODE=vectorless` |
| **Dynamic** | `read_vcd -scope tb_gcd/dut learn/sim/gcd/gcd.vcd` | `POWER_MODE=dynamic` (default `auto` se il VCD c’è) |

OpenSTA 26Q2: `read_power_activities` è deprecato e chiama `read_vcd` con l’arità sbagliata. Il helper è `learn/lib/power_vcd.sh`.

Il VCD Icarus annota i **nomi che matchano** il netlist gate (in pratica i port). I pin non annotati restano sui default OpenSTA. **Non** si fa `set_power_activity -global` dopo il VCD: sovrascriverebbe l’annotazione.

Attenzione **STA-1452**: il testbench usa periodo 10 ns, l’SDC 0.46 ns. I watt dynamic non sono 1:1 col vectorless — è un dato didattico, non un signoff foundry.

## Envelope IR

`learn/scripts/vectorless_analysis.py`:

- \(I_\mathrm{avg} = P_\mathrm{vectorless} / V_{DD}\)
- budget chip \(I_\mathrm{avg} \times 3\) (crest)
- pesi area \(\times P_{01}\) \(\times\) distanza (proxy strap)
- cap locale \(8\times\) share di area
- fill/tap **esclusi** (non commutano)
- se esiste `pg_vdd_bumps.sp`, DC sul mesh (`pdn_transient.py`) con correnti riscalate al budget

PDNSim (`analyze_power_grid -source_type STRAPS`) gira in entrambi i modi: IR straps sul report.

## Come lanciare

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_rtl_sim.sh   # VCD
FLOW_VARIANT=flowlab ./learn/scripts/run_vectorless.sh
# report: learn/sim/reports/vectorless_flowlab.json
```

Studio / FlowLab: azione **`vectorless`**. Orchestrator: **`tool_matrix`**.

## Cosa non è

Non è RedHawk, VoltSpot commerciale, né PrimeTime PX. È un envelope statico + liberty `report_power` + mesh DC, tracciabile ai due paper, eseguibile sul GCD di questo repo.
