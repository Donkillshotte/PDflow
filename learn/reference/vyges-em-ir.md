# vyges-em-ir on the GCD Nangate45

Real engine: [`vyges-tools/em-ir`](https://github.com/vyges-tools/em-ir) v0.1.33, Apache-2.0.
This is not a Python clone: Studio downloads the binary (sha256-pinned) in `tools/vyges-em-ir/` and runs it on a job `.emir`.

`pdn_transient.py` remains the lab solver (waveform CSV, explicit `pkg_r`/`pkg_l`). **vyges-em-ir** is the declarative IR/EM check on the same mesh `write_pg_spice` — bootstrap and validation, **not** the core Dynamic IR (that is Solver A in `pdn_dynamic.py`).

## How it hooks in

```text
6_final.odb
    │  OpenROAD PDNSim  analyze_power_grid -source_type BUMPS
    ▼
pg_vdd_bumps.sp          ← same netlist as chip_pdn_ir
    │  spice_to_pdn.py
    ▼
gcd_<variant>.pdn + .emir
    │  vyges-em-ir run --json
    ▼
sim/reports/vyges_em_ir_<variant>.json
```

```bash
FLOW_VARIANT=flowlab ./learn/scripts/run_vyges_em_ir.sh
# Studio: vyges_em_ir action  ·  /tools?tab=run&action=vyges_em_ir
```

Binary is not in git (`tools/` is ignored). `ensure_vyges_em_ir.sh` fetches the release `x86_64` / `aarch64` Linux, verifies sha256, and if download fails tries `cargo build --release` from tag `v0.1.33`.

## What the engine does (fidelity)

| Piece | Behavior |
|---|---|
| Static | CG + Jacobi on `G·V = I` |
| Dynamic | Backward Euler if `.pdn` has `cap` + `switch` |
| Switch | **All** cells at the same `switch_t_ns` — upper bound simultaneousus-switch, not a VCD |
| Timestep | Implicit `min(dur)/10`, not configurable |
| Waveform | **Not** exported — worst droop only |
| EM | Per-layer limits in `.pdn`; on Nangate45 we **do not** set `emlimit` (no foundry plugin) |
| Pad | PDNSim BUMPS `V` nodes, ideal voltages (= Vdd). No series `pkg_r` |

This is not a drop-in Ansys RedHawk. Upstream: correlated vs PDNSim on Sky130; on GCD Nangate45 static correlation is **the same SPICE mesh**, not native DEF+LEF (PDNSim bumps land on metal4, not on top metal).

## GCD flowlab numbers (verified)

Same `pg_vdd_bumps.sp` (~3985 nodes, 13 pad metal4, 601 load, I_tot ≈ 6.34 mA, Vdd = 1.1 V).

| Engine | Static IR | Dynamic droop |
|---|---|---|
| `pdn_transient.py` (spsolve) | **17.52 mV** (1.593 %) | 154.0 mV (14.0 %) — load-step ×8 + C/L package |
| **vyges-em-ir** 0.1.33 | **17.46 mV** (1.587 %) | 78.8 mV (7.17 %) @ 1.016 ns — simultaneous triangles |

Static ratio vyges / pdn_transient ≈ **0.996**. Dynamic droop is **not** comparable 1:1: different waveforms (step+pkg vs triangle, single `t50`). The 7.17% exceeds default `ir_limit_pct: 5` — is the educational upper bound, not a tapeout FAIL. The script **does not** use `--fail-on-violation`.

## Files

| Path | Role |
|---|---|
| `learn/scripts/ensure_vyges_em_ir.sh` | fetch binary v0.1.33 |
| `learn/scripts/spice_to_pdn.py` | SPICE → `.pdn` / `.emir` |
| `learn/scripts/run_vyges_em_ir.sh` | GCD job + Studio JSON |
| `results/.../pdn/vyges/` | `.pdn` `.emir` JSON engine |
| `sim/reports/vyges_em_ir_<variant>.json` | aggregated report + comparison |

Switch energy (pJ) from the same envelope as `pdn_transient`:

`E = peak_factor · I_avg · Vdd · dur_ns · 500`  (triangle, `Q = I_peak·dur/2`).

## Classroom limits

1. Global simultaneousus switch — tight upper bound, not real activity.
2. No waveform, no user timestep.
3. Ideal pads: static matches `pdn_transient` static (fixed V sources); Studio transient includes package R/L.
4. DEF+LEF extraction exists in the engine (Sky130 `RPERSQ`); on this course the honest path is the mesh PDNSim already used by GCD.
5. No commercial correlation; educational, not foundry sign-off.

Cross-ref: [spice-chip-mesh.md](./spice-chip-mesh.md) · [vectorless-power.md](./vectorless-power.md) · [oss-integrations.md](./oss-integrations.md) · [system-pdn.md](./system-pdn.md) · [dynamic-ir.md](./dynamic-ir.md)
