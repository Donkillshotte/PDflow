#include "dpn/csr.hpp"

#include <algorithm>
#include <vector>

namespace dpn {

Csr from_csr(Index n, const Index* rowptr, const Index* col, const double* val) {
  Csr A;
  A.nrows = n;
  A.ncols = n;
  A.rowptr.assign(rowptr, rowptr + n + 1);
  const Index nnz = rowptr[n];
  if (nnz > 0 && col && val) {
    A.col.assign(col, col + nnz);
    A.val.assign(val, val + nnz);
  }
  return A;
}

Csr from_triplets(Index n, const Index* ti, const Index* tj, const double* tv, Index ntrips) {
  struct T {
    Index i, j;
    double v;
  };
  std::vector<T> a(static_cast<size_t>(std::max(ntrips, Index{0})));
  for (Index k = 0; k < ntrips; ++k) {
    a[static_cast<size_t>(k)] = {ti[k], tj[k], tv[k]};
  }
  std::sort(a.begin(), a.end(), [](const T& x, const T& y) {
    if (x.i != y.i) {
      return x.i < y.i;
    }
    return x.j < y.j;
  });
  std::vector<T> b;
  b.reserve(a.size());
  for (const T& t : a) {
    if (t.i < 0 || t.j < 0 || t.i >= n || t.j >= n) {
      continue;
    }
    if (!b.empty() && b.back().i == t.i && b.back().j == t.j) {
      b.back().v += t.v;
    } else {
      b.push_back(t);
    }
  }
  Csr A;
  A.nrows = n;
  A.ncols = n;
  A.rowptr.assign(static_cast<size_t>(n + 1), 0);
  for (const T& t : b) {
    A.rowptr[t.i + 1]++;
  }
  for (Index i = 0; i < n; ++i) {
    A.rowptr[i + 1] += A.rowptr[i];
  }
  A.col.resize(b.size());
  A.val.resize(b.size());
  std::vector<Index> next = A.rowptr;
  for (const T& t : b) {
    const Index p = next[t.i]++;
    A.col[p] = t.j;
    A.val[p] = t.v;
  }
  return A;
}

Csr transpose(const Csr& A) {
  Csr T;
  T.nrows = A.ncols;
  T.ncols = A.nrows;
  T.rowptr.assign(T.nrows + 1, 0);
  for (Index k = 0; k < A.nnz(); ++k) {
    T.rowptr[A.col[k] + 1]++;
  }
  for (Index i = 0; i < T.nrows; ++i) {
    T.rowptr[i + 1] += T.rowptr[i];
  }
  T.col.resize(static_cast<size_t>(A.nnz()));
  T.val.resize(static_cast<size_t>(A.nnz()));
  std::vector<Index> next = T.rowptr;
  for (Index i = 0; i < A.nrows; ++i) {
    for (Index k = A.rowptr[i]; k < A.rowptr[i + 1]; ++k) {
      const Index j = A.col[k];
      const Index p = next[j]++;
      T.col[p] = i;
      T.val[p] = A.val[k];
    }
  }
  return T;
}

Csr spmm(const Csr& A, const Csr& B) {
  Csr C;
  C.nrows = A.nrows;
  C.ncols = B.ncols;
  C.rowptr.assign(C.nrows + 1, 0);
  std::vector<Index> marker(static_cast<size_t>(C.ncols), -1);
  std::vector<double> acc(static_cast<size_t>(C.ncols), 0.0);
  std::vector<Index> cols;
  std::vector<double> vals;
  cols.reserve(static_cast<size_t>(A.nnz()));
  vals.reserve(static_cast<size_t>(A.nnz()));

  for (Index i = 0; i < A.nrows; ++i) {
    std::vector<Index> row_idx;
    row_idx.reserve(16);
    for (Index ka = A.rowptr[i]; ka < A.rowptr[i + 1]; ++ka) {
      const Index j = A.col[ka];
      const double aij = A.val[ka];
      for (Index kb = B.rowptr[j]; kb < B.rowptr[j + 1]; ++kb) {
        const Index k = B.col[kb];
        if (marker[k] != i) {
          marker[k] = i;
          row_idx.push_back(k);
          acc[k] = aij * B.val[kb];
        } else {
          acc[k] += aij * B.val[kb];
        }
      }
    }
    std::sort(row_idx.begin(), row_idx.end());
    C.rowptr[i + 1] = C.rowptr[i] + static_cast<Index>(row_idx.size());
    for (Index k : row_idx) {
      cols.push_back(k);
      vals.push_back(acc[k]);
    }
  }
  C.col = std::move(cols);
  C.val = std::move(vals);
  return C;
}

Csr plus_diag(const Csr& A, const double* d) {
  Csr B;
  B.nrows = A.nrows;
  B.ncols = A.ncols;
  B.rowptr.resize(static_cast<size_t>(A.nrows + 1));
  B.rowptr[0] = 0;
  std::vector<Index> col;
  std::vector<double> val;
  col.reserve(static_cast<size_t>(A.val.size() + static_cast<size_t>(A.nrows)));
  val.reserve(static_cast<size_t>(A.val.size() + static_cast<size_t>(A.nrows)));
  for (Index i = 0; i < A.nrows; ++i) {
    bool has_diag = false;
    for (Index k = A.rowptr[i]; k < A.rowptr[i + 1]; ++k) {
      col.push_back(A.col[k]);
      if (A.col[k] == i) {
        val.push_back(A.val[k] + d[i]);
        has_diag = true;
      } else {
        val.push_back(A.val[k]);
      }
    }
    if (!has_diag) {
      col.push_back(i);
      val.push_back(d[i]);
    }
    B.rowptr[i + 1] = static_cast<Index>(col.size());
  }
  B.col = std::move(col);
  B.val = std::move(val);
  return B;
}

void drop_small(Csr& A, double tol) {
  std::vector<Index> col;
  std::vector<double> val;
  col.reserve(A.val.size());
  val.reserve(A.val.size());
  std::vector<Index> rp(static_cast<size_t>(A.nrows + 1), 0);
  for (Index i = 0; i < A.nrows; ++i) {
    for (Index k = A.rowptr[i]; k < A.rowptr[i + 1]; ++k) {
      if (std::abs(A.val[k]) >= tol || A.col[k] == i) {
        col.push_back(A.col[k]);
        val.push_back(A.val[k]);
      }
    }
    rp[i + 1] = static_cast<Index>(col.size());
  }
  A.rowptr = std::move(rp);
  A.col = std::move(col);
  A.val = std::move(val);
}

}  // namespace dpn
