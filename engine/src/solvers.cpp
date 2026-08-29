#include "dpn/solvers.hpp"

#include <Eigen/IterativeLinearSolvers>
#include <Eigen/Sparse>
#include <Eigen/SparseLU>
#include <algorithm>
#include <chrono>
#include <climits>
#include <cmath>
#include <memory>
#include <queue>
#include <stdexcept>
#include <vector>

namespace dpn {
namespace {

using SpMat = Eigen::SparseMatrix<double, Eigen::ColMajor, Index>;
using SpLU = Eigen::SparseLU<SpMat>;

constexpr Index kCoarseN = 64;
constexpr double kTheta = 0.25;
constexpr double kJacobiOmega = 0.7;
constexpr double kSmoothOmega = 0.67;
constexpr int kPreSweeps = 2;
constexpr int kPostSweeps = 2;

SpMat to_eigen(const Csr& A) {
  std::vector<Eigen::Triplet<double, Index>> t;
  t.reserve(static_cast<size_t>(A.nnz()));
  for (Index i = 0; i < A.nrows; ++i) {
    for (Index k = A.rowptr[i]; k < A.rowptr[i + 1]; ++k) {
      t.emplace_back(i, A.col[k], A.val[k]);
    }
  }
  SpMat M(static_cast<Eigen::Index>(A.nrows), static_cast<Eigen::Index>(A.ncols));
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

struct RasDom {
  std::vector<Index> all;       /* overlapping nodes, local order */
  std::vector<Index> interior;  /* owner == s, RAS restriction */
  std::vector<Index> loc;       /* global → local in all, or -1 */
  Csr A;
  SpMat M;
  std::unique_ptr<SpLU> lu;     /* SparseLU is neither copyable nor movable */
};

constexpr int kRasHops = 2;
constexpr int kRasGmresM = 32;
constexpr int kRasGmresRestart = 8;
constexpr double kRasTol = 1e-10;

class RasSolver final : public Solver {
 public:
  explicit RasSolver(const Csr& A) {
    n_ = A.nrows;
    fine_ = A;
    const auto t0 = std::chrono::steady_clock::now();
    const Index n = n_;
    int ndom = 1;
    if (n >= 8) {
      ndom = 2;
    }
    if (n > 64) {
      ndom = std::min(8, std::max(2, static_cast<int>(n / 32)));
    }
    owner_.assign(static_cast<size_t>(n), -1);
    Index unassigned = n;
    Index seed = 0;
    for (int s = 0; s < ndom && unassigned > 0; ++s) {
      while (seed < n && owner_[static_cast<size_t>(seed)] >= 0) {
        ++seed;
      }
      if (seed >= n) {
        break;
      }
      const Index want = std::max(Index{1}, unassigned / (ndom - s));
      std::queue<Index> q;
      q.push(seed);
      owner_[static_cast<size_t>(seed)] = s;
      --unassigned;
      Index taken = 1;
      while (!q.empty() && taken < want) {
        const Index i = q.front();
        q.pop();
        for (Index k = A.rowptr[i]; k < A.rowptr[i + 1]; ++k) {
          const Index j = A.col[k];
          if (owner_[static_cast<size_t>(j)] < 0) {
            owner_[static_cast<size_t>(j)] = s;
            --unassigned;
            ++taken;
            q.push(j);
            if (taken >= want) {
              break;
            }
          }
        }
      }
    }
    for (Index i = 0; i < n; ++i) {
      if (owner_[static_cast<size_t>(i)] < 0) {
        owner_[static_cast<size_t>(i)] = std::max(ndom - 1, 0);
      }
    }
    ndom_ = ndom;
    doms_.resize(static_cast<size_t>(ndom));
    for (int s = 0; s < ndom; ++s) {
      std::vector<char> in(static_cast<size_t>(n), 0);
      for (Index i = 0; i < n; ++i) {
        if (owner_[static_cast<size_t>(i)] == s) {
          in[static_cast<size_t>(i)] = 1;
          for (Index k = A.rowptr[i]; k < A.rowptr[i + 1]; ++k) {
            in[static_cast<size_t>(A.col[k])] = 1;
          }
        }
      }
      for (int hop = 1; hop < kRasHops; ++hop) {
        std::vector<char> nxt = in;
        for (Index i = 0; i < n; ++i) {
          if (!in[static_cast<size_t>(i)]) {
            continue;
          }
          for (Index k = A.rowptr[i]; k < A.rowptr[i + 1]; ++k) {
            nxt[static_cast<size_t>(A.col[k])] = 1;
          }
        }
        in.swap(nxt);
      }
      RasDom& D = doms_[static_cast<size_t>(s)];
      D.loc.assign(static_cast<size_t>(n), -1);
      for (Index i = 0; i < n; ++i) {
        if (!in[static_cast<size_t>(i)]) {
          continue;
        }
        D.loc[static_cast<size_t>(i)] = static_cast<Index>(D.all.size());
        D.all.push_back(i);
        if (owner_[static_cast<size_t>(i)] == s) {
          D.interior.push_back(i);
        }
      }
      std::vector<Index> ti, tj;
      std::vector<double> tv;
      const Index ns = static_cast<Index>(D.all.size());
      if (ns <= 0) {
        continue;
      }
      for (Index gi : D.all) {
        const Index i = D.loc[static_cast<size_t>(gi)];
        for (Index k = A.rowptr[gi]; k < A.rowptr[gi + 1]; ++k) {
          const Index gj = A.col[k];
          const Index j = D.loc[static_cast<size_t>(gj)];
          if (j < 0) {
            continue;
          }
          ti.push_back(i);
          tj.push_back(j);
          tv.push_back(A.val[k]);
        }
      }
      D.A = from_triplets(ns, ti.data(), tj.data(), tv.data(), static_cast<Index>(ti.size()));
      D.M = to_eigen(D.A);
      D.lu = std::make_unique<SpLU>();
      D.lu->compute(D.M);
      if (D.lu->info() != Eigen::Success) {
        throw std::runtime_error("RAS subdomain SparseLU failed");
      }
    }
    setup_s_ = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  }

  int n_levels() const override { return ndom_; }
  const char* name() const override { return "D_ras_schwarz"; }

  void solve(const double* b, double* x, const double* x0) override {
    if (x0) {
      std::copy(x0, x0 + n_, x);
    } else {
      std::fill(x, x + n_, 0.0);
    }
    if (ndom_ == 1 && !doms_.empty() && doms_[0].lu) {
      Eigen::Map<const Eigen::VectorXd> bv(b, n_);
      Eigen::VectorXd xv = doms_[0].lu->solve(bv);
      for (Index i = 0; i < n_; ++i) {
        x[i] = xv[i];
      }
      last_relres_ = residual_rel(fine_, x, b);
      return;
    }
    gmres(b, x);
  }

 private:
  void apply(const double* r, double* z) const {
    std::fill(z, z + n_, 0.0);
    for (const RasDom& D : doms_) {
      if (!D.lu || D.all.empty()) {
        continue;
      }
      const Index ns = static_cast<Index>(D.all.size());
      Eigen::VectorXd rs(ns);
      for (Index k = 0; k < ns; ++k) {
        rs[k] = r[D.all[static_cast<size_t>(k)]];
      }
      Eigen::VectorXd es = D.lu->solve(rs);
      for (Index gi : D.interior) {
        const Index k = D.loc[static_cast<size_t>(gi)];
        z[gi] += es[k];
      }
    }
  }

  /* Left-preconditioned GMRES: RAS is not SPD, so CG is the wrong Krylov. */
  void gmres(const double* b, double* x) {
    const Index n = n_;
    const double nb = nrm2(b, n);
    const double tol = kRasTol * (nb > 0.0 ? nb : 1.0);
    std::vector<double> r(static_cast<size_t>(n)), z(static_cast<size_t>(n)), w(static_cast<size_t>(n));
    std::vector<std::vector<double>> V(static_cast<size_t>(kRasGmresM + 1),
                                       std::vector<double>(static_cast<size_t>(n), 0.0));
    std::vector<std::vector<double>> H(static_cast<size_t>(kRasGmresM + 1),
                                       std::vector<double>(static_cast<size_t>(kRasGmresM), 0.0));
    std::vector<double> cs(static_cast<size_t>(kRasGmresM), 0.0);
    std::vector<double> sn(static_cast<size_t>(kRasGmresM), 0.0);
    std::vector<double> g(static_cast<size_t>(kRasGmresM + 1), 0.0);
    std::vector<double> y(static_cast<size_t>(kRasGmresM), 0.0);

    for (int restart = 0; restart < kRasGmresRestart; ++restart) {
      fine_.spmv(x, r.data());
      for (Index i = 0; i < n; ++i) {
        r[i] = b[i] - r[i];
      }
      apply(r.data(), z.data());
      const double beta = nrm2(z.data(), n);
      if (beta < tol) {
        last_relres_ = residual_rel(fine_, x, b);
        return;
      }
      const double invb = 1.0 / beta;
      for (Index i = 0; i < n; ++i) {
        V[0][static_cast<size_t>(i)] = z[i] * invb;
      }
      std::fill(g.begin(), g.end(), 0.0);
      g[0] = beta;
      int jlast = -1;
      for (int j = 0; j < kRasGmresM; ++j) {
        jlast = j;
        fine_.spmv(V[static_cast<size_t>(j)].data(), w.data());
        apply(w.data(), z.data());
        for (int i = 0; i <= j; ++i) {
          const double hij = dot(z.data(), V[static_cast<size_t>(i)].data(), n);
          H[static_cast<size_t>(i)][static_cast<size_t>(j)] = hij;
          for (Index k = 0; k < n; ++k) {
            z[k] -= hij * V[static_cast<size_t>(i)][static_cast<size_t>(k)];
          }
        }
        const double hnext = nrm2(z.data(), n);
        H[static_cast<size_t>(j + 1)][static_cast<size_t>(j)] = hnext;
        if (hnext > 0.0) {
          const double inv = 1.0 / hnext;
          for (Index k = 0; k < n; ++k) {
            V[static_cast<size_t>(j + 1)][static_cast<size_t>(k)] = z[k] * inv;
          }
        }
        for (int i = 0; i < j; ++i) {
          const double c = cs[static_cast<size_t>(i)];
          const double s = sn[static_cast<size_t>(i)];
          const double h0 = H[static_cast<size_t>(i)][static_cast<size_t>(j)];
          const double h1 = H[static_cast<size_t>(i + 1)][static_cast<size_t>(j)];
          H[static_cast<size_t>(i)][static_cast<size_t>(j)] = c * h0 + s * h1;
          H[static_cast<size_t>(i + 1)][static_cast<size_t>(j)] = -s * h0 + c * h1;
        }
        {
          const double h0 = H[static_cast<size_t>(j)][static_cast<size_t>(j)];
          const double h1 = H[static_cast<size_t>(j + 1)][static_cast<size_t>(j)];
          const double rho = std::hypot(h0, h1);
          const double c = (rho == 0.0) ? 1.0 : h0 / rho;
          const double s = (rho == 0.0) ? 0.0 : h1 / rho;
          cs[static_cast<size_t>(j)] = c;
          sn[static_cast<size_t>(j)] = s;
          H[static_cast<size_t>(j)][static_cast<size_t>(j)] = c * h0 + s * h1;
          H[static_cast<size_t>(j + 1)][static_cast<size_t>(j)] = 0.0;
          const double g0 = g[static_cast<size_t>(j)];
          const double g1 = g[static_cast<size_t>(j + 1)];
          g[static_cast<size_t>(j)] = c * g0 + s * g1;
          g[static_cast<size_t>(j + 1)] = -s * g0 + c * g1;
        }
        if (std::abs(g[static_cast<size_t>(j + 1)]) < tol) {
          break;
        }
      }
      for (int i = jlast; i >= 0; --i) {
        double s = g[static_cast<size_t>(i)];
        for (int k = i + 1; k <= jlast; ++k) {
          s -= H[static_cast<size_t>(i)][static_cast<size_t>(k)] * y[static_cast<size_t>(k)];
        }
        const double hii = H[static_cast<size_t>(i)][static_cast<size_t>(i)];
        y[static_cast<size_t>(i)] = (std::abs(hii) < 1e-30) ? 0.0 : s / hii;
      }
      for (int j = 0; j <= jlast; ++j) {
        const double yj = y[static_cast<size_t>(j)];
        for (Index i = 0; i < n; ++i) {
          x[i] += yj * V[static_cast<size_t>(j)][static_cast<size_t>(i)];
        }
      }
      last_relres_ = residual_rel(fine_, x, b);
      if (nb > 0.0 && last_relres_ < 1e-8) {
        return;
      }
    }
    last_relres_ = residual_rel(fine_, x, b);
  }

  Csr fine_;
  int ndom_ = 1;
  std::vector<Index> owner_;
  std::vector<RasDom> doms_;
};

class BicgSolver final : public Solver {
 public:
  using Ilut = Eigen::IncompleteLUT<double, Index>;
  using BicgIlut = Eigen::BiCGSTAB<SpMat, Ilut>;
  using BicgDiag = Eigen::BiCGSTAB<SpMat, Eigen::DiagonalPreconditioner<double>>;

  explicit BicgSolver(const Csr& A) : A_(A) {
    n_ = A.nrows;
    const auto t0 = std::chrono::steady_clock::now();
    M_ = to_eigen(A);
    const int maxit = static_cast<int>(
        std::min<Index>(std::max<Index>(Index{200}, 8 * n_), static_cast<Index>(INT_MAX / 4)));
    ilut_.preconditioner().setDroptol(1e-4);
    ilut_.preconditioner().setFillfactor(10);
    ilut_.setMaxIterations(maxit);
    ilut_.setTolerance(1e-12);
    bool ok = false;
    try {
      ilut_.compute(M_);
      ok = ilut_.info() == Eigen::Success;
    } catch (...) {
      ok = false;
    }
    if (ok) {
      use_ilut_ = true;
    } else {
      diag_.setMaxIterations(maxit);
      diag_.setTolerance(1e-12);
      diag_.compute(M_);
      if (diag_.info() != Eigen::Success) {
        throw std::runtime_error("BiCGSTAB setup failed");
      }
      use_ilut_ = false;
    }
    setup_s_ = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  }

  void solve(const double* b, double* x, const double* x0) override {
    Eigen::Map<const Eigen::VectorXd> bv(b, static_cast<Eigen::Index>(n_));
    Eigen::VectorXd xv(static_cast<Eigen::Index>(n_));
    if (x0) {
      Eigen::Map<const Eigen::VectorXd> x0v(x0, static_cast<Eigen::Index>(n_));
      if (use_ilut_) {
        xv = ilut_.solveWithGuess(bv, x0v);
      } else {
        xv = diag_.solveWithGuess(bv, x0v);
      }
    } else if (use_ilut_) {
      xv = ilut_.solve(bv);
    } else {
      xv = diag_.solve(bv);
    }
    for (Index i = 0; i < n_; ++i) {
      x[i] = xv[i];
    }
    last_relres_ = residual_rel(A_, x, b);
  }

  const char* name() const override { return "E_bicgstab"; }

 private:
  Csr A_;
  SpMat M_;
  BicgIlut ilut_;
  BicgDiag diag_;
  bool use_ilut_ = false;
};

std::unique_ptr<Solver> make_direct(const Csr& A) { return std::make_unique<DirectSolver>(A); }
std::unique_ptr<Solver> make_amg(const Csr& A) { return std::make_unique<AmgSolver>(A); }
std::unique_ptr<Solver> make_ras(const Csr& A) { return std::make_unique<RasSolver>(A); }
std::unique_ptr<Solver> make_bicgstab(const Csr& A) { return std::make_unique<BicgSolver>(A); }

}  // namespace dpn
