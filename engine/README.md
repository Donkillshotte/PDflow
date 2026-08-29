# DPN engine (native)

Sparse PDN solvers for the Dynamic Power Integrity stack.

Python (`learn/scripts/pdn_dynamic.py`) owns OpenROAD frontend, I(t), reporting.
This library owns the numerically hot path:

| Backend | Role |
|---|---|
| `direct` | Backward-Euler operator \(A=G+C/\Delta t\), Eigen SparseLU (gold) |
| `amg` | Smoothed-aggregation AMG + CG (workhorse) |

## Assumptions

- \(A\) is real, sparse, and treated as SPD / M-matrix (RC PDN + implicit BE).
- Indices are `int32` (nnz and n up to \(2^{31}-1\)). Switch the `Index` alias to `int64_t` before 2e9 nonzeros.
- AMG uses Vaněk–Mandel–Brezina smoothed aggregation, damped Jacobi, Eigen SparseLU on the coarsest level. Not Ginkgo, not a GPU backend yet.
- One `setup` of \(A\) is reused for many right-hand sides (same PDN, many \(I(t)\)).

## Build

```bash
./learn/scripts/build_dpn_engine.sh
```

Produces `engine/build/libdpn.so` and runs `dpn_test`.

## Tests

`dpn_test` checks 1D/2D Poisson AMG vs SparseLU and a 1-node BE step vs the closed-form implicit Euler update.
