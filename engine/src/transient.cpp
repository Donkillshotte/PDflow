#include "dpn/transient.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <memory>
#include <stdexcept>
#include <vector>

namespace dpn {

double triangle(double t, double t50, double dur, double ipulse) {
  if (dur <= 0.0 || ipulse == 0.0) {
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

void cap_over_dt(Index n, const double* C, const Csr* Cmat, const double* V, double dt, double* out) {
  const double inv_dt = 1.0 / dt;
  if (Cmat != nullptr && Cmat->nrows == n && Cmat->nnz() > 0) {
    Cmat->spmv(V, out);
    for (Index i = 0; i < n; ++i) {
      out[i] *= inv_dt;
    }
    return;
  }
  for (Index i = 0; i < n; ++i) {
    out[i] = (C[i] * inv_dt) * V[i];
  }
}

void record_step(TranResult& out, double t, const double* V, const double* I, Index n, double vdd,
                 Index n_rail0) {
  const Index n0 = (n_rail0 > 0 && n_rail0 < n) ? n_rail0 : n;
  double vmin = V[0];
  Index imin = 0;
  double itot = 0.0;
  for (Index i = 0; i < n0; ++i) {
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
  if (n_rail0 > 0 && n_rail0 < n) {
    double vmax = V[n_rail0];
    Index imax = n_rail0;
    for (Index i = n_rail0 + 1; i < n; ++i) {
      if (V[i] > vmax) {
        vmax = V[i];
        imax = i;
      }
    }
    if (out.V_worst_rail1.empty() || vmax > out.worst_v_rail1) {
      out.worst_v_rail1 = vmax;
      out.worst_t_rail1 = t;
      out.worst_node_rail1 = imax;
      out.V_worst_rail1.assign(V, V + n);
    }
  }
  (void)vdd;
}

std::unique_ptr<Solver> descriptor_solver(const Csr& K, int kind) {
  if (kind == 1) {
    throw std::runtime_error("AMG is SPD-companion only; descriptor K is unsymmetric");
  }
  if (kind == 2) {
    return make_ras(K);
  }
  if (kind == 3) {
    return make_bicgstab(K);
  }
  return make_direct(K);
}

void stamp_descriptor_u(Index n, int n_die, Index die_idx, const Index* iv, int n_iv, double vdd,
                        const double* leak, const double* u_const, const TriangleSrc* ev, int n_ev,
                        double t, double* rhs, double* I) {
  const Index n_die_i = std::max(static_cast<Index>(n_die), Index{0});
  fill_idraw(n_die_i > 0 ? n_die_i : 1, t, leak, ev, n_ev, I);
  std::fill(rhs, rhs + n, 0.0);
  if (die_idx >= 0 && die_idx < n) {
    rhs[static_cast<size_t>(die_idx)] = -I[0];
  } else {
    const Index nd = std::min(n_die_i, n);
    for (Index i = 0; i < nd; ++i) {
      rhs[static_cast<size_t>(i)] = -I[static_cast<size_t>(i)];
    }
  }
  if (u_const) {
    for (Index i = 0; i < n; ++i) {
      rhs[i] += u_const[i];
    }
  }
  if (iv && n_iv > 0) {
    for (int k = 0; k < n_iv; ++k) {
      const Index j = iv[k];
      if (j >= 0 && j < n) {
        rhs[static_cast<size_t>(j)] += vdd;
      }
    }
  }
}

void track_descriptor_vmin(TranResult& out, const std::vector<double>& x, Index n, int n_die,
                           Index die_idx, double t, const double* I, double vdd) {
  const Index n_die_i = std::max(static_cast<Index>(n_die), Index{0});
  double vmin = vdd;
  Index imin = 0;
  if (die_idx >= 0 && die_idx < n) {
    vmin = x[static_cast<size_t>(die_idx)];
    imin = 0;
  } else {
    const Index nd = std::min(n_die_i, n);
    vmin = x[0];
    for (Index i = 1; i < nd; ++i) {
      if (x[static_cast<size_t>(i)] < vmin) {
        vmin = x[static_cast<size_t>(i)];
        imin = i;
      }
    }
  }
  out.wave_t.push_back(t);
  out.wave_vmin.push_back(vmin);
  double itot = 0.0;
  const Index ndi = n_die_i > 0 ? n_die_i : 1;
  for (Index i = 0; i < ndi; ++i) {
    itot += I[i];
  }
  out.wave_itot.push_back(itot);
  if (vmin < out.worst_v) {
    out.worst_v = vmin;
    out.worst_t = t;
    out.worst_node = imin;
    if (die_idx >= 0) {
      out.V_worst.assign(1, vmin);
    } else {
      const Index nd = std::min(n_die_i, n);
      out.V_worst.assign(x.begin(), x.begin() + nd);
    }
  }
}

}  // namespace

TranResult timestep_be(Solver& solver, const Csr& A, const double* C, const double* leak,
                       const double* pad, double dt, double t_end, double vdd,
                       const TriangleSrc* ev, int n_ev, const Csr* Cmat, const double* v_init,
                       Index n_rail0) {
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
  if (v_init) {
    std::copy(v_init, v_init + n, V.begin());
    out.V_worst.assign(v_init, v_init + n);
    const Index n0 = (n_rail0 > 0 && n_rail0 < n) ? n_rail0 : n;
    out.worst_v = V[0];
    for (Index i = 1; i < n0; ++i) {
      out.worst_v = std::min(out.worst_v, V[i]);
    }
  }
  std::vector<double> rhs(static_cast<size_t>(n));
  std::vector<double> I(static_cast<size_t>(n));
  std::vector<double> Vnext(static_cast<size_t>(n));
  double res_max = 0.0;
  double t_solve = 0.0;
  for (int s = 0; s < steps; ++s) {
    const double t = static_cast<double>(s) * dt;
    fill_idraw(n, t, leak, ev, n_ev, I.data());
    cap_over_dt(n, C, Cmat, V.data(), dt, rhs.data());
    for (Index i = 0; i < n; ++i) {
      rhs[i] += -I[i] + pad[i];
    }
    const auto t0 = std::chrono::steady_clock::now();
    solver.solve(rhs.data(), Vnext.data(), V.data());
    t_solve += std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    res_max = std::max(res_max, residual_rel(A, Vnext.data(), rhs.data()));
    V.swap(Vnext);
    record_step(out, t, V.data(), I.data(), n, vdd, n_rail0);
  }
  out.steps = steps;
  out.rel_res_max = res_max;
  out.solve_s = t_solve;
  return out;
}

void rl_companion(double pkg_r, double pkg_l, double dt, double* g_eq, double* hist_scale) {
  const double Ldt = (pkg_l > 0.0 && dt > 0.0) ? (pkg_l / dt) : 0.0;
  const double req = std::max(pkg_r + Ldt, 1e-9);
  const double g = 1.0 / req;
  if (g_eq) {
    *g_eq = g;
  }
  if (hist_scale) {
    *hist_scale = g * Ldt;
  }
}

Csr form_be_operator(const Csr& Gmesh, const double* C, double dt, const Index* bumps, int n_bumps,
                     const double* bump_v, double pkg_r, double pkg_l, std::vector<double>& pad) {
  const Index n = Gmesh.nrows;
  double g_eq = 0.0, hist = 0.0;
  rl_companion(pkg_r, pkg_l, dt, &g_eq, &hist);
  (void)hist;
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
    d[b] += g_eq;
    const double vs = bump_v ? bump_v[k] : 0.0;
    pad[b] = g_eq * vs;
  }
  return plus_diag(Gmesh, d.data());
}

TranResult timestep_be_hist(Solver& solver, const Csr& A, const double* C, const double* leak,
                            double dt, double t_end, const TriangleSrc* ev, int n_ev,
                            const Index* bumps, int n_bumps, const double* bump_v, double pkg_r,
                            double pkg_l, const Csr* Cmat, const double* v_init, Index n_rail0) {
  const Index n = solver.n();
  double vref = 0.0;
  for (int k = 0; k < n_bumps; ++k) {
    vref = std::max(vref, bump_v ? bump_v[k] : 0.0);
  }
  TranResult out;
  out.worst_v = vref;
  out.V_worst.assign(static_cast<size_t>(n), vref);
  out.i_L_worst.assign(static_cast<size_t>(std::max(n_bumps, 0)), 0.0);
  if (n <= 0 || dt <= 0.0) {
    return out;
  }
  double g_eq = 0.0, hsc = 0.0;
  rl_companion(pkg_r, pkg_l, dt, &g_eq, &hsc);
  const int steps = std::max(2, static_cast<int>(std::ceil(t_end / dt)));
  std::vector<double> V(static_cast<size_t>(n), vref);
  if (v_init) {
    std::copy(v_init, v_init + n, V.begin());
    out.V_worst.assign(v_init, v_init + n);
    const Index n0 = (n_rail0 > 0 && n_rail0 < n) ? n_rail0 : n;
    out.worst_v = V[0];
    for (Index i = 1; i < n0; ++i) {
      out.worst_v = std::min(out.worst_v, V[i]);
    }
  }
  std::vector<double> rhs(static_cast<size_t>(n));
  std::vector<double> I(static_cast<size_t>(n));
  std::vector<double> Vnext(static_cast<size_t>(n));
  std::vector<double> i_L(static_cast<size_t>(std::max(n_bumps, 0)), 0.0);
  double res_max = 0.0;
  double t_solve = 0.0;
  for (int s = 0; s < steps; ++s) {
    const double t = static_cast<double>(s) * dt;
    fill_idraw(n, t, leak, ev, n_ev, I.data());
    cap_over_dt(n, C, Cmat, V.data(), dt, rhs.data());
    for (Index i = 0; i < n; ++i) {
      rhs[i] -= I[i];
    }
    for (int k = 0; k < n_bumps; ++k) {
      const Index b = bumps[k];
      if (b < 0 || b >= n) {
        continue;
      }
      const double vs = bump_v ? bump_v[k] : 0.0;
      rhs[b] += g_eq * vs + hsc * i_L[k];
    }
    const auto t0 = std::chrono::steady_clock::now();
    solver.solve(rhs.data(), Vnext.data(), V.data());
    t_solve += std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    res_max = std::max(res_max, residual_rel(A, Vnext.data(), rhs.data()));
    std::vector<double> i_new(i_L.size(), 0.0);
    double iabs = 0.0;
    for (int k = 0; k < n_bumps; ++k) {
      const Index b = bumps[k];
      const double vs = bump_v ? bump_v[k] : 0.0;
      const double vn = (b >= 0 && b < n) ? Vnext[b] : vs;
      i_new[k] = g_eq * (vs - vn) + hsc * i_L[k];
      iabs = std::max(iabs, std::abs(i_new[k]));
    }
    i_L.swap(i_new);
    V.swap(Vnext);
    record_step(out, t, V.data(), I.data(), n, vref, n_rail0);
    if (out.worst_t == t) {
      out.i_L_worst = i_L;
      out.i_L_absmax = iabs;
    }
  }
  out.steps = steps;
  out.rel_res_max = res_max;
  out.solve_s = t_solve;
  return out;
}

TranResult timestep_be_adaptive(const Csr& Gmesh, const double* C, const Index* bumps, int n_bumps,
                                const double* bump_v, double pkg_r, double pkg_l, double vdd,
                                const double* leak, double dt0, double t_end, double atol,
                                double rtol, const TriangleSrc* ev, int n_ev) {
  const Index n = Gmesh.nrows;
  double vref = vdd;
  for (int k = 0; k < n_bumps; ++k) {
    vref = std::max(vref, bump_v ? bump_v[k] : 0.0);
  }
  TranResult out;
  out.worst_v = vref;
  out.V_worst.assign(static_cast<size_t>(n), vref);
  out.i_L_worst.assign(static_cast<size_t>(std::max(n_bumps, 0)), 0.0);
  if (n <= 0 || dt0 <= 0.0 || t_end <= 0.0) {
    return out;
  }
  const double dt_min = dt0 / 128.0;
  const double dt_max = dt0 * 8.0;
  double dt = dt0;
  double t = 0.0;
  std::vector<double> V(static_cast<size_t>(n), vref);
  std::vector<double> Vprev(static_cast<size_t>(n), vref);
  std::vector<double> Vnext(static_cast<size_t>(n));
  std::vector<double> rhs(static_cast<size_t>(n));
  std::vector<double> I(static_cast<size_t>(n));
  std::vector<double> i_L(static_cast<size_t>(std::max(n_bumps, 0)), 0.0);
  std::vector<double> pad;
  int have_prev = 0;
  double last_dt = -1.0;
  double g_eq = 0.0, hsc = 0.0;
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
    A = form_be_operator(Gmesh, C, dtc, bumps, n_bumps, bump_v, pkg_r, pkg_l, pad);
    rl_companion(pkg_r, pkg_l, dtc, &g_eq, &hsc);
    solver = make_direct(A);
    last_dt = dtc;
  };

  while (t < t_end - 1e-18 * t_end && accepted < cap) {
    const double dt_use = std::min(dt, t_end - t);
    refactor(dt_use);
    fill_idraw(n, t, leak, ev, n_ev, I.data());
    for (Index i = 0; i < n; ++i) {
      rhs[i] = (C[i] / dt_use) * V[i] - I[i];
    }
    for (int k = 0; k < n_bumps; ++k) {
      const Index b = bumps[k];
      if (b < 0 || b >= n) {
        continue;
      }
      const double vs = bump_v ? bump_v[k] : vdd;
      rhs[b] += g_eq * vs + hsc * i_L[k];
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
    std::vector<double> i_new(i_L.size(), 0.0);
    double iabs = 0.0;
    for (int k = 0; k < n_bumps; ++k) {
      const Index b = bumps[k];
      const double vs = bump_v ? bump_v[k] : vdd;
      const double vn = (b >= 0 && b < n) ? Vnext[b] : vs;
      i_new[k] = g_eq * (vs - vn) + hsc * i_L[k];
      iabs = std::max(iabs, std::abs(i_new[k]));
    }
    i_L.swap(i_new);
    Vprev.swap(V);
    V.swap(Vnext);
    have_prev = 1;
    record_step(out, t, V.data(), I.data(), n, vref, 0);
    if (out.worst_t == t) {
      out.i_L_worst = i_L;
      out.i_L_absmax = iabs;
    }
    t += dt_use;
    ++accepted;
  }
  out.steps = accepted;
  out.rel_res_max = res_max;
  out.solve_s = t_solve;
  return out;
}

TranResult timestep_descriptor_gen(const Csr& A, const Csr& E, double dt, double t_end, double vdd,
                                   int n_v, int n_die, Index die_idx, const Index* iv, int n_iv,
                                   const double* leak, const double* u_const, const TriangleSrc* ev,
                                   int n_ev, int solver_kind) {
  TranResult out;
  const Index n = A.nrows;
  out.worst_v = vdd;
  out.worst_t = 0.0;
  const Index n_die_i = std::max(static_cast<Index>(n_die), Index{0});
  out.V_worst.assign(static_cast<size_t>(n_die_i > 0 ? n_die_i : n), vdd);
  if (n <= 0 || dt <= 0.0 || n_v <= 0 || E.nrows != n || E.ncols != n) {
    return out;
  }
  Csr Edt = scale(E, 1.0 / dt);
  Csr K = plus(A, Edt);
  auto solver = descriptor_solver(K, solver_kind);
  const int steps = std::max(2, static_cast<int>(std::ceil(t_end / dt)));
  std::vector<double> x(static_cast<size_t>(n), 0.0);
  for (int i = 0; i < n_v && static_cast<Index>(i) < n; ++i) {
    x[static_cast<size_t>(i)] = vdd;
  }
  std::vector<double> rhs(static_cast<size_t>(n)), I(static_cast<size_t>(std::max(n_die_i, Index{1})));
  const auto t0 = std::chrono::steady_clock::now();
  double res_max = 0.0;
  for (int s = 0; s < steps; ++s) {
    const double t = static_cast<double>(s) * dt;
    stamp_descriptor_u(n, n_die, die_idx, iv, n_iv, vdd, leak, u_const, ev, n_ev, t, rhs.data(),
                       I.data());
    std::vector<double> hist(static_cast<size_t>(n), 0.0);
    Edt.spmv(x.data(), hist.data());
    for (Index i = 0; i < n; ++i) {
      rhs[static_cast<size_t>(i)] += hist[static_cast<size_t>(i)];
    }
    std::vector<double> xnext(static_cast<size_t>(n));
    solver->solve(rhs.data(), xnext.data(), x.data());
    res_max = std::max(res_max, residual_rel(K, xnext.data(), rhs.data()));
    x.swap(xnext);
    track_descriptor_vmin(out, x, n, n_die, die_idx, t, I.data(), vdd);
  }
  out.steps = steps;
  out.rel_res_max = res_max;
  out.solve_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  return out;
}

TranResult timestep_descriptor_adaptive(const Csr& A, const Csr& E, double dt0, double t_end,
                                        double vdd, int n_v, int n_die, Index die_idx,
                                        const Index* iv, int n_iv, const double* leak,
                                        const double* u_const, double atol, double rtol,
                                        const TriangleSrc* ev, int n_ev, int solver_kind) {
  TranResult out;
  const Index n = A.nrows;
  out.worst_v = vdd;
  out.worst_t = 0.0;
  const Index n_die_i = std::max(static_cast<Index>(n_die), Index{0});
  out.V_worst.assign(static_cast<size_t>(n_die_i > 0 ? n_die_i : n), vdd);
  if (n <= 0 || dt0 <= 0.0 || t_end <= 0.0 || n_v <= 0 || E.nrows != n || E.ncols != n) {
    return out;
  }
  const double dt_min = dt0 / 128.0;
  const double dt_max = dt0 * 8.0;
  double dt = dt0;
  double t = 0.0;
  std::vector<double> x(static_cast<size_t>(n), 0.0);
  std::vector<double> xprev(static_cast<size_t>(n), 0.0);
  std::vector<double> xnext(static_cast<size_t>(n));
  for (int i = 0; i < n_v && static_cast<Index>(i) < n; ++i) {
    x[static_cast<size_t>(i)] = vdd;
    xprev[static_cast<size_t>(i)] = vdd;
  }
  std::vector<double> rhs(static_cast<size_t>(n));
  std::vector<double> I(static_cast<size_t>(std::max(n_die_i, Index{1})));
  std::unique_ptr<Solver> solver;
  Csr K;
  Csr Edt;
  double last_dt = -1.0;
  int have_prev = 0;
  double t_solve = 0.0;
  double res_max = 0.0;
  const int cap = std::max(4, static_cast<int>(std::ceil(t_end / dt_min)) + 4);
  int accepted = 0;

  auto refactor = [&](double dtc) {
    if (std::abs(dtc - last_dt) < 1e-18 * std::max(dtc, 1e-18) && solver) {
      return;
    }
    Edt = scale(E, 1.0 / dtc);
    K = plus(A, Edt);
    solver = descriptor_solver(K, solver_kind);
    last_dt = dtc;
  };

  while (t < t_end - 1e-18 * t_end && accepted < cap) {
    const double dt_use = std::min(dt, t_end - t);
    refactor(dt_use);
    stamp_descriptor_u(n, n_die, die_idx, iv, n_iv, vdd, leak, u_const, ev, n_ev, t, rhs.data(),
                       I.data());
    std::vector<double> hist(static_cast<size_t>(n), 0.0);
    Edt.spmv(x.data(), hist.data());
    for (Index i = 0; i < n; ++i) {
      rhs[i] += hist[i];
    }
    const auto t0 = std::chrono::steady_clock::now();
    solver->solve(rhs.data(), xnext.data(), x.data());
    t_solve += std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    res_max = std::max(res_max, residual_rel(K, xnext.data(), rhs.data()));

    bool accept = true;
    if (have_prev && atol > 0.0) {
      double err = 0.0;
      const Index nv = std::min(static_cast<Index>(n_v), n);
      for (Index i = 0; i < nv; ++i) {
        const double lte = 0.5 * std::abs(xnext[i] - 2.0 * x[i] + xprev[i]);
        const double tol = atol + rtol * std::abs(xnext[i]);
        err = std::max(err, lte / std::max(tol, 1e-18));
      }
      if (err > 1.0 && dt_use > dt_min * 1.01) {
        accept = false;
        dt = std::max(dt_use * 0.5, dt_min);
      } else if (err < 0.25) {
        dt = std::min(dt_use * 1.5, dt_max);
      }
    }
    if (!accept) {
      continue;
    }
    xprev.swap(x);
    x.swap(xnext);
    have_prev = 1;
    track_descriptor_vmin(out, x, n, n_die, die_idx, t, I.data(), vdd);
    t += dt_use;
    ++accepted;
  }
  out.steps = accepted;
  out.rel_res_max = res_max;
  out.solve_s = t_solve;
  return out;
}

TranResult timestep_descriptor(const Csr& A, const double* E, double dt, double t_end, double vdd,
                               int n_v, int n_die, Index die_idx, int iv, const double* leak,
                               const TriangleSrc* ev, int n_ev) {
  if (!E || A.nrows <= 0) {
    TranResult out;
    out.worst_v = vdd;
    return out;
  }
  Csr Ed = diag_csr(A.nrows, E);
  const Index iv_i = static_cast<Index>(iv);
  const int n_iv = (iv >= 0) ? 1 : 0;
  return timestep_descriptor_gen(A, Ed, dt, t_end, vdd, n_v, n_die, die_idx, n_iv ? &iv_i : nullptr,
                                 n_iv, leak, nullptr, ev, n_ev, 0);
}

ThermalTranResult timestep_thermal_be(Solver& solver, const Csr& A, const double* C, const double* P,
                                      double dt, double t_end, const double* T0, Index n_track) {
  const Index n = solver.n();
  ThermalTranResult out;
  if (n <= 0 || dt <= 0.0 || !C || !P) {
    return out;
  }
  const Index n0 = (n_track > 0 && n_track <= n) ? n_track : n;
  std::vector<double> T(static_cast<size_t>(n), 0.0);
  if (T0) {
    std::copy(T0, T0 + n, T.begin());
  }
  out.worst_T = T[0];
  out.worst_node = 0;
  for (Index i = 1; i < n0; ++i) {
    if (T[static_cast<size_t>(i)] > out.worst_T) {
      out.worst_T = T[static_cast<size_t>(i)];
      out.worst_node = i;
    }
  }
  out.T_worst = T;
  const int steps = std::max(2, static_cast<int>(std::ceil(t_end / dt)));
  std::vector<double> rhs(static_cast<size_t>(n));
  std::vector<double> Tnext(static_cast<size_t>(n));
  const double inv_dt = 1.0 / dt;
  double res_max = 0.0;
  double t_solve = 0.0;
  for (int s = 0; s < steps; ++s) {
    const double t = static_cast<double>(s) * dt;
    for (Index i = 0; i < n; ++i) {
      rhs[static_cast<size_t>(i)] = (C[i] * inv_dt) * T[static_cast<size_t>(i)] + P[i];
    }
    const auto t0s = std::chrono::steady_clock::now();
    solver.solve(rhs.data(), Tnext.data(), T.data());
    t_solve += std::chrono::duration<double>(std::chrono::steady_clock::now() - t0s).count();
    res_max = std::max(res_max, residual_rel(A, Tnext.data(), rhs.data()));
    T.swap(Tnext);
    double tmax = T[0];
    Index imax = 0;
    for (Index i = 1; i < n0; ++i) {
      if (T[static_cast<size_t>(i)] > tmax) {
        tmax = T[static_cast<size_t>(i)];
        imax = i;
      }
    }
    out.wave_t.push_back(t);
    out.wave_tmax.push_back(tmax);
    if (tmax > out.worst_T) {
      out.worst_T = tmax;
      out.worst_t = t;
      out.worst_node = imax;
      out.T_worst = T;
    }
  }
  out.steps = steps;
  out.rel_res_max = res_max;
  out.solve_s = t_solve;
  out.T_final = T;
  return out;
}

}  // namespace dpn
