# DPN engine (native)

Sparse PDN solvers for the Dynamic Power Integrity stack.

Python (`learn/scripts/pdn_dynamic.py`) owns OpenROAD frontend, I(t), reporting.
This library owns the numerically hot path:

| Backend | Role |
|---|---|
| `direct` | Backward-Euler operator \(A=G+C/\Delta t\), Eigen SparseLU (gold) |
| `amg` | Smoothed-aggregation AMG + CG (workhorse) |
| `timestep_be` | Triangle \(I(t)\) + RHS + solve loop (fixed \(\Delta t\)) |
| `timestep_be_adaptive` | Same physics; \(\Delta t\) from voltage LTE \(\tfrac12\|\Delta^2 V\|\) |
| `rational_krylov` | Reduced ODE \(C_r \dot z + G_r z = -V^\top I(t)\) on \(\delta v=v-V_\mathrm{dd}\) |

## Assumptions

- \(A\) and \(G\) are real, sparse, treated as SPD / M-matrix (RC PDN + implicit BE).
- Indices are `int32` (nnz and n up to \(2^{31}-1\)). Switch the `Index` alias to `int64_t` before 2e9 nonzeros.
- AMG uses Vaněk–Mandel–Brezina smoothed aggregation, damped Jacobi, Eigen SparseLU on the coarsest level. Not Ginkgo, not a GPU backend yet.
- Package inductance enters the BE companion as \(g_\mathrm{pad}=1/(R+L/\Delta t)\). Adaptive steps freeze that term at the analysis \(\Delta t\) (no inductor history current). MOR also freezes \(G\) at that \(\Delta t\). Extra MNA inductor states are a later slice.
- MOR is Galerkin on a rational Krylov basis. It is **not** the source of physical truth — Solver A is. Use C for repeated \(I(t)\) on the same PDN when \(\|A-C\|\) is inside the report tolerance.
- Deviation form assumes \(G V_\mathrm{dd} = \mathrm{pad}\) (floating mesh + pad conductances). That holds for the OpenROAD `write_pg_spice` + package pad model.

## Build

```bash
./learn/scripts/build_dpn_engine.sh
```

Requires **g++-13** (Clang as `/usr/bin/c++` fails `-lstdc++` here). Produces `engine/build/libdpn.so` and runs `dpn_test`.

## Tests

`dpn_test` checks:

- 1D/2D Poisson AMG vs SparseLU
- 1-node BE vs closed-form implicit Euler (C API and native timestep)
- Adaptive 1-node vs fine BE
- 1-node MOR vs full BE (exact in 1-D)
- 20-node RC line MOR vs LU BE
