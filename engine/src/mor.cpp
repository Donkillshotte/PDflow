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
  // reorthogonalize
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

}  // namespace

RationalMor::RationalMor(const Csr& G, const double* C, int n_starts, const double* starts,
                         int n_shifts, const double* shifts, int n_moments) {
  n_ = G.nrows;
  G_ = G;
  C_.assign(C, C + n_);
  const auto t0 = std::chrono::steady_clock::now();
  const int cap = std::min(n_, 48);
  V_.reserve(static_cast<size_t>(cap) * static_cast<size_t>(n_));
  m_ = 0;
  const int moments = std::max(1, n_moments);
  std::vector<double> rhs(static_cast<size_t>(n_));
  std::vector<double> x(static_cast<size_t>(n_));
  std::vector<double> d(static_cast<size_t>(n_));

  for (int s = 0; s < n_shifts && m_ < cap; ++s) {
    const double shift = shifts[s];
    for (Index i = 0; i < n_; ++i) {
      d[i] = shift * C_[i];
    }
    Csr K = plus_diag(G_, d.data());
    auto lu = make_direct(K);
    for (int b = 0; b < n_starts && m_ < cap; ++b) {
      const double* start = starts + static_cast<size_t>(b) * static_cast<size_t>(n_);
      std::copy(start, start + n_, rhs.begin());
      for (int mom = 0; mom < moments && m_ < cap; ++mom) {
        if (mom > 0) {
          const double* vlast =
              V_.data() + static_cast<size_t>(m_ - 1) * static_cast<size_t>(n_);
          for (Index i = 0; i < n_; ++i) {
            rhs[i] = C_[i] * vlast[i];
          }
        }
        lu->solve(rhs.data(), x.data(), nullptr);
        if (!mgs_append(V_, m_, n_, x, 1e-14)) {
          break;
        }
      }
    }
  }
  if (m_ == 0) {
    // Fallback: DC solve of ones, or the first start vector.
    std::fill(rhs.begin(), rhs.end(), 1.0);
    auto lu = make_direct(G_);
    lu->solve(rhs.data(), x.data(), nullptr);
    if (!mgs_append(V_, m_, n_, x, 1e-14)) {
      std::fill(x.begin(), x.end(), 1.0 / std::sqrt(static_cast<double>(n_)));
      mgs_append(V_, m_, n_, x, 1e-30);
    }
  }

  Gr_.assign(static_cast<size_t>(m_ * m_), 0.0);
  Cr_.assign(static_cast<size_t>(m_ * m_), 0.0);
  std::vector<double> gv(static_cast<size_t>(n_));
  for (int k = 0; k < m_; ++k) {
    const double* vk = V_.data() + static_cast<size_t>(k) * static_cast<size_t>(n_);
    G_.spmv(vk, gv.data());
    for (int j = 0; j < m_; ++j) {
      const double* vj = V_.data() + static_cast<size_t>(j) * static_cast<size_t>(n_);
      Gr_[j * m_ + k] = dot(vj, gv.data(), n_);
      double cjk = 0.0;
      for (Index i = 0; i < n_; ++i) {
        cjk += vj[i] * C_[i] * vk[i];
      }
      Cr_[j * m_ + k] = cjk;
    }
  }
  setup_s_ = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
}

TranResult RationalMor::timestep(const double* leak, const double* pad, double dt, double t_end,
                                 double vdd, const TriangleSrc* ev, int n_ev) const {
  TranResult out;
  out.worst_v = vdd;
  out.V_worst.assign(static_cast<size_t>(n_), vdd);
  if (m_ <= 0 || dt <= 0.0) {
    return out;
  }
  Eigen::MatrixXd Gr(m_, m_), Cr(m_, m_), Ar(m_, m_);
  for (int i = 0; i < m_; ++i) {
    for (int j = 0; j < m_; ++j) {
      Gr(i, j) = Gr_[i * m_ + j];
      Cr(i, j) = Cr_[i * m_ + j];
    }
  }
  Ar = Gr + Cr / dt;
  Eigen::LDLT<Eigen::MatrixXd> ldlt(Ar);
  if (ldlt.info() != Eigen::Success) {
    throw std::runtime_error("reduced BE LDLT failed");
  }

  const int steps = std::max(2, static_cast<int>(std::ceil(t_end / dt)));
  Eigen::VectorXd z = Eigen::VectorXd::Zero(m_);
  Eigen::VectorXd znext(m_), rhs(m_), f(m_);
  std::vector<double> I(static_cast<size_t>(n_));
  std::vector<double> V(static_cast<size_t>(n_));
  std::vector<double> gv(static_cast<size_t>(n_));
  double res_max = 0.0;
  const auto t0 = std::chrono::steady_clock::now();

  auto reconstruct = [&](const Eigen::VectorXd& zk) {
    std::fill(V.begin(), V.end(), vdd);
    for (int k = 0; k < m_; ++k) {
      const double* vk = V_.data() + static_cast<size_t>(k) * static_cast<size_t>(n_);
      axpy(zk[k], vk, V.data(), n_);
    }
  };

  for (int s = 0; s < steps; ++s) {
    const double t = static_cast<double>(s) * dt;
    fill_idraw(n_, t, leak, ev, n_ev, I.data());
    f.setZero();
    for (int k = 0; k < m_; ++k) {
      const double* vk = V_.data() + static_cast<size_t>(k) * static_cast<size_t>(n_);
      f[k] = dot(vk, I.data(), n_);
    }
    rhs = (Cr * z) / dt - f;
    znext = ldlt.solve(rhs);

    reconstruct(znext);
    // DAE residual of C dv/dt + G v - pad + I on the reconstructed trajectory.
    std::vector<double> Vprev(static_cast<size_t>(n_), vdd);
    if (s > 0) {
      std::fill(Vprev.begin(), Vprev.end(), vdd);
      for (int k = 0; k < m_; ++k) {
        const double* vk = V_.data() + static_cast<size_t>(k) * static_cast<size_t>(n_);
        axpy(z[k], vk, Vprev.data(), n_);
      }
    }
    G_.spmv(V.data(), gv.data());
    double nr = 0.0, nb = 0.0;
    for (Index i = 0; i < n_; ++i) {
      const double r = C_[i] * (V[i] - Vprev[i]) / dt + gv[i] - pad[i] + I[i];
      nr += r * r;
      nb += I[i] * I[i];
    }
    const double rel = (nb < 1e-30) ? std::sqrt(nr) : std::sqrt(nr / nb);
    res_max = std::max(res_max, rel);

    z = znext;
    double vmin = V[0];
    Index imin = 0;
    double itot = 0.0;
    for (Index i = 0; i < n_; ++i) {
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

}  // namespace dpn
