# DPN engine (native)

Sparse PDN solvers for the Dynamic Power Integrity stack.

Python (`learn/scripts/pdn_dynamic.py`) owns OpenROAD frontend, I(t), reporting.
This library owns the numerically hot path:

| Backend | Role |
|---|---|
| `direct` | Backward-Euler operator \(A=G+C/\Delta t\), Eigen SparseLU (gold) |
| `amg` | Smoothed-aggregation AMG + CG (workhorse) |
| `timestep_be` | Triangle \(I(t)\) + RHS + solve loop (fixed \(\Delta t\)) |
| `timestep_be_hist` | Same operator; package R+L companion with inductor current \(i_L\) |
| `timestep_be_adaptive` | Same physics; \(\Delta t\) from voltage LTE \(\tfrac12\|\Delta^2 V\|\); \(g_\mathrm{eq}(\Delta t)\) and \(i_L\) |
| `rational_krylov` | Reduced ODE \(C_r \dot z + G_r z = -V^\top I(t)\) on \(\delta v=v-V_\mathrm{dd}\) |

## Assumptions

- \(A\) and \(G\) are real, sparse, treated as SPD / M-matrix (RC PDN + implicit BE).
- Indices are `int32` (nnz and n up to \(2^{31}-1\)). Switch the `Index` alias to `int64_t` before 2e9 nonzeros.
- AMG uses Vaněk–Mandel–Brezina smoothed aggregation, damped Jacobi, Eigen SparseLU on the coarsest level. Not Ginkgo, not a GPU backend yet.
- Package inductance is a **BE series-R+L companion** at the bumps: \(g_\mathrm{eq}=1/(R+L/\Delta t)\), \(i^{n+1}=g_\mathrm{eq}(V_\mathrm{src}-v^{n+1})+g_\mathrm{eq}(L/\Delta t)\,i^n\). The operator \(A\) stays SPD (AMG applies). Adaptive steps recompute \(g_\mathrm{eq}\) at the current \(\Delta t\) and carry \(i_L\). This is lumped package R+L, not extracted on-die \(L\).
- MOR is Galerkin on a rational Krylov basis of \(G_\mathrm{soft}\) (pad \(g_\mathrm{eq}\) at the analysis \(\Delta t\)) with **no** \(i_L\). When \(L>0\), C is an RC-equivalent **screening** model. Solver A with history is the physical truth. Do not rank extra \(I(t)\) scenarios with MOR on this mesh.
- Adaptive \(\Delta t\) recomputes \(g_\mathrm{eq}(\Delta t)\). That is a **different** discretization of \(L\) than the fixed-\(\Delta t\) gold (coarse BE damps \(L\)). Gold is the stated analysis \(\Delta t\). Opt in with `--adaptive` / `DYNAMIC_IR_ADAPTIVE=1`.
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
- 1-node series R+L companion with \(i_L\) history vs hand BE (and vs memoryless \(L/\Delta t\))
