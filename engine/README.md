# DPN engine (native)

Sparse PDN solvers for the Dynamic Power Integrity stack.

Python (`learn/scripts/pdn_dynamic.py`) owns OpenROAD frontend, I(t), reporting.
This library owns the numerically hot path:

| Backend | Role |
|---|---|
| `direct` | Backward-Euler operator \(A=G+C/\Delta t\), Eigen SparseLU (gold) |
| `amg` | Smoothed-aggregation AMG + CG (workhorse) |
| `ras` | Restricted additive Schwarz: graph-grown subdomains, overlapping local SparseLU, RAS restriction, GMRES (kind=2) |
| `timestep_be` | Triangle \(I(t)\) + RHS + solve loop (fixed \(\Delta t\)) |
| `timestep_be_hist` | Same operator; package R+L companion with inductor current \(i_L\) |
| `timestep_be_adaptive` | Same physics; \(\Delta t\) from voltage LTE \(\tfrac12\|\Delta^2 V\|\); \(g_\mathrm{eq}(\Delta t)\) and \(i_L\) |
| `rational_krylov` | RC: reduced ODE on \(\delta v=v-V_\mathrm{dd}\). RLC: descriptor \(E\dot x+Ax=u\) on \(x=[v;i_L]\) |

## Assumptions

- The companion operator \(A=G+C/\Delta t+g_\mathrm{eq}\) is real, sparse, SPD / M-matrix (RC PDN + implicit BE). AMG applies **only** to that operator.
- The RLC descriptor \(A\) is **unsymmetric**. Krylov expansions factor \((A+sE)\) with SparseLU, never AMG.
- Indices are `int32` (nnz and n up to \(2^{31}-1\)). Switch the `Index` alias to `int64_t` before 2e9 nonzeros.
- AMG uses Vaněk–Mandel–Brezina smoothed aggregation, damped Jacobi, Eigen SparseLU on the coarsest level. Not Ginkgo, not a GPU backend yet.
- RAS (Solver D) partitions the **sparsity graph**, not index stripes. Overlap is a 2-hop halo; the correction is restricted to the interior (classical RAS). The outer iteration is GMRES because the RAS operator is not SPD. `n<8` uses one LU of the full matrix (exact). This is domain decomposition on the BE companion, not a second physics model.
- Package inductance is a **BE series-R+L companion** at the bumps: \(g_\mathrm{eq}=1/(R+L/\Delta t)\), \(i^{n+1}=g_\mathrm{eq}(V_\mathrm{src}-v^{n+1})+g_\mathrm{eq}(L/\Delta t)\,i^n\). The companion stays SPD (AMG applies). Adaptive steps recompute \(g_\mathrm{eq}\) at the current \(\Delta t\) and carry \(i_L\). This is lumped package R+L, not extracted on-die \(L\).
- MOR RLC uses the same physics as Solver A: \(C\dot v + G v - i_L = -I_\mathrm{draw}\), \(L\dot i + R i + v = V_\mathrm{src}\). UIC \(v=V_\mathrm{dd}\), \(i_L=0\), projected with \(E_r z_0 = V^\top E x_0\). Do not rank extra \(I(t)\) scenarios with MOR; ranking is Solver A.
- Adaptive \(\Delta t\) recomputes \(g_\mathrm{eq}(\Delta t)\). That is a **different** discretization of \(L\) than the fixed-\(\Delta t\) gold (coarse BE damps \(L\)). Gold is the stated analysis \(\Delta t\). Opt in with `--adaptive` / `DYNAMIC_IR_ADAPTIVE=1`.
- RC deviation form assumes \(G V_\mathrm{dd} = \mathrm{pad}\) (floating mesh + pad conductances). That holds for the OpenROAD `write_pg_spice` + package pad model.

## Build

```bash
./learn/scripts/build_dpn_engine.sh
```

Requires **g++-13** (Clang as `/usr/bin/c++` fails `-lstdc++` here). Produces `engine/build/libdpn.so` and runs `dpn_test`.

## Tests

`dpn_test` checks:

- 1D/2D Poisson AMG vs SparseLU
- 1D/2D Poisson RAS vs SparseLU (and C API `kind=2`)
- 1-node BE vs closed-form implicit Euler (C API and native timestep)
- Adaptive 1-node vs fine BE
- 1-node MOR vs full BE (exact in 1-D)
- 20-node RC line MOR vs LU BE
- 1-node series R+L companion with \(i_L\) history vs hand BE (and vs memoryless \(L/\Delta t\))
- 1-node and 2-node **descriptor RLC MOR** vs hist BE (machine-precision on these meshes)
