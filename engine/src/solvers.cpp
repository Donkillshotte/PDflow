#include "dpn/solvers.hpp"

#include <Eigen/Sparse>
#include <Eigen/SparseLU>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace dpn {
namespace {

using SpMat = Eigen::SparseMatrix<double, Eigen::ColMajor, int>;
using SpLU = Eigen::SparseLU<SpMat>;

constexpr Index kCoarseN = 64;
constexpr double kTheta = 0.25;
constexpr double kJacobiOmega = 0.7;
constexpr double kSmoothOmega = 0.67;
constexpr int kPreSweeps = 2;
constexpr int kPostSweeps = 2;

SpMat to_eigen(const Csr& A) {
  std::vector<Eigen::Triplet<double>> t;
  t.reserve(static_cast<size_t>(A.nnz()));
  for (Index i = 0; i < A.nrows; ++i) {
    for (Index k = A.rowptr[i]; k < A.rowptr[i + 1]; ++k) {
      t.emplace_back(i, A.col[k], A.val[k]);
    }
  }
  SpMat M(A.nrows, A.ncols);
  M.setFromTriplets(t.begin(), t.end());
  M.makeCompressed();
  return M;
}

void jacobi(const Csr& A, const std::vector<double>& dinv, const double* b, double* x,
            int sweeps) {
  std::vector<double> ax(static_cast<size_t>(A.nrows));
  for (int s = 0; s < sweeps; ++s) {
    A.spmv(x, ax.data());
    for (Index i = 0; i < A.nrows; ++i) {
      x[i] += kJacobiOmega * dinv[i] * (b[i] - ax[i]);
    }
  }
}

struct Agg {
  std::vector<Index> id;
  Index nagg = 0;
};

Agg aggregates(const Csr& A) {
  const Index n = A.nrows;
  std::vector<std::vector<Index>> strong(static_cast<size_t>(n));
  for (Index i = 0; i < n; ++i) {
    double max_neg = 0.0;
    for (Index k = A.rowptr[i]; k < A.rowptr[i + 1]; ++k) {
      if (A.col[k] == i) {
        continue;
      }
      max_neg = std::max(max_neg, -A.val[k]);
    }
    if (max_neg <= 0.0) {
      continue;
    }
    const double thresh = kTheta * max_neg;
    for (Index k = A.rowptr[i]; k < A.rowptr[i + 1]; ++k) {
      if (A.col[k] == i) {
        continue;
      }
      if (-A.val[k] >= thresh) {
        strong[i].push_back(A.col[k]);
      }
    }
  }

  Agg out;
  out.id.assign(n, -1);
  for (Index i = 0; i < n; ++i) {
    if (out.id[i] >= 0) {
      continue;
    }
    std::vector<Index> members;
    members.push_back(i);
    for (Index j : strong[i]) {
      if (out.id[j] < 0) {
        members.push_back(j);
      }
    }
    for (Index j : members) {
      if (out.id[j] < 0) {
        out.id[j] = out.nagg;
      }
    }
    ++out.nagg;
  }
  for (Index i = 0; i < n; ++i) {
    if (out.id[i] >= 0) {
      continue;
    }
    bool placed = false;
    for (Index j : strong[i]) {
      if (out.id[j] >= 0) {
        out.id[i] = out.id[j];
        placed = true;
        break;
      }
    }
    if (!placed) {
      out.id[i] = out.nagg++;
    }
  }
  return out;
}

Csr tentative_p(const Agg& agg, Index n) {
  Csr P;
  P.nrows = n;
  P.ncols = agg.nagg;
  P.rowptr.resize(static_cast<size_t>(n + 1));
  P.col.resize(static_cast<size_t>(n));
  P.val.assign(static_cast<size_t>(n), 1.0);
  for (Index i = 0; i < n; ++i) {
    P.rowptr[i] = i;
    P.col[i] = agg.id[i];
  }
  P.rowptr[n] = n;
  return P;
}

Csr smooth_p(const Csr& A, const Csr& P) {
  std::vector<double> dinv;
  A.diag_inv(dinv);
  Csr DinvA;
  DinvA.nrows = A.nrows;
  DinvA.ncols = A.ncols;
  DinvA.rowptr = A.rowptr;
  DinvA.col = A.col;
  DinvA.val = A.val;
  for (Index i = 0; i < A.nrows; ++i) {
    for (Index k = DinvA.rowptr[i]; k < DinvA.rowptr[i + 1]; ++k) {
      DinvA.val[k] *= dinv[i];
    }
  }
  Csr AP = spmm(DinvA, P);
  Csr R;
  R.nrows = P.nrows;
  R.ncols = P.ncols;
  R.rowptr.assign(P.nrows + 1, 0);
  std::vector<Index> marker(static_cast<size_t>(P.ncols), -1);
  std::vector<double> acc(static_cast<size_t>(P.ncols), 0.0);
  std::vector<Index> cols;
  std::vector<double> vals;
  for (Index i = 0; i < P.nrows; ++i) {
    std::vector<Index> idx;
    auto accum = [&](const Csr& M, double sign) {
      for (Index k = M.rowptr[i]; k < M.rowptr[i + 1]; ++k) {
        const Index j = M.col[k];
        if (marker[j] != i) {
          marker[j] = i;
          idx.push_back(j);
          acc[j] = sign * M.val[k];
        } else {
          acc[j] += sign * M.val[k];
        }
      }
    };
    accum(P, 1.0);
    accum(AP, -kSmoothOmega);
    std::sort(idx.begin(), idx.end());
    R.rowptr[i + 1] = R.rowptr[i] + static_cast<Index>(idx.size());
    for (Index j : idx) {
      cols.push_back(j);
      vals.push_back(acc[j]);
    }
  }
  R.col = std::move(cols);
  R.val = std::move(vals);
  drop_small(R, 1e-14);
  return R;
}

}  // namespace

double residual_rel(const Csr& A, const double* x, const double* b) {
  std::vector<double> ax(static_cast<size_t>(A.nrows));
  A.spmv(x, ax.data());
  double nr = 0.0, nb = 0.0;
  for (Index i = 0; i < A.nrows; ++i) {
    const double r = b[i] - ax[i];
    nr += r * r;
    nb += b[i] * b[i];
  }
  if (nb < 1e-30) {
    return std::sqrt(nr);
  }
  return std::sqrt(nr / nb);
}

class DirectSolver final : public Solver {
 public:
  explicit DirectSolver(const Csr& A) : A_(A) {
    n_ = A.nrows;
    const auto t0 = std::chrono::steady_clock::now();
    M_ = to_eigen(A);
    lu_.compute(M_);
    if (lu_.info() != Eigen::Success) {
      throw std::runtime_error("SparseLU factorization failed");
    }
    setup_s_ = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  }

  void solve(const double* b, double* x, const double*) override {
    Eigen::Map<const Eigen::VectorXd> bv(b, n_);
    Eigen::VectorXd xv = lu_.solve(bv);
    for (Index i = 0; i < n_; ++i) {
      x[i] = xv[i];
    }
    last_relres_ = residual_rel(A_, x, b);
  }

  const char* name() const override { return "A_direct_be"; }

 private:
  Csr A_;
  SpMat M_;
  SpLU lu_;
};

struct Level {
  Csr A;
  Csr P;
  Csr Pt;
  std::vector<double> dinv;
};

class AmgSolver final : public Solver {
 public:
  explicit AmgSolver(const Csr& A) {
    n_ = A.nrows;
    const auto t0 = std::chrono::steady_clock::now();
    Csr cur = A;
    fine_ = A;
    while (cur.nrows > kCoarseN) {
      Agg agg = aggregates(cur);
      if (agg.nagg < 2 || agg.nagg > static_cast<Index>(0.85 * cur.nrows)) {
        break;
      }
      Csr Ptent = tentative_p(agg, cur.nrows);
      Csr P = smooth_p(cur, Ptent);
      Csr AP = spmm(cur, P);
      Csr Pt = transpose(P);
      Csr Ac = spmm(Pt, AP);
      Level lvl;
      lvl.A = cur;
      lvl.P = std::move(P);
      lvl.Pt = transpose(lvl.P);
      lvl.A.diag_inv(lvl.dinv);
      levels_.push_back(std::move(lvl));
      cur = std::move(Ac);
    }
    coarse_ = to_eigen(cur);
    coarse_csr_ = cur;
    coarse_lu_.compute(coarse_);
    if (coarse_lu_.info() != Eigen::Success) {
      throw std::runtime_error("coarse SparseLU failed");
    }
    setup_s_ = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  }

  int n_levels() const override { return static_cast<int>(levels_.size()) + 1; }

  const char* name() const override { return "B_sa_amg"; }

  void solve(const double* b, double* x, const double* x0) override {
    if (levels_.empty()) {
      Eigen::Map<const Eigen::VectorXd> bv(b, n_);
      Eigen::VectorXd xv = coarse_lu_.solve(bv);
      for (Index i = 0; i < n_; ++i) {
        x[i] = xv[i];
      }
      last_relres_ = residual_rel(fine_, x, b);
      return;
    }
    if (x0) {
      std::copy(x0, x0 + n_, x);
    } else {
      std::fill(x, x + n_, 0.0);
    }
    cg(b, x);
    last_relres_ = residual_rel(fine_, x, b);
  }

 private:
  void vcycle(int depth, const double* b, double* x) {
    if (depth >= static_cast<int>(levels_.size())) {
      Eigen::Map<const Eigen::VectorXd> bv(b, coarse_csr_.nrows);
      Eigen::VectorXd xv = coarse_lu_.solve(bv);
      for (Index i = 0; i < coarse_csr_.nrows; ++i) {
        x[i] = xv[i];
      }
      return;
    }
    Level& L = levels_[depth];
    const Index n = L.A.nrows;
    jacobi(L.A, L.dinv, b, x, kPreSweeps);
    std::vector<double> ax(n), r(n);
    L.A.spmv(x, ax.data());
    for (Index i = 0; i < n; ++i) {
      r[i] = b[i] - ax[i];
    }
    const Index nc = L.P.ncols;
    std::vector<double> rc(nc, 0.0), ec(nc, 0.0);
    L.Pt.spmv(r.data(), rc.data());
    vcycle(depth + 1, rc.data(), ec.data());
    std::vector<double> e(n, 0.0);
    L.P.spmv(ec.data(), e.data());
    for (Index i = 0; i < n; ++i) {
      x[i] += e[i];
    }
    jacobi(L.A, L.dinv, b, x, kPostSweeps);
  }

  void apply_prec(const double* r, double* z) {
    std::fill(z, z + n_, 0.0);
    vcycle(0, r, z);
  }

  void cg(const double* b, double* x) {
    std::vector<double> r(n_), z(n_), p(n_), ap(n_);
    fine_.spmv(x, ap.data());
    for (Index i = 0; i < n_; ++i) {
      r[i] = b[i] - ap[i];
    }
    const double nb = nrm2(b, n_);
    apply_prec(r.data(), z.data());
    p = z;
    double rz = dot(r.data(), z.data(), n_);
    for (int it = 0; it < 64; ++it) {
      fine_.spmv(p.data(), ap.data());
      const double pAp = dot(p.data(), ap.data(), n_);
      if (std::abs(pAp) < 1e-30) {
        break;
      }
      const double alpha = rz / pAp;
      for (Index i = 0; i < n_; ++i) {
        x[i] += alpha * p[i];
        r[i] -= alpha * ap[i];
      }
      if (nb > 0 && nrm2(r.data(), n_) / nb < 1e-8) {
        return;
      }
      apply_prec(r.data(), z.data());
      const double rz_new = dot(r.data(), z.data(), n_);
      const double beta = rz_new / (rz == 0.0 ? 1.0 : rz);
      for (Index i = 0; i < n_; ++i) {
        p[i] = z[i] + beta * p[i];
      }
      rz = rz_new;
    }
    // extra V-cycles if CG stalled
    for (int k = 0; k < 6; ++k) {
      vcycle(0, b, x);
    }
  }

  Csr fine_;
  std::vector<Level> levels_;
  Csr coarse_csr_;
  SpMat coarse_;
  SpLU coarse_lu_;
};

std::unique_ptr<Solver> make_direct(const Csr& A) { return std::make_unique<DirectSolver>(A); }
std::unique_ptr<Solver> make_amg(const Csr& A) { return std::make_unique<AmgSolver>(A); }

}  // namespace dpn
