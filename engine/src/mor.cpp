#include "dpn/mor.hpp"

#include "dpn/solvers.hpp"

#include <Eigen/Dense>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace dpn {
namespace {

void axpy(double a, const double* x, double* y, Index n) {
  for (Index i = 0; i < n; ++i) {
    y[i] += a * x[i];
  }
}

bool mgs_append(std::vector<double>& V, int& m, Index n, std::vector<double>& w, double tol) {
  const double nrm0 = nrm2(w.data(), n);
  if (nrm0 < tol) {
    return false;
  }
  for (int k = 0; k < m; ++k) {
    const double* vk = V.data() + static_cast<size_t>(k) * static_cast<size_t>(n);
    const double a = dot(w.data(), vk, n);
    for (Index i = 0; i < n; ++i) {
      w[i] -= a * vk[i];
    }
  }
  for (int k = 0; k < m; ++k) {
    const double* vk = V.data() + static_cast<size_t>(k) * static_cast<size_t>(n);
    const double a = dot(w.data(), vk, n);
    for (Index i = 0; i < n; ++i) {
      w[i] -= a * vk[i];
    }
  }
  const double nrm = nrm2(w.data(), n);
  if (nrm < std::max(tol, 1e-12 * nrm0)) {
    return false;
  }
  for (Index i = 0; i < n; ++i) {
    w[i] /= nrm;
  }
  V.resize(static_cast<size_t>(m + 1) * static_cast<size_t>(n));
  std::copy(w.begin(), w.end(), V.begin() + static_cast<size_t>(m) * static_cast<size_t>(n));
  ++m;
  return true;
}

Csr descriptor_rlc(const Csr& Gmesh, const Index* bumps, int n_bumps, double pkg_r, Index* n_aug) {
  /* Unsymmetric MNA matching the BE companion with i_L history:
       C dv/dt + G v − i_L = −I_draw
       L di/dt + R i + v_bump = Vsrc
     so A[b, n+k] = −1, A[n+k, b] = +1, A[n+k, n+k] = R.
     Symmetric Bᵀ=B would give L i' + R i − v = Vsrc (wrong sign on v).
     (A + sE) is unsymmetric; factored with SparseLU, never AMG. */
  const Index n = Gmesh.nrows;
  const Index p = std::max(n_bumps, 0);
  const Index N = n + p;
  *n_aug = N;
  std::vector<Index> ti;
  std::vector<Index> tj;
  std::vector<double> tv;
  const Index gnnz = Gmesh.nnz();
  ti.reserve(static_cast<size_t>(gnnz + 3 * p));
  tj.reserve(static_cast<size_t>(gnnz + 3 * p));
  tv.reserve(static_cast<size_t>(gnnz + 3 * p));
  for (Index i = 0; i < n; ++i) {
    for (Index k = Gmesh.rowptr[i]; k < Gmesh.rowptr[i + 1]; ++k) {
      ti.push_back(i);
      tj.push_back(Gmesh.col[k]);
      tv.push_back(Gmesh.val[k]);
    }
  }
  const double R = std::max(pkg_r, 1e-9);
  for (int k = 0; k < p; ++k) {
    const Index b = bumps[k];
    if (b < 0 || b >= n) {
      continue;
    }
    const Index ik = n + static_cast<Index>(k);
    ti.push_back(b);
    tj.push_back(ik);
    tv.push_back(-1.0);
    ti.push_back(ik);
    tj.push_back(b);
    tv.push_back(1.0);
    ti.push_back(ik);
    tj.push_back(ik);
    tv.push_back(R);
  }
  return from_triplets(N, ti.data(), tj.data(), tv.data(), static_cast<Index>(ti.size()));
}

}  // namespace

void RationalMor::build_basis(const Csr& A, const double* Ediag, Index n_aug, int n_starts,
                              const double* starts_aug, int n_shifts, const double* shifts,
                              int n_moments) {
  A_ = A;
  Ediag_.assign(Ediag, Ediag + n_aug);
  n_aug_ = n_aug;
  const auto t0 = std::chrono::steady_clock::now();
  const int cap = std::min(static_cast<int>(n_aug), 96);
  V_.clear();
  V_.reserve(static_cast<size_t>(cap) * static_cast<size_t>(n_aug));
  m_ = 0;
  const int moments = std::max(1, n_moments);
  std::vector<double> rhs(static_cast<size_t>(n_aug));
  std::vector<double> x(static_cast<size_t>(n_aug));
  std::vector<double> d(static_cast<size_t>(n_aug));

  for (int s = 0; s < n_shifts && m_ < cap; ++s) {
    const double shift = shifts[s];
    for (Index i = 0; i < n_aug; ++i) {
      d[i] = shift * Ediag_[i];
    }
    Csr K = plus_diag(A_, d.data());
    auto lu = make_direct(K);
    for (int b = 0; b < n_starts && m_ < cap; ++b) {
      const double* start = starts_aug + static_cast<size_t>(b) * static_cast<size_t>(n_aug);
      std::copy(start, start + n_aug, rhs.begin());
      for (int mom = 0; mom < moments && m_ < cap; ++mom) {
        if (mom > 0) {
          const double* vlast = V_.data() + static_cast<size_t>(m_ - 1) * static_cast<size_t>(n_aug);
          for (Index i = 0; i < n_aug; ++i) {
            rhs[i] = Ediag_[i] * vlast[i];
          }
        }
        lu->solve(rhs.data(), x.data(), nullptr);
        if (!mgs_append(V_, m_, n_aug, x, 1e-14)) {
          break;
        }
      }
    }
  }
  if (m_ == 0) {
    std::fill(rhs.begin(), rhs.end(), 1.0);
    auto lu = make_direct(A_);
    lu->solve(rhs.data(), x.data(), nullptr);
    if (!mgs_append(V_, m_, n_aug, x, 1e-14)) {
      std::fill(x.begin(), x.end(), 1.0 / std::sqrt(static_cast<double>(n_aug)));
      mgs_append(V_, m_, n_aug, x, 1e-30);
    }
  }

  Ar_.assign(static_cast<size_t>(m_ * m_), 0.0);
  Er_.assign(static_cast<size_t>(m_ * m_), 0.0);
  std::vector<double> av(static_cast<size_t>(n_aug));
  for (int k = 0; k < m_; ++k) {
    const double* vk = V_.data() + static_cast<size_t>(k) * static_cast<size_t>(n_aug);
    A_.spmv(vk, av.data());
    for (int j = 0; j < m_; ++j) {
      const double* vj = V_.data() + static_cast<size_t>(j) * static_cast<size_t>(n_aug);
      Ar_[j * m_ + k] = dot(vj, av.data(), n_aug);
      double ejk = 0.0;
      for (Index i = 0; i < n_aug; ++i) {
        ejk += vj[i] * Ediag_[i] * vk[i];
      }
      Er_[j * m_ + k] = ejk;
    }
  }
  setup_s_ = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
}

RationalMor::RationalMor(const Csr& G, const double* C, int n_starts, const double* starts,
                         int n_shifts, const double* shifts, int n_moments) {
  n_volt_ = G.nrows;
  rlc_ = false;
  build_basis(G, C, n_volt_, n_starts, starts, n_shifts, shifts, n_moments);
}

RationalMor::RationalMor(const Csr& Gmesh, const double* C, const Index* bumps, int n_bumps,
                         const double* bump_v, double pkg_r, double pkg_l, int n_starts,
                         const double* starts, int n_shifts, const double* shifts, int n_moments) {
  n_volt_ = Gmesh.nrows;
  rlc_ = pkg_l > 0.0 && n_bumps > 0;
  if (!rlc_) {
    double g_eq = 0.0, hsc = 0.0;
    rl_companion(pkg_r, 0.0, 1.0, &g_eq, &hsc);
    std::vector<double> d(static_cast<size_t>(n_volt_), 0.0);
    for (int k = 0; k < n_bumps; ++k) {
      const Index b = bumps[k];
      if (b >= 0 && b < n_volt_) {
        d[b] += g_eq;
      }
    }
    Csr A = plus_diag(Gmesh, d.data());
    build_basis(A, C, n_volt_, n_starts, starts, n_shifts, shifts, n_moments);
    return;
  }

  Index n_aug = 0;
  Csr A = descriptor_rlc(Gmesh, bumps, n_bumps, pkg_r, &n_aug);
  std::vector<double> E(static_cast<size_t>(n_aug), 0.0);
  for (Index i = 0; i < n_volt_; ++i) {
    E[i] = C[i];
  }
  for (int k = 0; k < n_bumps; ++k) {
    E[n_volt_ + k] = pkg_l;
  }
  bump_v_.assign(bump_v, bump_v + n_bumps);

  /* Ports: each inductor (Vsrc), caller voltage starts, then all-node common-mode. */
  const int ns_aug = n_starts + n_bumps + 1;
  std::vector<double> starts_aug(static_cast<size_t>(ns_aug) * static_cast<size_t>(n_aug), 0.0);
  int col = 0;
  for (int k = 0; k < n_bumps; ++k, ++col) {
    starts_aug[static_cast<size_t>(col) * static_cast<size_t>(n_aug) + static_cast<size_t>(n_volt_ + k)] =
        1.0;
  }
  for (int b = 0; b < n_starts; ++b, ++col) {
    const double* src = starts + static_cast<size_t>(b) * static_cast<size_t>(n_volt_);
    double* dst = starts_aug.data() + static_cast<size_t>(col) * static_cast<size_t>(n_aug);
    std::copy(src, src + n_volt_, dst);
  }
  {
    double* sV = starts_aug.data() + static_cast<size_t>(col) * static_cast<size_t>(n_aug);
    const double nv = 1.0 / std::sqrt(static_cast<double>(std::max(n_volt_, Index{1})));
    for (Index i = 0; i < n_volt_; ++i) {
      sV[i] = nv;
    }
  }
  build_basis(A, E.data(), n_aug, ns_aug, starts_aug.data(), n_shifts, shifts, n_moments);
}

TranResult RationalMor::timestep(const double* leak, const double* pad, double dt, double t_end,
                                 double vdd, const TriangleSrc* ev, int n_ev) const {
  TranResult out;
  out.worst_v = vdd;
  out.V_worst.assign(static_cast<size_t>(n_volt_), vdd);
  if (m_ <= 0 || dt <= 0.0) {
    return out;
  }
  Eigen::MatrixXd Ar(m_, m_), Er(m_, m_), Kr(m_, m_);
  for (int i = 0; i < m_; ++i) {
    for (int j = 0; j < m_; ++j) {
      Ar(i, j) = Ar_[i * m_ + j];
      Er(i, j) = Er_[i * m_ + j];
    }
  }
  Kr = Ar + Er / dt;
  Eigen::PartialPivLU<Eigen::MatrixXd> lu(Kr);

  const int steps = std::max(2, static_cast<int>(std::ceil(t_end / dt)));
  Eigen::VectorXd z = Eigen::VectorXd::Zero(m_);
  Eigen::VectorXd znext(m_), rhs(m_), f(m_);
  std::vector<double> I(static_cast<size_t>(n_volt_));
  std::vector<double> x(static_cast<size_t>(n_aug_), 0.0);
  std::vector<double> u(static_cast<size_t>(n_aug_), 0.0);
  const Index p = n_aug_ - n_volt_;
  if (rlc_) {
    for (Index i = 0; i < n_volt_; ++i) {
      x[i] = vdd;
    }
    /* Consistent mass projection: Er z0 = Vᵀ E x0 (UIC v=Vdd, i_L=0). */
    Eigen::VectorXd Ex(m_);
    Ex.setZero();
    for (int k = 0; k < m_; ++k) {
      const double* vk = V_.data() + static_cast<size_t>(k) * static_cast<size_t>(n_aug_);
      double s = 0.0;
      for (Index i = 0; i < n_volt_; ++i) {
        s += vk[i] * Ediag_[i] * vdd;
      }
      Ex[k] = s;
    }
    Eigen::PartialPivLU<Eigen::MatrixXd> Erlu(Er);
    z = Erlu.solve(Ex);
  }
  std::vector<double> V(static_cast<size_t>(n_volt_), vdd);
  std::vector<double> av(static_cast<size_t>(n_aug_));
  double res_max = 0.0;
  const auto t0 = std::chrono::steady_clock::now();

  auto reconstruct_v = [&](const Eigen::VectorXd& zk) {
    std::fill(V.begin(), V.end(), rlc_ ? 0.0 : vdd);
    for (int k = 0; k < m_; ++k) {
      const double* vk = V_.data() + static_cast<size_t>(k) * static_cast<size_t>(n_aug_);
      for (Index i = 0; i < n_volt_; ++i) {
        V[i] += zk[k] * vk[i];
      }
    }
  };

  for (int s = 0; s < steps; ++s) {
    const double t = static_cast<double>(s) * dt;
    fill_idraw(n_volt_, t, leak, ev, n_ev, I.data());
    f.setZero();
    if (rlc_) {
      std::fill(u.begin(), u.end(), 0.0);
      for (Index i = 0; i < n_volt_; ++i) {
        u[i] = -I[i];
      }
      for (Index k = 0; k < p; ++k) {
        u[n_volt_ + k] = (k < static_cast<Index>(bump_v_.size())) ? bump_v_[k] : vdd;
      }
      for (int k = 0; k < m_; ++k) {
        const double* vk = V_.data() + static_cast<size_t>(k) * static_cast<size_t>(n_aug_);
        f[k] = dot(vk, u.data(), n_aug_);
      }
      rhs = (Er * z) / dt + f;
    } else {
      for (int k = 0; k < m_; ++k) {
        const double* vk = V_.data() + static_cast<size_t>(k) * static_cast<size_t>(n_aug_);
        f[k] = dot(vk, I.data(), n_volt_);
      }
      rhs = (Er * z) / dt - f;
    }
    znext = lu.solve(rhs);
    reconstruct_v(znext);

    if (rlc_) {
      std::fill(x.begin(), x.end(), 0.0);
      for (int k = 0; k < m_; ++k) {
        const double* vk = V_.data() + static_cast<size_t>(k) * static_cast<size_t>(n_aug_);
        axpy(znext[k], vk, x.data(), n_aug_);
      }
      std::vector<double> xprev(static_cast<size_t>(n_aug_), 0.0);
      for (int k = 0; k < m_; ++k) {
        const double* vk = V_.data() + static_cast<size_t>(k) * static_cast<size_t>(n_aug_);
        axpy(z[k], vk, xprev.data(), n_aug_);
      }
      A_.spmv(x.data(), av.data());
      double nr = 0.0, nb = 0.0;
      for (Index i = 0; i < n_aug_; ++i) {
        const double r = Ediag_[i] * (x[i] - xprev[i]) / dt + av[i] - u[i];
        nr += r * r;
        nb += u[i] * u[i];
      }
      const double rel = (nb < 1e-30) ? std::sqrt(nr) : std::sqrt(nr / nb);
      res_max = std::max(res_max, rel);
    } else {
      std::vector<double> Vprev(static_cast<size_t>(n_volt_), vdd);
      if (s > 0) {
        std::fill(Vprev.begin(), Vprev.end(), vdd);
        for (int k = 0; k < m_; ++k) {
          const double* vk = V_.data() + static_cast<size_t>(k) * static_cast<size_t>(n_aug_);
          axpy(z[k], vk, Vprev.data(), n_volt_);
        }
      }
      A_.spmv(V.data(), av.data());
      double nr = 0.0, nb = 0.0;
      for (Index i = 0; i < n_volt_; ++i) {
        const double r = Ediag_[i] * (V[i] - Vprev[i]) / dt + av[i] - (pad ? pad[i] : 0.0) + I[i];
        nr += r * r;
        nb += I[i] * I[i];
      }
      const double rel = (nb < 1e-30) ? std::sqrt(nr) : std::sqrt(nr / nb);
      res_max = std::max(res_max, rel);
    }

    z = znext;
    double vmin = V[0];
    Index imin = 0;
    double itot = 0.0;
    for (Index i = 0; i < n_volt_; ++i) {
      if (V[i] < vmin) {
        vmin = V[i];
        imin = i;
      }
      itot += I[i];
    }
    out.wave_t.push_back(t);
    out.wave_vmin.push_back(vmin);
    out.wave_itot.push_back(itot);
    if (vmin < out.worst_v) {
      out.worst_v = vmin;
      out.worst_t = t;
      out.worst_node = imin;
      out.V_worst = V;
    }
  }
  out.steps = steps;
  out.rel_res_max = res_max;
  out.solve_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  return out;
}

std::unique_ptr<RationalMor> make_mor(const Csr& G, const double* C, int n_starts,
                                      const double* starts, int n_shifts, const double* shifts,
                                      int n_moments) {
  return std::make_unique<RationalMor>(G, C, n_starts, starts, n_shifts, shifts, n_moments);
}

std::unique_ptr<RationalMor> make_mor_rlc(const Csr& Gmesh, const double* C, const Index* bumps,
                                          int n_bumps, const double* bump_v, double pkg_r,
                                          double pkg_l, int n_starts, const double* starts,
                                          int n_shifts, const double* shifts, int n_moments) {
  return std::make_unique<RationalMor>(Gmesh, C, bumps, n_bumps, bump_v, pkg_r, pkg_l, n_starts,
                                       starts, n_shifts, shifts, n_moments);
}

}  // namespace dpn
