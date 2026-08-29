# DPN engine (native)

Sparse PDN solvers for the Dynamic Power Integrity stack.

Python (`learn/scripts/pdn_dynamic.py`) owns OpenROAD frontend, I(t), reporting.
This library owns the numerically hot path:

| Backend | Role |
|---|---|
| `direct` | Backward-Euler operator \(A=G+C/\Delta t\), Eigen SparseLU (gold) |
| `amg` | Smoothed-aggregation AMG + CG (workhorse) |
| `ras` | Restricted additive Schwarz: undirected graph \(A\cup A^\top\), overlapping local SparseLU of the real operator \(A\), RAS restriction, GMRES (kind=2). Works on SPD companion **and** unsymmetric descriptor \(K\). |
| `bicgstab` | Eigen BiCGSTAB + ILUT (diag fallback), kind=3. Unsymmetric CPU Krylov workhorse — **not Ginkgo** |
| `timestep_be` | Triangle \(I(t)\) + RHS + solve loop (fixed \(\Delta t\)) |
| `timestep_be_hist` | Same operator; package R+L companion with inductor current \(i_L\) |
| `timestep_be_hist_cmat` | Sparse \(C\) (rail-to-rail \(C_{rr}\)) + mixed-rail UIC; tracks VDD min and VSS \(+V_\max\) |
| `timestep_be_adaptive` | Same physics; \(\Delta t\) from voltage LTE \(\tfrac12\|\Delta^2 V\|\); \(g_\mathrm{eq}(\Delta t)\) and \(i_L\) |
| `timestep_descriptor` | Fixed-\(\Delta t\) BE on \(E\dot x + A x = u\) (N4 VRM+die). Diagonal \(E\) wrapper |
| `timestep_descriptor_gen` | Same BE; sparse \(E\) (mutual L), \(n_\mathrm{iv}\) voltage sources, optional \(u_\mathrm{const}\). Unsymmetric \(A\) → SparseLU gold, never AMG |
| `timestep_descriptor_workhorse` | Same operator; `solver_kind` 0=SparseLU, 2=RAS+GMRES, 3=BiCGSTAB+ILUT. Rejects AMG |
| `timestep_descriptor_adaptive` | Same physics; \(\Delta t\) from voltage LTE \(\tfrac12\|\Delta^2 x\|\) on states \(0..n_v-1\). Not the fixed-\(\Delta t\) gold when \(L>0\) |
| `rational_krylov` | RC: reduced ODE on \(\delta v=v-V_\mathrm{dd}\). RLC: descriptor \(E\dot x+Ax=u\) on \(x=[v;i_L]\) |
| `dpn_mor_setup_gen` | Sparse-\(E\) rational Krylov (mutual L, \(n_\mathrm{iv}\), \(u_\mathrm{const}\)). Opt-in; GCD Solver C stays package-L companion MOR |

## Assumptions

- Companion \(A=G+C/\Delta t+g_\mathrm{eq}\) stays SPD when \(C\) includes instance-pin \(C_{rr}\) (SPSD capacitance matrix). AMG still applies. GCD default TRAN does **not** stamp \(C_{rr}\) (`--rail-c` / `RAIL_C=1`). Negative triangle \(I\) is return-rail KCL (current into VSS).
- The RLC descriptor \(A\) is **unsymmetric**. Krylov expansions factor \((A+sE)\) with SparseLU, never AMG.
- Mesh `n` and `nnz` use `int64_t` (`dpn::Index`, Eigen `SparseMatrix` StorageIndex). Call `dpn_index_width()` (returns 64) before `dpn_setup`. SciPy fallback CSR may still be int32 internally; the native path copies to int64. Event counts still reject `n_events > INT_MAX` (internal `timestep_*` take `int n_ev`).
- AMG uses Vaněk–Mandel–Brezina smoothed aggregation, damped Jacobi, Eigen SparseLU on the coarsest level. Not Ginkgo, not a GPU backend yet. kind=3 is Eigen BiCGSTAB+ILUT (diagonal fallback) for **unsymmetric** operators; it is not a Ginkgo shim.
- RAS (Solver D) partitions the **undirected sparsity graph** \(A\cup A^\top\), not index stripes. Unsymmetric descriptor \(K\) has one-way stamps; halo must follow both directions. Subdomain matrices are assembled from the **original** \(A\) (not \(A+A^\top\)). Overlap is a 2-hop halo; the correction is restricted to the interior (classical RAS). The outer iteration is GMRES because the RAS operator is not SPD. `n<8` uses one LU of the full matrix (exact). GCD Solver D stays on the SPD companion \(A=G+C/\Delta t+g_\mathrm{eq}\); kind=2 on descriptor \(K\) is opt-in, not the GCD default.
- Package inductance is a **BE series-R+L companion** at the bumps: \(g_\mathrm{eq}=1/(R+L/\Delta t)\), \(i^{n+1}=g_\mathrm{eq}(V_\mathrm{src}-v^{n+1})+g_\mathrm{eq}(L/\Delta t)\,i^n\). The companion stays SPD (AMG applies). Adaptive steps recompute \(g_\mathrm{eq}\) at the current \(\Delta t\) and carry \(i_L\). On-die strap L is Grover partial self **plus cutoff partial mutual** (same-layer parallel, overlapping projection, \(d\le 2\,\mu\mathrm{m}\), \(k\le 0.99\); no skin, no full PEEC) in Python `pdn_em` / `assemble_strap_rlc`. Sparse \(E\) and \(n_\mathrm{iv}\) pads go through `timestep_descriptor_gen`. That descriptor is unsymmetric and is **not** AMG. Default GCD TRAN does not stamp it (`--on-die-l` / `ON_DIE_L=1`).
- N4 descriptor BE stamps \(C\dot v + G v - i_L = -I_\mathrm{draw}\) and \(L\dot i + R i + v_\mathrm{bump} = V_\mathrm{src}\) (unsymmetric). UIC \(v=V_\mathrm{dd}\), \(i=0\). Not AMG. Multiple bump KVL rows each get \(+V_\mathrm{src}\).
- Extraction and EM live in Python (`pdn_extract`, `pdn_em`): tech LEF WIDTH/THICKNESS/RPERSQ; strap width from \(w=\mathrm{RPERSQ}\cdot L/R\), not min WIDTH. SPEF PG C is stamped only from a power `*D_NET` by name-join onto `write_pg_spice` nodes (GCD OpenRCX SPEF has no VDD).
- MOR RLC uses the same physics as Solver A: \(C\dot v + G v - i_L = -I_\mathrm{draw}\), \(L\dot i + R i + v = V_\mathrm{src}\). UIC \(v=V_\mathrm{dd}\), \(i_L=0\), projected with \(E_r z_0 = V^\top E x_0\). Do not rank extra \(I(t)\) scenarios with MOR; ranking is Solver A.
- Adaptive \(\Delta t\) recomputes \(g_\mathrm{eq}(\Delta t)\). That is a **different** discretization of \(L\) than the fixed-\(\Delta t\) gold (coarse BE damps \(L\)). Gold is the stated analysis \(\Delta t\). Opt in with `--adaptive` / `DYNAMIC_IR_ADAPTIVE=1`. Descriptor adaptive is the same caveat on \(E\dot x+Ax=u\) (LTE on voltage states only).
- Sparse-\(E\) rational Krylov (`make_mor_gen` / `dpn_mor_setup_gen`) is for **repeated on-die L+M scenarios**, not the GCD clock gold. GCD Solver C is package-L descriptor MOR on the N3 companion mesh. Do not rank extra \(I(t)\) with MOR.
- RC deviation form assumes \(G V_\mathrm{dd} = \mathrm{pad}\) (floating mesh + pad conductances). That holds for the OpenROAD `write_pg_spice` + package pad model.

## Build

```bash
./learn/scripts/build_dpn_engine.sh
```

Requires **g++-13** (Clang as `/usr/bin/c++` fails `-lstdc++` here). Produces `engine/build/libdpn.so` and runs `dpn_test`.

## Tests

`dpn_test` checks:

- `sizeof(Index)==8` and `dpn_index_width()==64`; nnz=0 CSR copy allows null col/val; nnz>0 rejects them
- 1D/2D Poisson AMG vs SparseLU
- 1D/2D Poisson RAS vs SparseLU (and C API `kind=2`)
- 1-node BE vs closed-form implicit Euler (C API and native timestep)
- Adaptive 1-node vs fine BE
- 1-node MOR vs full BE (exact in 1-D)
- 20-node RC line MOR vs LU BE
- 1-node series R+L companion with \(i_L\) history vs hand BE (and vs memoryless \(L/\Delta t\))
- 1-node and 2-node **descriptor RLC MOR** vs hist BE (machine-precision on these meshes)
- Compact 4-state VRM+die **descriptor BE** vs dense 4×4 gold (C API too)
- Sparse-E `plus`/`scale`/`diag_csr`; gen API vs diagonal wrapper; off-diagonal C and coupled L vs dense BE
- Poisson and unsymmetric VRM \(K\) **BiCGSTAB** vs SparseLU (C API `kind=3`)
- Compact VRM: descriptor BiCGSTAB vs LU; adaptive vs fixed \(\Delta t\) (1 mV-class); **sparse-E gen MOR** vs descriptor BE (C API too)
- Coupled-L gen MOR vs sparse-\(E\) BE (1 mV-class; not GCD Solver C)
- 32-node RC line + bump R+L **descriptor RAS** vs SparseLU (ndom≥2, C API kind=2); workhorse still rejects AMG (kind=1)
- 2-node rail-to-rail \(C_{rr}\): \(C_{rr}=0\) matches 1-node BE; \(C_{rr}>0\) reduces VDD droop; C API `hist_cmat`; signed triangle \(I\)
