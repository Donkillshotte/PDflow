# vyges-em-ir sul GCD Nangate45

Engine reale: [`vyges-tools/em-ir`](https://github.com/vyges-tools/em-ir) v0.1.33, Apache-2.0.
Non è un clone Python: Studio scarica il binario (sha256-pinnato) in `tools/vyges-em-ir/` e lo lancia su un job `.emir`.

`pdn_transient.py` resta il solver di laboratorio (waveform CSV, `pkg_r`/`pkg_l` espliciti). **vyges-em-ir** è il check IR/EM dichiarativo sullo stesso mesh `write_pg_spice`.

## Come si aggancia

```text
6_final.odb
    │  OpenROAD PDNSim  analyze_power_grid -source_type BUMPS
    ▼
pg_vdd_bumps.sp          ← stessa netlist di chip_pdn_ir
    │  spice_to_pdn.py
    ▼
gcd_<variant>.pdn + .emir
    │  vyges-em-ir run --json
    ▼
sim/reports/vyges_em_ir_<variant>.json
```

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_vyges_em_ir.sh
# Studio: azione vyges_em_ir  ·  /strumenti?tab=run&action=vyges_em_ir
```

Il binario non è in git (`tools/` è ignorato). `ensure_vyges_em_ir.sh` prende il release `x86_64` / `aarch64` Linux, verifica lo sha256, e se il download fallisce prova `cargo build --release` dal tag `v0.1.33`.

## Cosa fa l’engine (fedeltà)

| Pezzo | Comportamento |
|---|---|
| Statico | CG + Jacobi su `G·V = I` |
| Dinamico | Backward Euler se il `.pdn` ha `cap` + `switch` |
| Switch | **Tutte** le celle nello stesso `switch_t_ns` — upper bound simultaneous-switch, non un VCD |
| Timestep | Implicito `min(dur)/10`, non configurabile |
| Waveform | **Non** esportata — solo worst droop |
| EM | Limiti per-layer nel `.pdn`; su Nangate45 **non** mettiamo `emlimit` (niente plugin foundry) |
| Pad | Nodi `V` di PDNSim BUMPS, tensioni ideali (= Vdd). Nessun `pkg_r` serie |

Non è un drop-in Ansys RedHawk. Upstream: correlato vs PDNSim su Sky130; sul GCD Nangate45 la correlazione statica è **la stessa mesh SPICE**, non DEF+LEF nativo (i bump PDNSim atterrano su metal4, non sul top metal).

## Numeri GCD flowlab (verificati)

Stesso `pg_vdd_bumps.sp` (~3985 nodi, 13 pad metal4, 601 load, I_tot ≈ 6.34 mA, Vdd = 1.1 V).

| Engine | Static IR | Dynamic droop |
|---|---|---|
| `pdn_transient.py` (spsolve) | **17.52 mV** (1.593 %) | 154.0 mV (14.0 %) — load-step ×8 + C/L package |
| **vyges-em-ir** 0.1.33 | **17.46 mV** (1.587 %) | 78.8 mV (7.17 %) @ 1.016 ns — triangoli simultaneous |

Rapporto statico vyges / pdn_transient ≈ **0.996**. Il droop dinamico **non** è confrontabile 1:1: waveform diversi (step+pkg vs triangolo, un solo `t50`). Il 7.17 % supera il default `ir_limit_pct: 5` — è l’upper bound didattico, non un FAIL di tapeout. Lo script **non** usa `--fail-on-violation`.

## File

| Path | Ruolo |
|---|---|
| `learn/scripts/ensure_vyges_em_ir.sh` | fetch binario v0.1.33 |
| `learn/scripts/spice_to_pdn.py` | SPICE → `.pdn` / `.emir` |
| `learn/scripts/run_vyges_em_ir.sh` | job GCD + JSON Studio |
| `results/.../pdn/vyges/` | `.pdn` `.emir` JSON engine |
| `sim/reports/vyges_em_ir_<variant>.json` | report aggregato + confronto |

Energia `switch` (pJ) dallo stesso inviluppo di `pdn_transient`:

`E = peak_factor · I_avg · Vdd · dur_ns · 500`  (triangolo, `Q = I_peak·dur/2`).

## Limiti da dire in aula

1. Simultaneous switch globale — stretto upper bound, non activity reale.
2. Nessuna waveform, nessun timestep utente.
3. Pad ideali: lo statico coincide con `pdn_transient` statico (sorgenti V fisse); il transitorio Studio include R/L di package.
4. DEF+LEF extraction esiste nell’engine (Sky130 `RPERSQ`); su questo corso il path onesto è la mesh PDNSim già usata dal GCD.
5. Nessuna correlazione commerciale; educativo, non sign-off foundry.

Cross-ref: [spice-chip-mesh.md](./spice-chip-mesh.md) · [vectorless-power.md](./vectorless-power.md) · [oss-integrations.md](./oss-integrations.md) · [system-pdn.md](./system-pdn.md) · [dynamic-ir.md](./dynamic-ir.md)
