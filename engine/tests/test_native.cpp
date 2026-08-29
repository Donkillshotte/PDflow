#include "dpn/c_api.h"
#include "dpn/csr.hpp"
#include "dpn/mor.hpp"
#include "dpn/solvers.hpp"
#include "dpn/transient.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
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
  check(sizeof(Index) == 8, "Index is 8 bytes");
  check(dpn_index_width() == 64, "dpn_index_width is 64");
  {
    Index rp0[2] = {0, 0};
    Csr Z = dpn::from_csr(1, rp0, nullptr, nullptr);
    check(Z.nrows == 1 && Z.nnz() == 0, "from_csr nnz=0 allows null col/val");
    Index rp1[2] = {0, 1};
    DpnHandle* bad = dpn_setup(0, 1, 1, rp1, nullptr, nullptr);
    check(bad == nullptr, "c_api nnz>0 rejects null col/val");
  }
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
    Index rowptr[2] = {0, 1};
    Index col[1] = {0};
    double val[1] = {a};
    DpnHandle* h = dpn_setup(0, 1, 1, rowptr, col, val);
    check(h != nullptr, "c_api setup direct 1-node");
    check(dpn_n(h) == 1, "c_api dpn_n is int64");
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
    Index rowptr[2] = {0, 1};
    Index col[1] = {0};
    double val[1] = {a};
    double C[1] = {c};
    double leak[1] = {0.0};
    double pad[1] = {g * vdd};
    Index ev_idx[1] = {0};
    double ev_t50[1] = {t50}, ev_dur[1] = {dur}, ev_ip[1] = {ipulse};
    DpnHandle* h = dpn_setup(0, 1, 1, rowptr, col, val);
    const int maxs = 128;
    std::vector<double> wt(maxs), wv(maxs), wi(maxs), Vw(1);
    Index worst_node = 0, n_steps = 0;
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

    Index bumps[1] = {0};
    double bump_v[1] = {vdd};
    Index growptr[2] = {0, 0};
    Index gcol[1] = {0};
    double Gempty[1] = {0.0};
    check(dpn_timestep_be_adaptive(1, 0, growptr, gcol, Gempty, C, bumps, 1, bump_v, r, 0.0, vdd,
                                   leak, dt, t_end, 1e-5, 1e-3, 1, ev_idx, ev_t50, ev_dur, ev_ip,
                                   Vw.data(), &worst_node, &worst_v, &worst_t, &rel, &ts, maxs,
                                   wt.data(), wv.data(), wi.data(), &n_steps) == 0,
          "adaptive timestep 1-node");
    check(std::abs(worst_v - worst_cf) < 2e-3, "adaptive vs fine BE (1 mV-class)");
    std::printf("    adaptive steps=%ld vmin=%.6f closed=%.6f\n", static_cast<long>(n_steps), worst_v,
                worst_cf);
  }
  {
    // Rational Krylov: 1-node is exact with m=1.
    const double vdd = 1.1, r = 2.0, c = 50e-12, dt = 10e-12, ipulse = 5e-3;
    const double t50 = 0.2e-9, dur = 0.2e-9, t_end = 0.8e-9, g = 1.0 / r;
    Index rowptr[2] = {0, 1};
    Index col[1] = {0};
    double Gval[1] = {g};
    double C[1] = {c};
    double start[1] = {1.0};
    double shifts[2] = {0.0, 1e9};
    DpnMor* mor = dpn_mor_setup(1, 1, rowptr, col, Gval, C, 1, start, 2, shifts, 3);
    check(mor != nullptr && dpn_mor_m(mor) >= 1, "mor setup 1-node");
    double leak[1] = {0.0};
    double pad[1] = {g * vdd};
    Index ev_idx[1] = {0};
    double ev_t50[1] = {t50}, ev_dur[1] = {dur}, ev_ip[1] = {ipulse};
    const int maxs = 128;
    std::vector<double> wt(maxs), wv(maxs), wi(maxs), Vw(1);
    Index worst_node = 0, n_steps = 0;
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
    Index growptr[2] = {0, 0};
    Index gcol[1] = {0};
    double Gempty[1] = {0.0};
    Csr Gmesh = dpn::from_csr(1, growptr, gcol, Gempty);
    double C[1] = {c};
    Index bumps[1] = {0};
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
    DpnHandle* hh = dpn_setup(0, 1, A.nnz(), A.rowptr.data(), A.col.data(), A.val.data());
    check(hh != nullptr, "c_api hist setup");
    const int maxs = 128;
    std::vector<double> wt(maxs), wv(maxs), wi(maxs), Vw(1);
    Index worst_node = 0, n_steps = 0;
    double worst_v = 0, worst_t = 0, rel = 0, ts = 0, ilabs = 0, ilw[1] = {0};
    Index ev_idx[1] = {0};
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
    Index bumps[1] = {0};
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

    const int maxs = 128;
    std::vector<double> wt(maxs), wv(maxs), wi(maxs), Vw(1);
    Index worst_node = 0, n_steps = 0;
    double worst_v = 0, worst_t = 0, rel = 0, ts = 0;
    Index ev_idx[1] = {0};
    double ev_t50[1] = {t50}, ev_dur[1] = {dur}, ev_ip[1] = {ipulse};
    check(dpn_timestep_descriptor(4, A.nnz(), A.rowptr.data(), A.col.data(), A.val.data(), E, 2, 1, 1,
                                  2, dt,
                                  t_end, vdd, nullptr, 1, ev_idx, ev_t50, ev_dur, ev_ip, Vw.data(),
                                  &worst_node, &worst_v, &worst_t, &rel, &ts, maxs, wt.data(),
                                  wv.data(), wi.data(), &n_steps) == 0,
          "c_api timestep_descriptor");
    check(std::abs(worst_v - worst) < 1e-12, "c_api compact VRM descriptor vs dense 4x4 BE");

    Csr Ed = dpn::diag_csr(4, E);
    Index iv_row[1] = {2};
    double worst_g = 0;
    check(dpn_timestep_descriptor_gen(4, A.nnz(), A.rowptr.data(), A.col.data(), A.val.data(),
                                      Ed.nnz(), Ed.rowptr.data(), Ed.col.data(), Ed.val.data(), 2, 1,
                                      1, 1, iv_row, dt, t_end, vdd, nullptr, nullptr, 1, ev_idx,
                                      ev_t50, ev_dur, ev_ip, Vw.data(), &worst_node, &worst_g,
                                      &worst_t, &rel, &ts, maxs, wt.data(), wv.data(), wi.data(),
                                      &n_steps) == 0,
          "c_api timestep_descriptor_gen diagonal E");
    check(std::abs(worst_g - worst) < 1e-12, "gen API diagonal E vs dense 4x4");

    auto gen = dpn::timestep_descriptor_gen(A, Ed, dt, t_end, vdd, 2, 1, 1, iv_row, 1, nullptr,
                                            nullptr, &ev, 1);
    check(std::abs(gen.worst_v - desc.worst_v) < 1e-15, "sparse-E gen vs diagonal descriptor");
  }
  {
    // Sparse E with off-diagonal C (mutual capacitance analogue) vs dense 2×2 BE.
    const double vdd = 1.1, dt = 10e-12, t_end = 0.4e-9, t50 = 0.2e-9, dur = 0.2e-9, ipulse = 5e-3;
    const double g = 1.0 / 0.2, gpad = 1.0 / 0.05, C = 50e-12, Mc = 5e-12;
    Index ti[4] = {0, 0, 1, 1};
    Index tj[4] = {0, 1, 0, 1};
    double tv[4] = {g + gpad, -g, -g, g};
    Csr A = dpn::from_triplets(2, ti, tj, tv, 4);
    Index ei[4] = {0, 0, 1, 1};
    Index ej[4] = {0, 1, 0, 1};
    double evv[4] = {C, Mc, Mc, C};
    Csr E = dpn::from_triplets(2, ei, ej, evv, 4);
    double u0[2] = {gpad * vdd, 0.0};
    dpn::TriangleSrc ev;
    ev.idx = 1;
    ev.t50 = t50;
    ev.dur = dur;
    ev.ipulse = ipulse;
    auto desc = dpn::timestep_descriptor_gen(A, E, dt, t_end, vdd, 2, 2, -1, nullptr, 0, nullptr, u0,
                                             &ev, 1);
    double Ad[2][2] = {{g + gpad, -g}, {-g, g}};
    double Ed[2][2] = {{C, Mc}, {Mc, C}};
    double K[2][2];
    for (int i = 0; i < 2; ++i) {
      for (int j = 0; j < 2; ++j) {
        K[i][j] = Ad[i][j] + Ed[i][j] / dt;
      }
    }
    double x[2] = {vdd, vdd};
    double worst = vdd;
    const int steps = std::max(2, static_cast<int>(std::ceil(t_end / dt)));
    for (int s = 0; s < steps; ++s) {
      const double t = static_cast<double>(s) * dt;
      const double idraw = dpn::triangle(t, t50, dur, ipulse);
      double rhs[2];
      rhs[0] = (Ed[0][0] / dt) * x[0] + (Ed[0][1] / dt) * x[1] + u0[0];
      rhs[1] = (Ed[1][0] / dt) * x[0] + (Ed[1][1] / dt) * x[1] + u0[1] - idraw;
      const double det = K[0][0] * K[1][1] - K[0][1] * K[1][0];
      const double x0n = (K[1][1] * rhs[0] - K[0][1] * rhs[1]) / det;
      const double x1n = (K[0][0] * rhs[1] - K[1][0] * rhs[0]) / det;
      x[0] = x0n;
      x[1] = x1n;
      worst = std::min(worst, x[1]);
    }
    check(std::abs(desc.worst_v - worst) < 1e-12, "sparse-E mutual C vs dense 2x2 BE");
    std::printf("    sparse E vmin=%.9f gold=%.9f |err|=%.3e V\n", desc.worst_v, worst,
                std::abs(desc.worst_v - worst));
  }
  {
    // Two coupled strap L (M off-diag in E) vs dense 4×4 BE.
    const double vdd = 1.1, dt = 10e-12, t_end = 0.4e-9, t50 = 0.2e-9, dur = 0.2e-9, ipulse = 5e-3;
    const double R = 0.38, L = 1e-12, M = 0.3e-12, C = 50e-12, gpad = 1.0 / 0.05;
    Index ti[10] = {0, 0, 1, 2, 2, 2, 0, 1, 3, 3};
    Index tj[10] = {0, 2, 2, 0, 1, 2, 3, 3, 0, 1};
    double tv[10] = {gpad, -1.0, 1.0, 1.0, -1.0, R, -1.0, 1.0, 1.0, -1.0};
    // A[3,3]=R
    Index ti2[1] = {3};
    Index tj2[1] = {3};
    double tv2[1] = {R};
    Csr A1 = dpn::from_triplets(4, ti, tj, tv, 10);
    Csr A2 = dpn::from_triplets(4, ti2, tj2, tv2, 1);
    Csr A = dpn::plus(A1, A2);
    Index ei[6] = {0, 1, 2, 2, 3, 3};
    Index ej[6] = {0, 1, 2, 3, 2, 3};
    double evv[6] = {C, C, L, M, M, L};
    Csr E = dpn::from_triplets(4, ei, ej, evv, 6);
    double u0[4] = {gpad * vdd, 0, 0, 0};
    dpn::TriangleSrc ev;
    ev.idx = 1;
    ev.t50 = t50;
    ev.dur = dur;
    ev.ipulse = ipulse;
    auto desc = dpn::timestep_descriptor_gen(A, E, dt, t_end, vdd, 2, 2, -1, nullptr, 0, nullptr, u0,
                                             &ev, 1);
    double Ad[4][4] = {};
    Ad[0][0] = gpad;
    Ad[0][2] = -1.0;
    Ad[1][2] = 1.0;
    Ad[2][0] = 1.0;
    Ad[2][1] = -1.0;
    Ad[2][2] = R;
    Ad[0][3] = -1.0;
    Ad[1][3] = 1.0;
    Ad[3][0] = 1.0;
    Ad[3][1] = -1.0;
    Ad[3][3] = R;
    double Ed[4][4] = {};
    Ed[0][0] = C;
    Ed[1][1] = C;
    Ed[2][2] = L;
    Ed[3][3] = L;
    Ed[2][3] = M;
    Ed[3][2] = M;
    double K[4][4];
    for (int i = 0; i < 4; ++i) {
      for (int j = 0; j < 4; ++j) {
        K[i][j] = Ad[i][j] + Ed[i][j] / dt;
      }
    }
    double x[4] = {vdd, vdd, 0.0, 0.0};
    double worst = vdd;
    const int steps = std::max(2, static_cast<int>(std::ceil(t_end / dt)));
    for (int s = 0; s < steps; ++s) {
      const double t = static_cast<double>(s) * dt;
      const double idraw = dpn::triangle(t, t50, dur, ipulse);
      double rhs[4] = {};
      for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 4; ++j) {
          rhs[i] += (Ed[i][j] / dt) * x[j];
        }
      }
      rhs[0] += u0[0];
      rhs[1] -= idraw;
      ge4(K, rhs, x);
      worst = std::min(worst, x[1]);
    }
    check(std::abs(desc.worst_v - worst) < 1e-12, "coupled L sparse-E vs dense 4x4 BE");
    std::printf("    coupled L vmin=%.9f gold=%.9f |err|=%.3e V\n", desc.worst_v, worst,
                std::abs(desc.worst_v - worst));
  }
  {
    Csr A = poisson_1d(400);
    auto lu = dpn::make_direct(A);
    auto bicg = dpn::make_bicgstab(A);
    std::vector<double> b(400, 1.0), xlu(400), xbicg(400);
    lu->solve(b.data(), xlu.data(), nullptr);
    bicg->solve(b.data(), xbicg.data(), nullptr);
    double err = 0.0;
    for (int i = 0; i < 400; ++i) {
      err = std::max(err, std::abs(xlu[i] - xbicg[i]));
    }
    check(err < 1e-6, "poisson1d n=400 BiCGSTAB vs LU");
    std::printf("    BiCGSTAB max|A-E|=%.3e relres=%.3e name=%s\n", err, bicg->last_relres(),
                bicg->name());
    DpnHandle* hb = dpn_setup(3, 400, A.nnz(), A.rowptr.data(), A.col.data(), A.val.data());
    check(hb != nullptr, "c_api BiCGSTAB setup");
    std::vector<double> xapi(400);
    double rel = 0.0;
    check(dpn_solve(hb, b.data(), xapi.data(), nullptr, &rel) == 0, "c_api BiCGSTAB solve");
    double erra = 0.0;
    for (int i = 0; i < 400; ++i) {
      erra = std::max(erra, std::abs(xlu[i] - xapi[i]));
    }
    check(erra < 1e-6, "c_api BiCGSTAB vs LU");
    dpn_free(hb);
  }
  {
    // Unsymmetric compact-VRM K = A + E/dt: BiCGSTAB vs SparseLU.
    const double dt = 10e-12, r_vrm = 0.015, r_pkg = 0.05;
    const double c_vrm = 50e-12, c_die = 50e-12, l_vrm = 2e-10, l_pkg = 2e-10;
    Index ti[8] = {0, 0, 1, 2, 2, 3, 3, 3};
    Index tj[8] = {2, 3, 3, 0, 2, 1, 0, 3};
    double tv[8] = {-1.0, 1.0, -1.0, 1.0, r_vrm, 1.0, -1.0, r_pkg};
    Csr A = dpn::from_triplets(4, ti, tj, tv, 8);
    double Ed[4] = {c_vrm / dt, c_die / dt, l_vrm / dt, l_pkg / dt};
    Csr K = dpn::plus_diag(A, Ed);
    auto lu = dpn::make_direct(K);
    auto bicg = dpn::make_bicgstab(K);
    std::vector<double> b{1.0, -0.005, 1.1, 0.0}, xlu(4), xbicg(4);
    lu->solve(b.data(), xlu.data(), nullptr);
    bicg->solve(b.data(), xbicg.data(), nullptr);
    double err = 0.0;
    for (int i = 0; i < 4; ++i) {
      err = std::max(err, std::abs(xlu[i] - xbicg[i]));
    }
    check(err < 1e-8, "unsymmetric VRM K BiCGSTAB vs LU");
    std::printf("    unsym BiCGSTAB max|LU-E|=%.3e relres=%.3e\n", err, bicg->last_relres());
  }
  {
    // Sparse-E workhorse (kind=3), adaptive Δt, and gen MOR on compact VRM.
    const double vdd = 1.1, dt = 10e-12, t_end = 0.4e-9;
    const double r_vrm = 0.015, r_pkg = 0.05;
    const double c_vrm = 50e-12, c_die = 50e-12, l_vrm = 2e-10, l_pkg = 2e-10;
    const double t50 = 0.2e-9, dur = 0.2e-9, ipulse = 5e-3;
    Index ti[8] = {0, 0, 1, 2, 2, 3, 3, 3};
    Index tj[8] = {2, 3, 3, 0, 2, 1, 0, 3};
    double tv[8] = {-1.0, 1.0, -1.0, 1.0, r_vrm, 1.0, -1.0, r_pkg};
    Csr A = dpn::from_triplets(4, ti, tj, tv, 8);
    double Ediag[4] = {c_vrm, c_die, l_vrm, l_pkg};
    Csr E = dpn::diag_csr(4, Ediag);
    Index iv_row[1] = {2};
    dpn::TriangleSrc ev;
    ev.idx = 0;
    ev.t50 = t50;
    ev.dur = dur;
    ev.ipulse = ipulse;
    auto gold = dpn::timestep_descriptor_gen(A, E, dt, t_end, vdd, 2, 1, 1, iv_row, 1, nullptr,
                                            nullptr, &ev, 1, 0);
    auto bicg = dpn::timestep_descriptor_gen(A, E, dt, t_end, vdd, 2, 1, 1, iv_row, 1, nullptr,
                                            nullptr, &ev, 1, 3);
    check(std::abs(bicg.worst_v - gold.worst_v) < 1e-8, "descriptor BiCGSTAB vs SparseLU gold");
    std::printf("    descriptor BiCGSTAB vmin=%.9f gold=%.9f |err|=%.3e V\n", bicg.worst_v,
                gold.worst_v, std::abs(bicg.worst_v - gold.worst_v));

    auto ad = dpn::timestep_descriptor_adaptive(A, E, dt, t_end, vdd, 2, 1, 1, iv_row, 1, nullptr,
                                               nullptr, 1e-4, 0.01, &ev, 1, 0);
    check(ad.steps >= 2, "adaptive descriptor took steps");
    check(std::abs(ad.worst_v - gold.worst_v) < 2e-3, "adaptive descriptor vs fixed-dt (1 mV-class)");
    std::printf("    adaptive descriptor steps=%d vmin=%.6f gold=%.6f |err|=%.3e V\n", ad.steps,
                ad.worst_v, gold.worst_v, std::abs(ad.worst_v - gold.worst_v));

    std::vector<double> start(2, 0.0);
    start[1] = 1.0;
    double shifts[3] = {0.0, 1e9, 1.0 / dt};
    auto mor = dpn::make_mor_gen(A, E, 2, 1, 1, iv_row, 1, nullptr, 1, start.data(), 3, shifts, 4);
    double leak0[1] = {0.0};
    double pad0[2] = {0.0, 0.0};
    auto red = mor->timestep(leak0, pad0, dt, t_end, vdd, &ev, 1);
    check(mor->rlc(), "gen MOR is descriptor RLC");
    check(std::abs(red.worst_v - gold.worst_v) < 5e-3, "compact VRM gen MOR vs descriptor BE");
    std::printf("    gen MOR m=%d vmin=%.6f gold=%.6f |A-C|=%.3e V\n", mor->m(), red.worst_v,
                gold.worst_v, std::abs(red.worst_v - gold.worst_v));

    const int maxs = 8192;
    std::vector<double> wt(maxs), wv(maxs), wi(maxs), Vw(1);
    Index worst_node = 0, n_steps = 0;
    double worst_v = 0, worst_t = 0, rel = 0, ts = 0;
    Index ev_idx[1] = {0};
    double ev_t50[1] = {t50}, ev_dur[1] = {dur}, ev_ip[1] = {ipulse};
    check(dpn_timestep_descriptor_workhorse(
              4, A.nnz(), A.rowptr.data(), A.col.data(), A.val.data(), E.nnz(), E.rowptr.data(),
              E.col.data(), E.val.data(), 2, 1, 1, 1, iv_row, dt, t_end, vdd, nullptr, nullptr, 3, 1,
              ev_idx, ev_t50, ev_dur, ev_ip, Vw.data(), &worst_node, &worst_v, &worst_t, &rel, &ts,
              maxs, wt.data(), wv.data(), wi.data(), &n_steps) == 0,
          "c_api descriptor workhorse BiCGSTAB");
    check(std::abs(worst_v - gold.worst_v) < 1e-8, "c_api workhorse vs LU gold");
    check(dpn_timestep_descriptor_workhorse(
              4, A.nnz(), A.rowptr.data(), A.col.data(), A.val.data(), E.nnz(), E.rowptr.data(),
              E.col.data(), E.val.data(), 2, 1, 1, 1, iv_row, dt, t_end, vdd, nullptr, nullptr, 1, 1,
              ev_idx, ev_t50, ev_dur, ev_ip, Vw.data(), &worst_node, &worst_v, &worst_t, &rel, &ts,
              maxs, wt.data(), wv.data(), wi.data(), &n_steps) == -1,
          "c_api workhorse rejects AMG on unsymmetric K");
    check(dpn_timestep_descriptor_adaptive(
              4, A.nnz(), A.rowptr.data(), A.col.data(), A.val.data(), E.nnz(), E.rowptr.data(),
              E.col.data(), E.val.data(), 2, 1, 1, 1, iv_row, dt, t_end, vdd, nullptr, nullptr, 1e-4,
              0.01, 1, ev_idx, ev_t50, ev_dur, ev_ip, Vw.data(), &worst_node, &worst_v, &worst_t,
              &rel, &ts, maxs, wt.data(), wv.data(), wi.data(), &n_steps) == 0,
          "c_api descriptor adaptive");
    DpnMor* hm = dpn_mor_setup_gen(4, A.nnz(), A.rowptr.data(), A.col.data(), A.val.data(), E.nnz(),
                                   E.rowptr.data(), E.col.data(), E.val.data(), 2, 1, 1, 1, iv_row,
                                   nullptr, 1, start.data(), 3, shifts, 4);
    check(hm != nullptr && dpn_mor_m(hm) >= 1, "c_api mor_setup_gen");
    check(dpn_mor_timestep(hm, leak0, pad0, dt, t_end, vdd, 1, ev_idx, ev_t50, ev_dur, ev_ip,
                           Vw.data(), &worst_node, &worst_v, &worst_t, &rel, &ts, maxs, wt.data(),
                           wv.data(), wi.data(), &n_steps) == 0,
          "c_api gen MOR timestep");
    check(std::abs(worst_v - gold.worst_v) < 5e-3, "c_api gen MOR vs descriptor BE");
    dpn_mor_free(hm);
  }
  {
    // Coupled-L gen MOR vs sparse-E descriptor BE (reduced, 1 mV-class).
    const double vdd = 1.1, dt = 10e-12, t_end = 0.4e-9, t50 = 0.2e-9, dur = 0.2e-9, ipulse = 5e-3;
    const double R = 0.38, L = 1e-12, M = 0.3e-12, C = 50e-12, gpad = 1.0 / 0.05;
    Index ti[10] = {0, 0, 1, 2, 2, 2, 0, 1, 3, 3};
    Index tj[10] = {0, 2, 2, 0, 1, 2, 3, 3, 0, 1};
    double tv[10] = {gpad, -1.0, 1.0, 1.0, -1.0, R, -1.0, 1.0, 1.0, -1.0};
    Index ti2[1] = {3};
    Index tj2[1] = {3};
    double tv2[1] = {R};
    Csr A = dpn::plus(dpn::from_triplets(4, ti, tj, tv, 10), dpn::from_triplets(4, ti2, tj2, tv2, 1));
    Index ei[6] = {0, 1, 2, 2, 3, 3};
    Index ej[6] = {0, 1, 2, 3, 2, 3};
    double evv[6] = {C, C, L, M, M, L};
    Csr E = dpn::from_triplets(4, ei, ej, evv, 6);
    double u0[4] = {gpad * vdd, 0, 0, 0};
    dpn::TriangleSrc ev;
    ev.idx = 1;
    ev.t50 = t50;
    ev.dur = dur;
    ev.ipulse = ipulse;
    auto gold = dpn::timestep_descriptor_gen(A, E, dt, t_end, vdd, 2, 2, -1, nullptr, 0, nullptr, u0,
                                            &ev, 1, 0);
    std::vector<double> start(2, 0.0);
    start[1] = 1.0;
    double shifts[3] = {0.0, 1e9, 1.0 / dt};
    auto mor = dpn::make_mor_gen(A, E, 2, 2, -1, nullptr, 0, u0, 1, start.data(), 3, shifts, 4);
    double leak[2] = {0.0, 0.0};
    double pad0[2] = {0.0, 0.0};
    auto red = mor->timestep(leak, pad0, dt, t_end, vdd, &ev, 1);
    check(std::abs(red.worst_v - gold.worst_v) < 5e-3, "coupled L gen MOR vs sparse-E BE");
    std::printf("    coupled L MOR m=%d vmin=%.6f gold=%.6f |A-C|=%.3e V\n", mor->m(), red.worst_v,
                gold.worst_v, std::abs(red.worst_v - gold.worst_v));
  }
  {
    // Unsymmetric descriptor RAS vs SparseLU on an RC line + bump R+L (ndom≥2).
    const int nv = 32;
    Csr G = r_chain(nv, 0.2);
    const double vdd = 1.1, dt = 10e-12, t_end = 0.4e-9, R = 0.05, L = 2e-10, C = 50e-12;
    const Index N = nv + 1;
    std::vector<Index> ti, tj;
    std::vector<double> tv;
    for (Index i = 0; i < nv; ++i) {
      for (Index k = G.rowptr[i]; k < G.rowptr[i + 1]; ++k) {
        ti.push_back(i);
        tj.push_back(G.col[k]);
        tv.push_back(G.val[k]);
      }
    }
    ti.push_back(0);
    tj.push_back(nv);
    tv.push_back(-1.0);
    ti.push_back(nv);
    tj.push_back(0);
    tv.push_back(1.0);
    ti.push_back(nv);
    tj.push_back(nv);
    tv.push_back(R);
    Csr A = dpn::from_triplets(N, ti.data(), tj.data(), tv.data(), static_cast<Index>(ti.size()));
    std::vector<double> Ed(static_cast<size_t>(N), 0.0);
    for (int i = 0; i < nv; ++i) {
      Ed[static_cast<size_t>(i)] = C;
    }
    Ed[static_cast<size_t>(nv)] = L;
    Csr E = dpn::diag_csr(N, Ed.data());
    Index iv_row[1] = {nv};
    dpn::TriangleSrc ev;
    ev.idx = nv - 1;
    ev.t50 = 0.2e-9;
    ev.dur = 0.2e-9;
    ev.ipulse = 5e-3;
    auto gold = dpn::timestep_descriptor_gen(A, E, dt, t_end, vdd, nv, nv, -1, iv_row, 1, nullptr,
                                            nullptr, &ev, 1, 0);
    Csr K = dpn::plus(A, dpn::scale(E, 1.0 / dt));
    auto ras_op = dpn::make_ras(K);
    check(ras_op->n_levels() >= 2, "descriptor RAS multi-domain");
    auto ras = dpn::timestep_descriptor_gen(A, E, dt, t_end, vdd, nv, nv, -1, iv_row, 1, nullptr,
                                           nullptr, &ev, 1, 2);
    check(std::abs(ras.worst_v - gold.worst_v) < 1e-6, "descriptor RAS vs LU TRAN");
    std::printf("    descriptor RAS ndom=%d vmin=%.9f gold=%.9f |err|=%.3e V\n", ras_op->n_levels(),
                ras.worst_v, gold.worst_v, std::abs(ras.worst_v - gold.worst_v));
    const int maxs = 128;
    std::vector<double> wt(maxs), wv(maxs), wi(maxs), Vw(static_cast<size_t>(nv));
    Index worst_node = 0, n_steps = 0;
    double worst_v = 0, worst_t = 0, rel = 0, ts = 0;
    Index ev_idx[1] = {nv - 1};
    double ev_t50[1] = {ev.t50}, ev_dur[1] = {ev.dur}, ev_ip[1] = {ev.ipulse};
    check(dpn_timestep_descriptor_workhorse(
              N, A.nnz(), A.rowptr.data(), A.col.data(), A.val.data(), E.nnz(), E.rowptr.data(),
              E.col.data(), E.val.data(), nv, nv, -1, 1, iv_row, dt, t_end, vdd, nullptr, nullptr, 2,
              1, ev_idx, ev_t50, ev_dur, ev_ip, Vw.data(), &worst_node, &worst_v, &worst_t, &rel,
              &ts, maxs, wt.data(), wv.data(), wi.data(), &n_steps) == 0,
          "c_api descriptor RAS workhorse");
    check(std::abs(worst_v - gold.worst_v) < 1e-6, "c_api descriptor RAS vs LU");
  }
  {
    double d[2] = {1.0, 2.0};
    Csr D = dpn::diag_csr(2, d);
    Csr S = dpn::scale(D, 0.5);
    Csr P = dpn::plus(D, S);
    check(P.nnz() == 2 && std::abs(P.val[0] - 1.5) < 1e-15 && std::abs(P.val[1] - 3.0) < 1e-15,
          "csr plus/scale/diag");
  }
  if (fails) {
    std::fprintf(stderr, "%d checks failed\n", fails);
    return 1;
  }
  std::printf("ALL dpn_test PASSED\n");
  return 0;
}
