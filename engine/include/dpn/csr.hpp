#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

namespace dpn {

using Index = int32_t;

struct Csr {
  Index nrows = 0;
  Index ncols = 0;
  std::vector<Index> rowptr;  // nrows+1
  std::vector<Index> col;
  std::vector<double> val;

  Index nnz() const { return static_cast<Index>(val.size()); }

  void spmv(const double* x, double* y) const {
    for (Index i = 0; i < nrows; ++i) {
      double s = 0.0;
      for (Index k = rowptr[i]; k < rowptr[i + 1]; ++k) {
        s += val[k] * x[col[k]];
      }
      y[i] = s;
    }
  }

  void diag_inv(std::vector<double>& dinv) const {
    dinv.assign(nrows, 1.0);
    for (Index i = 0; i < nrows; ++i) {
      for (Index k = rowptr[i]; k < rowptr[i + 1]; ++k) {
        if (col[k] == i) {
          const double d = val[k];
          dinv[i] = (std::abs(d) < 1e-30) ? 1.0 : 1.0 / d;
          break;
        }
      }
    }
  }
};

Csr from_csr(Index n, const Index* rowptr, const Index* col, const double* val);
Csr transpose(const Csr& A);
Csr spmm(const Csr& A, const Csr& B);
void drop_small(Csr& A, double tol);

}  // namespace dpn
