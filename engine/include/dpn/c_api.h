#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct DpnHandle DpnHandle;

/* kind: 0 = direct SparseLU, 1 = SA-AMG + CG.
   rowptr has n+1 entries, col/val have nnz. Data is copied. */
DpnHandle* dpn_setup(int kind, int n, int nnz, const int* rowptr, const int* col,
                     const double* val);

/* Solve A x = b. x0 may be NULL. Returns 0 on success. relres may be NULL. */
int dpn_solve(DpnHandle* h, const double* b, double* x, const double* x0, double* relres);

int dpn_n(DpnHandle* h);
int dpn_n_levels(DpnHandle* h);
double dpn_setup_s(DpnHandle* h);
const char* dpn_name(DpnHandle* h);
void dpn_free(DpnHandle* h);

#ifdef __cplusplus
}
#endif
