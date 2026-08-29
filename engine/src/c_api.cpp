#include "dpn/c_api.h"

#include "dpn/csr.hpp"
#include "dpn/mor.hpp"
#include "dpn/solvers.hpp"
#include "dpn/transient.hpp"

#include <algorithm>
#include <memory>
#include <new>
#include <vector>

struct DpnHandle {
  dpn::Csr A;
  std::unique_ptr<dpn::Solver> solver;
};

struct DpnMor {
  std::unique_ptr<dpn::RationalMor> mor;
};

namespace {

std::vector<dpn::TriangleSrc> pack_events(int n_events, const int* ev_idx, const double* ev_t50,
                                         const double* ev_dur, const double* ev_ipulse) {
  std::vector<dpn::TriangleSrc> ev(static_cast<size_t>(std::max(n_events, 0)));
  for (int i = 0; i < n_events; ++i) {
    ev[i].idx = ev_idx ? ev_idx[i] : 0;
    ev[i].t50 = ev_t50 ? ev_t50[i] : 0.0;
    ev[i].dur = ev_dur ? ev_dur[i] : 0.0;
    ev[i].ipulse = ev_ipulse ? ev_ipulse[i] : 0.0;
  }
  return ev;
}

int copy_tran(const dpn::TranResult& r, int n, double* V_worst, int* worst_node, double* worst_v,
              double* worst_t, double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
              double* wave_vmin, double* wave_itot, int* n_steps) {
  if (worst_node) {
    *worst_node = static_cast<int>(r.worst_node);
  }
  if (worst_v) {
    *worst_v = r.worst_v;
  }
  if (worst_t) {
    *worst_t = r.worst_t;
  }
  if (rel_res_max) {
    *rel_res_max = r.rel_res_max;
  }
  if (solve_s) {
    *solve_s = r.solve_s;
  }
  if (V_worst) {
    const int nn = static_cast<int>(r.V_worst.size());
    for (int i = 0; i < n && i < nn; ++i) {
      V_worst[i] = r.V_worst[i];
    }
  }
  const int ns = r.steps;
  if (max_steps < ns) {
    if (n_steps) {
      *n_steps = ns;
    }
    return -2;
  }
  if (n_steps) {
    *n_steps = ns;
  }
  for (int i = 0; i < ns; ++i) {
    if (wave_t) {
      wave_t[i] = r.wave_t[i];
    }
    if (wave_vmin) {
      wave_vmin[i] = r.wave_vmin[i];
    }
    if (wave_itot) {
      wave_itot[i] = r.wave_itot[i];
    }
  }
  return 0;
}

}  // namespace

extern "C" {

DpnHandle* dpn_setup(int kind, int n, int nnz, const int* rowptr, const int* col,
                     const double* val) {
  if (!rowptr || !col || !val || n <= 0 || nnz < 0 || rowptr[n] != nnz) {
    return nullptr;
  }
  try {
    auto* h = new DpnHandle();
    h->A = dpn::from_csr(n, rowptr, col, val);
    if (kind == 1) {
      h->solver = dpn::make_amg(h->A);
    } else {
      h->solver = dpn::make_direct(h->A);
    }
    return h;
  } catch (...) {
    return nullptr;
  }
}

int dpn_solve(DpnHandle* h, const double* b, double* x, const double* x0, double* relres) {
  if (!h || !h->solver || !b || !x) {
    return -1;
  }
  h->solver->solve(b, x, x0);
  if (relres) {
    *relres = h->solver->last_relres();
  }
  return 0;
}

int dpn_n(DpnHandle* h) { return h && h->solver ? static_cast<int>(h->solver->n()) : 0; }

int dpn_n_levels(DpnHandle* h) { return h && h->solver ? h->solver->n_levels() : 0; }

double dpn_setup_s(DpnHandle* h) { return h && h->solver ? h->solver->setup_s() : 0.0; }

const char* dpn_name(DpnHandle* h) { return h && h->solver ? h->solver->name() : ""; }

void dpn_free(DpnHandle* h) { delete h; }

int dpn_timestep_be(DpnHandle* h, const double* C, const double* leak, const double* pad, double dt,
                    double t_end, double vdd, int n_events, const int* ev_idx, const double* ev_t50,
                    const double* ev_dur, const double* ev_ipulse, double* V_worst, int* worst_node,
                    double* worst_v, double* worst_t, double* rel_res_max, double* solve_s,
                    int max_steps, double* wave_t, double* wave_vmin, double* wave_itot,
                    int* n_steps) {
  if (!h || !h->solver || !C || !leak || !pad || dt <= 0.0) {
    return -1;
  }
  try {
    auto ev = pack_events(n_events, ev_idx, ev_t50, ev_dur, ev_ipulse);
    auto r = dpn::timestep_be(*h->solver, h->A, C, leak, pad, dt, t_end, vdd, ev.data(),
                              static_cast<int>(ev.size()));
    return copy_tran(r, h->solver->n(), V_worst, worst_node, worst_v, worst_t, rel_res_max, solve_s,
                     max_steps, wave_t, wave_vmin, wave_itot, n_steps);
  } catch (...) {
    return -3;
  }
}

int dpn_timestep_be_adaptive(int n, int nnz, const int* rowptr, const int* col, const double* Gval,
                             const double* C, const int* bumps, int n_bumps, double pkg_r,
                             double pkg_l, double vdd, const double* leak, double dt0, double t_end,
                             double atol, double rtol, int n_events, const int* ev_idx,
                             const double* ev_t50, const double* ev_dur, const double* ev_ipulse,
                             double* V_worst, int* worst_node, double* worst_v, double* worst_t,
                             double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
                             double* wave_vmin, double* wave_itot, int* n_steps) {
  if (!rowptr || !col || !Gval || !C || !leak || n <= 0 || dt0 <= 0.0) {
    return -1;
  }
  try {
    dpn::Csr G = dpn::from_csr(n, rowptr, col, Gval);
    auto ev = pack_events(n_events, ev_idx, ev_t50, ev_dur, ev_ipulse);
    auto r = dpn::timestep_be_adaptive(G, C, bumps, n_bumps, pkg_r, pkg_l, vdd, leak, dt0, t_end,
                                       atol, rtol, ev.data(), static_cast<int>(ev.size()));
    return copy_tran(r, n, V_worst, worst_node, worst_v, worst_t, rel_res_max, solve_s, max_steps,
                     wave_t, wave_vmin, wave_itot, n_steps);
  } catch (...) {
    return -3;
  }
}

DpnMor* dpn_mor_setup(int n, int nnz, const int* rowptr, const int* col, const double* Gval,
                      const double* C, int n_starts, const double* starts, int n_shifts,
                      const double* shifts, int n_moments) {
  if (!rowptr || !col || !Gval || !C || !starts || !shifts || n <= 0 || n_starts <= 0 ||
      n_shifts <= 0 || rowptr[n] != nnz) {
    return nullptr;
  }
  try {
    auto* h = new DpnMor();
    dpn::Csr G = dpn::from_csr(n, rowptr, col, Gval);
    h->mor = dpn::make_mor(G, C, n_starts, starts, n_shifts, shifts, n_moments);
    return h;
  } catch (...) {
    return nullptr;
  }
}

int dpn_mor_m(DpnMor* h) { return h && h->mor ? h->mor->m() : 0; }

double dpn_mor_setup_s(DpnMor* h) { return h && h->mor ? h->mor->setup_s() : 0.0; }

const char* dpn_mor_name(DpnMor* h) { return h && h->mor ? h->mor->name() : ""; }

void dpn_mor_free(DpnMor* h) { delete h; }

int dpn_mor_timestep(DpnMor* h, const double* leak, const double* pad, double dt, double t_end,
                     double vdd, int n_events, const int* ev_idx, const double* ev_t50,
                     const double* ev_dur, const double* ev_ipulse, double* V_worst, int* worst_node,
                     double* worst_v, double* worst_t, double* rel_res_max, double* solve_s,
                     int max_steps, double* wave_t, double* wave_vmin, double* wave_itot,
                     int* n_steps) {
  if (!h || !h->mor || !leak || !pad || dt <= 0.0) {
    return -1;
  }
  try {
    auto ev = pack_events(n_events, ev_idx, ev_t50, ev_dur, ev_ipulse);
    auto r = h->mor->timestep(leak, pad, dt, t_end, vdd, ev.data(), static_cast<int>(ev.size()));
    return copy_tran(r, h->mor->n(), V_worst, worst_node, worst_v, worst_t, rel_res_max, solve_s,
                     max_steps, wave_t, wave_vmin, wave_itot, n_steps);
  } catch (...) {
    return -3;
  }
}

}  // extern "C"
