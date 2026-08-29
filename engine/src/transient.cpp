#include "dpn/transient.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <memory>
#include <vector>

namespace dpn {

double triangle(double t, double t50, double dur, double ipulse) {
  if (dur <= 0.0 || ipulse <= 0.0) {
    return 0.0;
  }
  const double half = 0.5 * dur;
  const double tau = t - t50;
  if (std::abs(tau) >= half) {
    return 0.0;
  }
  return ipulse * (1.0 - std::abs(tau) / half);
}

void fill_idraw(Index n, double t, const double* leak, const TriangleSrc* ev, int n_ev, double* I) {
  if (leak) {
    std::copy(leak, leak + n, I);
  } else {
    std::fill(I, I + n, 0.0);
  }
  for (int e = 0; e < n_ev; ++e) {
    const Index i = ev[e].idx;
    if (i < 0 || i >= n) {
      continue;
    }
    I[i] += triangle(t, ev[e].t50, ev[e].dur, ev[e].ipulse);
  }
}

namespace {

void record_step(TranResult& out, double t, const double* V, const double* I, Index n, double vdd) {
  double vmin = V[0];
  Index imin = 0;
  double itot = 0.0;
  for (Index i = 0; i < n; ++i) {
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
    out.V_worst.assign(V, V + n);
  }
  (void)vdd;
}

}  // namespace

TranResult timestep_be(Solver& solver, const Csr& A, const double* C, const double* leak,
                       const double* pad, double dt, double t_end, double vdd,
                       const TriangleSrc* ev, int n_ev) {
  const Index n = solver.n();
  TranResult out;
  out.worst_v = vdd;
  out.worst_t = 0.0;
  out.V_worst.assign(static_cast<size_t>(n), vdd);
  if (n <= 0 || dt <= 0.0) {
    return out;
  }
  const int steps = std::max(2, static_cast<int>(std::ceil(t_end / dt)));
  std::vector<double> V(static_cast<size_t>(n), vdd);
  std::vector<double> rhs(static_cast<size_t>(n));
  std::vector<double> I(static_cast<size_t>(n));
  std::vector<double> Vnext(static_cast<size_t>(n));
  double res_max = 0.0;
  double t_solve = 0.0;
  for (int s = 0; s < steps; ++s) {
    const double t = static_cast<double>(s) * dt;
    fill_idraw(n, t, leak, ev, n_ev, I.data());
    for (Index i = 0; i < n; ++i) {
      rhs[i] = (C[i] / dt) * V[i] - I[i] + pad[i];
    }
    const auto t0 = std::chrono::steady_clock::now();
    solver.solve(rhs.data(), Vnext.data(), V.data());
    t_solve += std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    res_max = std::max(res_max, residual_rel(A, Vnext.data(), rhs.data()));
    V.swap(Vnext);
    record_step(out, t, V.data(), I.data(), n, vdd);
  }
  out.steps = steps;
  out.rel_res_max = res_max;
  out.solve_s = t_solve;
  return out;
}

Csr form_be_operator(const Csr& Gmesh, const double* C, double dt, const Index* bumps, int n_bumps,
                     double pkg_r, double pkg_l, std::vector<double>& pad, double vdd,
                     double dt_pkg) {
  const Index n = Gmesh.nrows;
  const double dt_l = dt_pkg > 0.0 ? dt_pkg : dt;
  const double r_series = std::max(pkg_r + (pkg_l > 0.0 ? pkg_l / dt_l : 0.0), 1e-9);
  const double g_pad = 1.0 / r_series;
  std::vector<double> d(static_cast<size_t>(n));
  pad.assign(static_cast<size_t>(n), 0.0);
  for (Index i = 0; i < n; ++i) {
    d[i] = C[i] / dt;
  }
  for (int k = 0; k < n_bumps; ++k) {
    const Index b = bumps[k];
    if (b < 0 || b >= n) {
      continue;
    }
    d[b] += g_pad;
    pad[b] = g_pad * vdd;
  }
  return plus_diag(Gmesh, d.data());
}

TranResult timestep_be_adaptive(const Csr& Gmesh, const double* C, const Index* bumps, int n_bumps,
                                double pkg_r, double pkg_l, double vdd, const double* leak,
                                double dt0, double t_end, double atol, double rtol,
                                const TriangleSrc* ev, int n_ev) {
  const Index n = Gmesh.nrows;
  TranResult out;
  out.worst_v = vdd;
  out.V_worst.assign(static_cast<size_t>(n), vdd);
  if (n <= 0 || dt0 <= 0.0 || t_end <= 0.0) {
    return out;
  }
  const double dt_min = dt0 / 128.0;
  const double dt_max = dt0 * 8.0;
  double dt = dt0;
  double t = 0.0;
  std::vector<double> V(static_cast<size_t>(n), vdd);
  std::vector<double> Vprev(static_cast<size_t>(n), vdd);
  std::vector<double> Vnext(static_cast<size_t>(n));
  std::vector<double> rhs(static_cast<size_t>(n));
  std::vector<double> I(static_cast<size_t>(n));
  std::vector<double> pad;
  int have_prev = 0;
  double last_dt = -1.0;
  std::unique_ptr<Solver> solver;
  Csr A;
  double t_solve = 0.0;
  double res_max = 0.0;
  const int cap = std::max(4, static_cast<int>(std::ceil(t_end / dt_min)) + 4);
  int accepted = 0;

  auto refactor = [&](double dtc) {
    if (std::abs(dtc - last_dt) < 1e-18 * std::max(dtc, 1e-18) && solver) {
      return;
    }
    A = form_be_operator(Gmesh, C, dtc, bumps, n_bumps, pkg_r, pkg_l, pad, vdd, dt0);
    solver = make_direct(A);
    last_dt = dtc;
  };

  while (t < t_end - 1e-18 * t_end && accepted < cap) {
    const double dt_use = std::min(dt, t_end - t);
    refactor(dt_use);
    fill_idraw(n, t, leak, ev, n_ev, I.data());
    for (Index i = 0; i < n; ++i) {
      rhs[i] = (C[i] / dt_use) * V[i] - I[i] + pad[i];
    }
    const auto t0 = std::chrono::steady_clock::now();
    solver->solve(rhs.data(), Vnext.data(), V.data());
    t_solve += std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    res_max = std::max(res_max, residual_rel(A, Vnext.data(), rhs.data()));

    bool accept = true;
    if (have_prev && atol > 0.0) {
      double err = 0.0;
      for (Index i = 0; i < n; ++i) {
        const double lte = 0.5 * std::abs(Vnext[i] - 2.0 * V[i] + Vprev[i]);
        const double tol = atol + rtol * std::abs(Vnext[i]);
        err = std::max(err, lte / std::max(tol, 1e-18));
      }
      if (err > 1.0 && dt_use > dt_min * 1.01) {
        accept = false;
        dt = std::max(dt_use * 0.5, dt_min);
      } else if (err < 0.125) {
        dt = std::min(dt_use * 1.5, dt_max);
      }
    }
    if (!accept) {
      continue;
    }
    Vprev.swap(V);
    V.swap(Vnext);
    have_prev = 1;
    record_step(out, t, V.data(), I.data(), n, vdd);
    t += dt_use;
    ++accepted;
  }
  out.steps = accepted;
  out.rel_res_max = res_max;
  out.solve_s = t_solve;
  return out;
}

}  // namespace dpn
