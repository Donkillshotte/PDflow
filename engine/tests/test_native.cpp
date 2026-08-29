#include "dpn/c_api.h"
#include "dpn/csr.hpp"
#include "dpn/mor.hpp"
#include "dpn/solvers.hpp"
#include "dpn/transient.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

using dpn::Csr;
using dpn::Index;

static Csr poisson_1d(Index n) {
  Csr A;
  A.nrows = n;
  A.ncols = n;
  A.rowptr.resize(n + 1);
  A.rowptr[0] = 0;
  for (Index i = 0; i < n; ++i) {
    int row_n = 1;
    if (i > 0) {
      ++row_n;
    }
    if (i + 1 < n) {
      ++row_n;
    }
    A.rowptr[i + 1] = A.rowptr[i] + row_n;
  }
  A.col.resize(A.rowptr[n]);
  A.val.resize(A.rowptr[n]);
  for (Index i = 0; i < n; ++i) {
    Index k = A.rowptr[i];
    if (i > 0) {
      A.col[k] = i - 1;
      A.val[k++] = -1.0;
    }
    A.col[k] = i;
    A.val[k++] = 2.0;
    if (i + 1 < n) {
      A.col[k] = i + 1;
      A.val[k++] = -1.0;
    }
  }
  return A;
}

static Csr r_chain(Index n, double r) {
  const double g = 1.0 / r;
  Csr A;
  A.nrows = n;
  A.ncols = n;
  A.rowptr.resize(n + 1);
  A.rowptr[0] = 0;
  for (Index i = 0; i < n; ++i) {
    int row_n = 1;
    if (i > 0) {
      ++row_n;
    }
    if (i + 1 < n) {
      ++row_n;
    }
    A.rowptr[i + 1] = A.rowptr[i] + row_n;
  }
  A.col.resize(A.rowptr[n]);
  A.val.resize(A.rowptr[n]);
  for (Index i = 0; i < n; ++i) {
    Index k = A.rowptr[i];
    double diag = 0.0;
    if (i > 0) {
      A.col[k] = i - 1;
      A.val[k++] = -g;
      diag += g;
    }
    const Index dpos = k;
    A.col[k] = i;
    A.val[k++] = 0.0;
    if (i + 1 < n) {
      A.col[k] = i + 1;
      A.val[k++] = -g;
      diag += g;
    }
    A.val[dpos] = diag;
  }
  return A;
}

static void ge4(double A[4][4], const double b[4], double x[4]) {
  double M[4][4];
  double rhs[4];
  for (int i = 0; i < 4; ++i) {
    rhs[i] = b[i];
    for (int j = 0; j < 4; ++j) {
      M[i][j] = A[i][j];
    }
  }
  for (int k = 0; k < 4; ++k) {
    int piv = k;
    for (int i = k + 1; i < 4; ++i) {
      if (std::abs(M[i][k]) > std::abs(M[piv][k])) {
        piv = i;
      }
    }
    for (int j = 0; j < 4; ++j) {
      std::swap(M[k][j], M[piv][j]);
    }
    std::swap(rhs[k], rhs[piv]);
    const double akk = M[k][k];
    for (int i = k + 1; i < 4; ++i) {
      const double f = M[i][k] / akk;
      for (int j = k; j < 4; ++j) {
        M[i][j] -= f * M[k][j];
      }
      rhs[i] -= f * rhs[k];
    }
  }
  for (int i = 3; i >= 0; --i) {
    double s = rhs[i];
    for (int j = i + 1; j < 4; ++j) {
      s -= M[i][j] * x[j];
    }
    x[i] = s / M[i][i];
  }
}

static Csr poisson_2d(Index m) {
  const Index n = m * m;
  Csr A;
  A.nrows = n;
  A.ncols = n;
  A.rowptr.resize(n + 1);
  A.rowptr[0] = 0;
  for (Index i = 0; i < m; ++i) {
    for (Index j = 0; j < m; ++j) {
      const Index k = i * m + j;
      int row_n = 1;
      if (j > 0) {
        ++row_n;
      }
      if (j + 1 < m) {
        ++row_n;
      }
      if (i > 0) {
        ++row_n;
      }
      if (i + 1 < m) {
        ++row_n;
      }
      A.rowptr[k + 1] = A.rowptr[k] + row_n;
    }
  }
  A.col.resize(A.rowptr[n]);
  A.val.resize(A.rowptr[n]);
  for (Index i = 0; i < m; ++i) {
    for (Index j = 0; j < m; ++j) {
      const Index id = i * m + j;
      Index p = A.rowptr[id];
      auto put = [&](Index c, double v) {
        A.col[p] = c;
        A.val[p++] = v;
      };
      if (j > 0) {
        put(id - 1, -1.0);
      }
      if (i > 0) {
        put(id - m, -1.0);
      }
      put(id, 4.0);
      if (i + 1 < m) {
        put(id + m, -1.0);
      }
      if (j + 1 < m) {
        put(id + 1, -1.0);
      }
    }
  }
  return A;
}

static int fails = 0;

static void check(bool ok, const char* msg) {
  if (!ok) {
    std::fprintf(stderr, "FAIL %s\n", msg);
    ++fails;
  } else {
    std::printf("ok  %s\n", msg);
  }
}

int main() {
  {
    Csr A = poisson_1d(8);
    auto lu = dpn::make_direct(A);
    auto amg = dpn::make_amg(A);
    std::vector<double> b(8, 1.0), xlu(8), xamg(8);
    lu->solve(b.data(), xlu.data(), nullptr);
    amg->solve(b.data(), xamg.data(), nullptr);
    double err = 0.0;
    for (int i = 0; i < 8; ++i) {
      err = std::max(err, std::abs(xlu[i] - xamg[i]));
    }
    check(err < 1e-12, "poisson1d n=8 AMG==LU (coarse LU)");
  }
  {
    Csr A = poisson_1d(400);
    auto lu = dpn::make_direct(A);
    auto amg = dpn::make_amg(A);
    std::vector<double> b(400, 1.0), xlu(400), xamg(400);
    lu->solve(b.data(), xlu.data(), nullptr);
    amg->solve(b.data(), xamg.data(), nullptr);
    double err = 0.0;
    for (int i = 0; i < 400; ++i) {
      err = std::max(err, std::abs(xlu[i] - xamg[i]));
    }
    check(amg->n_levels() >= 2, "poisson1d n=400 multilevel");
    check(err < 1e-6, "poisson1d n=400 AMG vs LU");
    std::printf("    levels=%d max|A-B|=%.3e relres=%.3e setup=%.4fs\n", amg->n_levels(), err,
                amg->last_relres(), amg->setup_s());
    auto ras = dpn::make_ras(A);
    std::vector<double> xras(400);
    ras->solve(b.data(), xras.data(), nullptr);
    double errd = 0.0;
    for (int i = 0; i < 400; ++i) {
      errd = std::max(errd, std::abs(xlu[i] - xras[i]));
    }
    check(ras->n_levels() >= 2, "poisson1d RAS multi-domain");
    check(errd < 1e-6, "poisson1d n=400 RAS vs LU");
    std::printf("    RAS ndom=%d max|A-D|=%.3e relres=%.3e\n", ras->n_levels(), errd,
                ras->last_relres());
  }
  {
    Csr A = poisson_2d(40);
    auto lu = dpn::make_direct(A);
    auto amg = dpn::make_amg(A);
    const int n = 1600;
    std::vector<double> b(n, 1.0), xlu(n), xamg(n);
    lu->solve(b.data(), xlu.data(), nullptr);
    amg->solve(b.data(), xamg.data(), nullptr);
    double err = 0.0;
    for (int i = 0; i < n; ++i) {
      err = std::max(err, std::abs(xlu[i] - xamg[i]));
    }
    check(err < 1e-6, "poisson2d 40x40 AMG vs LU");
    std::printf("    levels=%d max|A-B|=%.3e lu_setup=%.4fs amg_setup=%.4fs\n", amg->n_levels(), err,
                lu->setup_s(), amg->setup_s());
    auto ras = dpn::make_ras(A);
    std::vector<double> xras(n);
    ras->solve(b.data(), xras.data(), nullptr);
    double errd = 0.0;
    for (int i = 0; i < n; ++i) {
      errd = std::max(errd, std::abs(xlu[i] - xras[i]));
    }
    check(ras->n_levels() >= 2, "poisson2d RAS multi-domain");
    check(errd < 1e-6, "poisson2d 40x40 RAS vs LU");
    std::printf("    RAS ndom=%d max|A-D|=%.3e relres=%.3e setup=%.4fs\n", ras->n_levels(), errd,
                ras->last_relres(), ras->setup_s());
    DpnHandle* hd = dpn_setup(2, n, A.nnz(), A.rowptr.data(), A.col.data(), A.val.data());
    check(hd != nullptr, "c_api RAS setup 40x40");
    std::vector<double> xapi(static_cast<size_t>(n));
    double rel = 0.0;
    check(dpn_solve(hd, b.data(), xapi.data(), nullptr, &rel) == 0, "c_api RAS solve");
    double erra = 0.0;
    for (int i = 0; i < n; ++i) {
      erra = std::max(erra, std::abs(xlu[i] - xapi[i]));
    }
    check(erra < 1e-6, "c_api RAS vs LU 40x40");
    const int ndom_api = dpn_n_levels(hd);
    check(ndom_api >= 2, "c_api RAS ndom");
    dpn_free(hd);
    std::printf("    c_api RAS max|A-D|=%.3e relres=%.3e ndom=%d\n", erra, rel, ndom_api);
  }
  {
    // 1-node implicit Euler: (g + c/dt) v = g*vdd - i + (c/dt) vprev
    const double vdd = 1.1, r = 2.0, c = 50e-12, dt = 10e-12, i = 5e-3;
    const double g = 1.0 / r;
    const double a = g + c / dt;
    const double vprev = vdd;
    const double rhs = g * vdd - i + (c / dt) * vprev;
    const double v_closed = rhs / a;
    int rowptr[2] = {0, 1};
    int col[1] = {0};
    double val[1] = {a};
    DpnHandle* h = dpn_setup(0, 1, 1, rowptr, col, val);
    check(h != nullptr, "c_api setup direct 1-node");
    double b = rhs, x = 0.0, rel = 0.0;
    check(dpn_solve(h, &b, &x, nullptr, &rel) == 0, "c_api solve 1-node");
    check(std::abs(x - v_closed) < 1e-12, "1-node BE matches closed form");
    dpn_free(h);
  }
  {
    // Multi-step 1-node BE vs closed form (native timestep).
    const double vdd = 1.1, r = 2.0, c = 50e-12, dt = 10e-12, ipulse = 5e-3;
    const double t50 = 0.2e-9, dur = 0.2e-9, t_end = 0.8e-9;
    const double g = 1.0 / r;
    const double a = g + c / dt;
    int rowptr[2] = {0, 1};
    int col[1] = {0};
    double val[1] = {a};
    double C[1] = {c};
    double leak[1] = {0.0};
    double pad[1] = {g * vdd};
    int ev_idx[1] = {0};
    double ev_t50[1] = {t50}, ev_dur[1] = {dur}, ev_ip[1] = {ipulse};
    DpnHandle* h = dpn_setup(0, 1, 1, rowptr, col, val);
    const int maxs = 128;
    std::vector<double> wt(maxs), wv(maxs), wi(maxs), Vw(1);
    int worst_node = 0, n_steps = 0;
    double worst_v = 0, worst_t = 0, rel = 0, ts = 0;
    check(dpn_timestep_be(h, C, leak, pad, dt, t_end, vdd, 1, ev_idx, ev_t50, ev_dur, ev_ip,
                          Vw.data(), &worst_node, &worst_v, &worst_t, &rel, &ts, maxs, wt.data(),
                          wv.data(), wi.data(), &n_steps) == 0,
          "native timestep 1-node rc");
    double v = vdd, worst_cf = vdd;
    const int steps = std::max(2, static_cast<int>(std::ceil(t_end / dt)));
    for (int s = 0; s < steps; ++s) {
      const double t = s * dt;
      const double i = dpn::triangle(t, t50, dur, ipulse);
      v = (g * vdd - i + (c / dt) * v) / a;
      worst_cf = std::min(worst_cf, v);
    }
    check(n_steps == steps, "native timestep step count");
    check(std::abs(worst_v - worst_cf) < 1e-12, "native timestep vs closed-form BE");
    dpn_free(h);

    int bumps[1] = {0};
    double bump_v[1] = {vdd};
    int growptr[2] = {0, 0};
    int gcol[1] = {0};
    double Gempty[1] = {0.0};
    check(dpn_timestep_be_adaptive(1, 0, growptr, gcol, Gempty, C, bumps, 1, bump_v, r, 0.0, vdd,
                                   leak, dt, t_end, 1e-5, 1e-3, 1, ev_idx, ev_t50, ev_dur, ev_ip,
                                   Vw.data(), &worst_node, &worst_v, &worst_t, &rel, &ts, maxs,
                                   wt.data(), wv.data(), wi.data(), &n_steps) == 0,
          "adaptive timestep 1-node");
    check(std::abs(worst_v - worst_cf) < 2e-3, "adaptive vs fine BE (1 mV-class)");
    std::printf("    adaptive steps=%d vmin=%.6f closed=%.6f\n", n_steps, worst_v, worst_cf);
  }
  {
    // Rational Krylov: 1-node is exact with m=1.
    const double vdd = 1.1, r = 2.0, c = 50e-12, dt = 10e-12, ipulse = 5e-3;
    const double t50 = 0.2e-9, dur = 0.2e-9, t_end = 0.8e-9, g = 1.0 / r;
    int rowptr[2] = {0, 1};
    int col[1] = {0};
    double Gval[1] = {g};
    double C[1] = {c};
    double start[1] = {1.0};
    double shifts[2] = {0.0, 1e9};
    DpnMor* mor = dpn_mor_setup(1, 1, rowptr, col, Gval, C, 1, start, 2, shifts, 3);
    check(mor != nullptr && dpn_mor_m(mor) >= 1, "mor setup 1-node");
    double leak[1] = {0.0};
    double pad[1] = {g * vdd};
    int ev_idx[1] = {0};
    double ev_t50[1] = {t50}, ev_dur[1] = {dur}, ev_ip[1] = {ipulse};
    const int maxs = 128;
    std::vector<double> wt(maxs), wv(maxs), wi(maxs), Vw(1);
    int worst_node = 0, n_steps = 0;
    double worst_v = 0, worst_t = 0, rel = 0, ts = 0;
    check(dpn_mor_timestep(mor, leak, pad, dt, t_end, vdd, 1, ev_idx, ev_t50, ev_dur, ev_ip,
                           Vw.data(), &worst_node, &worst_v, &worst_t, &rel, &ts, maxs, wt.data(),
                           wv.data(), wi.data(), &n_steps) == 0,
          "mor timestep 1-node");
    const double a = g + c / dt;
    double v = vdd, worst_cf = vdd;
    const int steps = std::max(2, static_cast<int>(std::ceil(t_end / dt)));
    for (int s = 0; s < steps; ++s) {
      const double t = s * dt;
      const double i = dpn::triangle(t, t50, dur, ipulse);
      v = (g * vdd - i + (c / dt) * v) / a;
      worst_cf = std::min(worst_cf, v);
    }
    check(std::abs(worst_v - worst_cf) < 1e-9, "1-node MOR == full BE");
    std::printf("    mor m=%d vmin=%.9f closed=%.9f\n", dpn_mor_m(mor), worst_v, worst_cf);
    dpn_mor_free(mor);
  }
  {
    // 1D RC line: MOR vs SparseLU BE.
    const int n = 20;
    Csr G = r_chain(n, 2.0);
    std::vector<double> C(n, 20e-12);
    std::vector<double> leak(n, 0.0);
    std::vector<double> pad(n, 0.0);
    const double vdd = 1.1, dt = 20e-12, t_end = 0.4e-9, g_pad = 1.0;
    std::vector<double> dpad(n, 0.0);
    dpad[0] = g_pad;
    pad[0] = g_pad * vdd;
    Csr Gp = dpn::plus_diag(G, dpad.data());
    std::vector<double> Cd(n);
    for (int i = 0; i < n; ++i) {
      Cd[i] = C[i] / dt;
    }
    Csr A = dpn::plus_diag(Gp, Cd.data());
    auto lu = dpn::make_direct(A);
    dpn::TriangleSrc ev;
    ev.idx = n - 1;
    ev.t50 = 0.12e-9;
    ev.dur = 0.08e-9;
    ev.ipulse = 3e-3;
    auto full = dpn::timestep_be(*lu, A, C.data(), leak.data(), pad.data(), dt, t_end, vdd, &ev, 1);
    std::vector<double> start(n, 0.0);
    start[n - 1] = 1.0;
    start[0] = 1.0;
    double shifts[3] = {0.0, 1e9, 1.0 / dt};
    auto mor = dpn::make_mor(Gp, C.data(), 1, start.data(), 3, shifts, 4);
    auto red = mor->timestep(leak.data(), pad.data(), dt, t_end, vdd, &ev, 1);
    const double err = std::abs(full.worst_v - red.worst_v);
    check(mor->m() >= 2, "RC line MOR multilevel basis");
    check(err < 5e-3, "RC line MOR vs LU BE (< 5 mV)");
    std::printf("    RC n=20 m=%d |A-C|=%.3e V  full=%.4f red=%.4f\n", mor->m(), err, full.worst_v,
                red.worst_v);
  }
  {
    // Series R+L companion with history: 1-node vs hand BE (two steps differ from resistive L/dt).
    const double vdd = 1.1, R = 0.05, L = 2e-10, c = 50e-12, dt = 10e-12, ipulse = 5e-3;
    const double t50 = 0.2e-9, dur = 0.2e-9, t_end = 0.4e-9;
    double g_eq = 0.0, hsc = 0.0;
    dpn::rl_companion(R, L, dt, &g_eq, &hsc);
    check(g_eq > 0.0 && hsc > 0.0, "RL companion g_eq and history scale");
    int growptr[2] = {0, 0};
    int gcol[1] = {0};
    double Gempty[1] = {0.0};
    Csr Gmesh = dpn::from_csr(1, growptr, gcol, Gempty);
    double C[1] = {c};
    int bumps[1] = {0};
    double bump_v[1] = {vdd};
    std::vector<double> pad;
    Csr A = dpn::form_be_operator(Gmesh, C, dt, bumps, 1, bump_v, R, L, pad);
    auto lu = dpn::make_direct(A);
    dpn::TriangleSrc ev;
    ev.idx = 0;
    ev.t50 = t50;
    ev.dur = dur;
    ev.ipulse = ipulse;
    double leak[1] = {0.0};
    auto hist = dpn::timestep_be_hist(*lu, A, C, leak, dt, t_end, &ev, 1, bumps, 1, bump_v, R, L);
    // Hand companion
    double v = vdd, iL = 0.0, worst = vdd;
    const int steps = std::max(2, static_cast<int>(std::ceil(t_end / dt)));
    for (int s = 0; s < steps; ++s) {
      const double t = s * dt;
      const double id = dpn::triangle(t, t50, dur, ipulse);
      const double rhs = (c / dt) * v - id + g_eq * vdd + hsc * iL;
      const double a = c / dt + g_eq;
      const double vn = rhs / a;
      iL = g_eq * (vdd - vn) + hsc * iL;
      v = vn;
      worst = std::min(worst, v);
    }
    check(std::abs(hist.worst_v - worst) < 1e-12, "1-node RL history vs hand companion");
    // Resistive L/dt (no history) must differ once the inductor has current.
    double v_r = vdd, worst_r = vdd;
    const double g_res = 1.0 / std::max(R + L / dt, 1e-9);
    const double a_r = c / dt + g_res;
    for (int s = 0; s < steps; ++s) {
      const double t = s * dt;
      const double id = dpn::triangle(t, t50, dur, ipulse);
      v_r = ((c / dt) * v_r - id + g_res * vdd) / a_r;
      worst_r = std::min(worst_r, v_r);
    }
    check(std::abs(worst - worst_r) > 1e-6, "RL history differs from memoryless L/dt");
    std::printf("    RL hist vmin=%.6f resistive=%.6f iLmax=%.4e\n", hist.worst_v, worst_r,
                hist.i_L_absmax);
    std::vector<int> rp(A.rowptr.begin(), A.rowptr.end());
    std::vector<int> ci(A.col.begin(), A.col.end());
    DpnHandle* hh = dpn_setup(0, 1, A.nnz(), rp.data(), ci.data(), A.val.data());
    check(hh != nullptr, "c_api hist setup");
    const int maxs = 128;
    std::vector<double> wt(maxs), wv(maxs), wi(maxs), Vw(1);
    int worst_node = 0, n_steps = 0;
    double worst_v = 0, worst_t = 0, rel = 0, ts = 0, ilabs = 0, ilw[1] = {0};
    int ev_idx[1] = {0};
    double ev_t50[1] = {t50}, ev_dur[1] = {dur}, ev_ip[1] = {ipulse};
    check(dpn_timestep_be_hist(hh, C, leak, dt, t_end, bumps, 1, bump_v, R, L, 1, ev_idx, ev_t50,
                               ev_dur, ev_ip, Vw.data(), &worst_node, &worst_v, &worst_t, &rel, &ts,
                               maxs, wt.data(), wv.data(), wi.data(), &n_steps, &ilabs, ilw) == 0,
          "c_api timestep_be_hist");
    check(std::abs(worst_v - worst) < 1e-12, "c_api RL hist vs hand companion");
    dpn_free(hh);

    std::vector<double> start(1, 1.0);
    double shifts[3] = {0.0, 1e9, 1.0 / dt};
    auto mor = dpn::make_mor_rlc(Gmesh, C, bumps, 1, bump_v, R, L, 1, start.data(), 3, shifts, 4);
    double pad0[1] = {0.0};
    auto red = mor->timestep(leak, pad0, dt, t_end, vdd, &ev, 1);
    const double err_rlc = std::abs(red.worst_v - hist.worst_v);
    check(mor->rlc(), "1-node MOR is descriptor RLC");
    check(err_rlc < 5e-3, "1-node RLC MOR vs hist BE (< 5 mV)");
    std::printf("    RLC MOR m=%d vmin=%.6f hist=%.6f |A-C|=%.3e V\n", mor->m(), red.worst_v,
                hist.worst_v, err_rlc);
  }
  {
    // 2-node RC line + package R+L: descriptor MOR vs hist BE gold.
    const int n = 2;
    Csr G = r_chain(n, 0.2);
    std::vector<double> C(n, 50e-12);
    const double vdd = 1.1, dt = 10e-12, t_end = 0.4e-9, R = 0.05, L = 2e-10;
    int bumps[1] = {0};
    double bump_v[1] = {vdd};
    std::vector<double> pad;
    Csr A = dpn::form_be_operator(G, C.data(), dt, bumps, 1, bump_v, R, L, pad);
    auto lu = dpn::make_direct(A);
    dpn::TriangleSrc ev;
    ev.idx = 1;
    ev.t50 = 0.2e-9;
    ev.dur = 0.2e-9;
    ev.ipulse = 5e-3;
    double leak[2] = {0.0, 0.0};
    auto hist = dpn::timestep_be_hist(*lu, A, C.data(), leak, dt, t_end, &ev, 1, bumps, 1, bump_v,
                                      R, L);
    std::vector<double> start(n, 0.0);
    start[1] = 1.0;
    double shifts[3] = {0.0, 1e9, 1.0 / dt};
    auto mor = dpn::make_mor_rlc(G, C.data(), bumps, 1, bump_v, R, L, 1, start.data(), 3, shifts, 4);
    double pad0[2] = {0.0, 0.0};
    auto red = mor->timestep(leak, pad0, dt, t_end, vdd, &ev, 1);
    const double err = std::abs(red.worst_v - hist.worst_v);
    check(mor->rlc(), "2-node MOR is descriptor RLC");
    check(err < 5e-3, "2-node RLC MOR vs hist BE (< 5 mV)");
    std::printf("    2-node RLC MOR m=%d vmin=%.6f hist=%.6f |A-C|=%.3e V\n", mor->m(), red.worst_v,
                hist.worst_v, err);
  }
  {
    // Compact VRM+die descriptor BE vs dense 4×4 gold (same stamp as pdn_vrm.compact_vrm_die).
    const double vdd = 1.1, dt = 10e-12, t_end = 0.4e-9;
    const double r_vrm = 0.015, r_pkg = 0.05;
    const double c_vrm = 50e-12, c_die = 50e-12, l_vrm = 2e-10, l_pkg = 2e-10;
    const double t50 = 0.2e-9, dur = 0.2e-9, ipulse = 5e-3;
    Index ti[8] = {0, 0, 1, 2, 2, 3, 3, 3};
    Index tj[8] = {2, 3, 3, 0, 2, 1, 0, 3};
    double tv[8] = {-1.0, 1.0, -1.0, 1.0, r_vrm, 1.0, -1.0, r_pkg};
    Csr A = dpn::from_triplets(4, ti, tj, tv, 8);
    double E[4] = {c_vrm, c_die, l_vrm, l_pkg};
    dpn::TriangleSrc ev;
    ev.idx = 0;
    ev.t50 = t50;
    ev.dur = dur;
    ev.ipulse = ipulse;
    auto desc = dpn::timestep_descriptor(A, E, dt, t_end, vdd, 2, 1, 1, 2, nullptr, &ev, 1);

    double Ad[4][4] = {};
    Ad[0][2] = -1.0;
    Ad[0][3] = 1.0;
    Ad[1][3] = -1.0;
    Ad[2][0] = 1.0;
    Ad[2][2] = r_vrm;
    Ad[3][1] = 1.0;
    Ad[3][0] = -1.0;
    Ad[3][3] = r_pkg;
    double K[4][4];
    for (int i = 0; i < 4; ++i) {
      for (int j = 0; j < 4; ++j) {
        K[i][j] = Ad[i][j] + (i == j ? E[i] / dt : 0.0);
      }
    }
    double x[4] = {vdd, vdd, 0.0, 0.0};
    double worst = vdd;
    const int steps = std::max(2, static_cast<int>(std::ceil(t_end / dt)));
    for (int s = 0; s < steps; ++s) {
      const double t = static_cast<double>(s) * dt;
      const double idraw = dpn::triangle(t, t50, dur, ipulse);
      double rhs[4];
      for (int i = 0; i < 4; ++i) {
        rhs[i] = (E[i] / dt) * x[i];
      }
      rhs[1] -= idraw;
      rhs[2] += vdd;
      ge4(K, rhs, x);
      worst = std::min(worst, x[1]);
    }
    check(std::abs(desc.worst_v - worst) < 1e-12, "compact VRM descriptor vs dense 4x4 BE");
    std::printf("    N4 descriptor vmin=%.9f gold=%.9f |err|=%.3e V\n", desc.worst_v, worst,
                std::abs(desc.worst_v - worst));

    std::vector<int> rp(A.rowptr.begin(), A.rowptr.end());
    std::vector<int> ci(A.col.begin(), A.col.end());
    const int maxs = 128;
    std::vector<double> wt(maxs), wv(maxs), wi(maxs), Vw(1);
    int worst_node = 0, n_steps = 0;
    double worst_v = 0, worst_t = 0, rel = 0, ts = 0;
    int ev_idx[1] = {0};
    double ev_t50[1] = {t50}, ev_dur[1] = {dur}, ev_ip[1] = {ipulse};
    check(dpn_timestep_descriptor(4, A.nnz(), rp.data(), ci.data(), A.val.data(), E, 2, 1, 1, 2, dt,
                                  t_end, vdd, nullptr, 1, ev_idx, ev_t50, ev_dur, ev_ip, Vw.data(),
                                  &worst_node, &worst_v, &worst_t, &rel, &ts, maxs, wt.data(),
                                  wv.data(), wi.data(), &n_steps) == 0,
          "c_api timestep_descriptor");
    check(std::abs(worst_v - worst) < 1e-12, "c_api compact VRM descriptor vs dense 4x4 BE");
  }
  if (fails) {
    std::fprintf(stderr, "%d checks failed\n", fails);
    return 1;
  }
  std::printf("ALL dpn_test PASSED\n");
  return 0;
}
