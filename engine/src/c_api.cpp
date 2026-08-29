#include "dpn/c_api.h"

#include "dpn/csr.hpp"
#include "dpn/solvers.hpp"

#include <memory>
#include <new>

struct DpnHandle {
  dpn::Csr A;
  std::unique_ptr<dpn::Solver> solver;
};

extern "C" {

DpnHandle* dpn_setup(int kind, int n, int nnz, const int* rowptr, const int* col,
                     const double* val) {
  if (!rowptr || !col || !val || n <= 0 || nnz < 0 || rowptr[n] != nnz) {
    return nullptr;
  }
  try {
    auto* h = new DpnHandle();
    h->A = dpn::from_csr(n, rowptr, col, val);
    if (kind == 1) {
      h->solver = dpn::make_amg(h->A);
    } else {
      h->solver = dpn::make_direct(h->A);
    }
    return h;
  } catch (...) {
    return nullptr;
  }
}

int dpn_solve(DpnHandle* h, const double* b, double* x, const double* x0, double* relres) {
  if (!h || !h->solver || !b || !x) {
    return -1;
  }
  h->solver->solve(b, x, x0);
  if (relres) {
    *relres = h->solver->last_relres();
  }
  return 0;
}

int dpn_n(DpnHandle* h) { return h && h->solver ? static_cast<int>(h->solver->n()) : 0; }

int dpn_n_levels(DpnHandle* h) { return h && h->solver ? h->solver->n_levels() : 0; }

double dpn_setup_s(DpnHandle* h) { return h && h->solver ? h->solver->setup_s() : 0.0; }

const char* dpn_name(DpnHandle* h) { return h && h->solver ? h->solver->name() : ""; }

void dpn_free(DpnHandle* h) { delete h; }

}  // extern "C"
