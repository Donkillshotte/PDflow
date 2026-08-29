#include "dpn/c_api.h"

#include "dpn/csr.hpp"
#include "dpn/mor.hpp"
#include "dpn/solvers.hpp"
#include "dpn/transient.hpp"

#include <algorithm>
#include <climits>
#include <cstdint>
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

int n_ev_ok(int64_t n_events) {
  if (n_events < 0) {
    return -1;
  }
  if (n_events > static_cast<int64_t>(INT_MAX)) {
    return -1;
  }
  return static_cast<int>(n_events);
}

std::vector<dpn::TriangleSrc> pack_events(int64_t n_events, const int64_t* ev_idx, const double* ev_t50,
                                         const double* ev_dur, const double* ev_ipulse) {
  const int ne = n_ev_ok(n_events);
  std::vector<dpn::TriangleSrc> ev(static_cast<size_t>(std::max(ne, 0)));
  for (int i = 0; i < ne; ++i) {
    ev[i].idx = ev_idx ? static_cast<dpn::Index>(ev_idx[i]) : 0;
    ev[i].t50 = ev_t50 ? ev_t50[i] : 0.0;
    ev[i].dur = ev_dur ? ev_dur[i] : 0.0;
    ev[i].ipulse = ev_ipulse ? ev_ipulse[i] : 0.0;
  }
  return ev;
}

int copy_tran(const dpn::TranResult& r, int64_t n, double* V_worst, int64_t* worst_node,
              double* worst_v, double* worst_t, double* rel_res_max, double* solve_s, int max_steps,
              double* wave_t, double* wave_vmin, double* wave_itot, int64_t* n_steps) {
  if (worst_node) {
    *worst_node = static_cast<int64_t>(r.worst_node);
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
    const int64_t nn = static_cast<int64_t>(r.V_worst.size());
    for (int64_t i = 0; i < n && i < nn; ++i) {
      V_worst[i] = r.V_worst[static_cast<size_t>(i)];
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

int run_descriptor_from_c(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                          const double* Aval, int64_t nnz_e, const int64_t* eptr, const int64_t* eidx,
                          const double* eval, int n_v, int n_die, int64_t die_idx, int64_t n_iv,
                          const int64_t* iv, double dt, double t_end, double vdd, const double* leak,
                          const double* u_const, int solver_kind, int adaptive, double atol,
                          double rtol, int64_t n_events, const int64_t* ev_idx, const double* ev_t50,
                          const double* ev_dur, const double* ev_ipulse, double* V_worst,
                          int64_t* worst_node, double* worst_v, double* worst_t, double* rel_res_max,
                          double* solve_s, int max_steps, double* wave_t, double* wave_vmin,
                          double* wave_itot, int64_t* n_steps) {
  if (!rowptr || !eptr || n <= 0 || dt <= 0.0 || n_v <= 0 || rowptr[n] != nnz || eptr[n] != nnz_e ||
      n_ev_ok(n_events) < 0) {
    return -1;
  }
  if (nnz > 0 && (!col || !Aval)) {
    return -1;
  }
  if (nnz_e > 0 && (!eidx || !eval)) {
    return -1;
  }
  if (n_iv < 0 || (n_iv > 0 && !iv)) {
    return -1;
  }
  if (n_iv > static_cast<int64_t>(INT_MAX)) {
    return -1;
  }
  if (solver_kind != 0 && solver_kind != 2 && solver_kind != 3) {
    return -1;  // AMG (kind=1) is SPD-companion only; descriptor K is unsymmetric.
  }
  try {
    dpn::Csr A = dpn::from_csr(static_cast<dpn::Index>(n), rowptr, col, Aval);
    dpn::Csr E = dpn::from_csr(static_cast<dpn::Index>(n), eptr, eidx, eval);
    auto ev = pack_events(n_events, ev_idx, ev_t50, ev_dur, ev_ipulse);
    dpn::TranResult r;
    if (adaptive) {
      r = dpn::timestep_descriptor_adaptive(
          A, E, dt, t_end, vdd, n_v, n_die, static_cast<dpn::Index>(die_idx), iv,
          static_cast<int>(n_iv), leak, u_const, atol, rtol, ev.data(), static_cast<int>(ev.size()),
          solver_kind);
    } else {
      r = dpn::timestep_descriptor_gen(A, E, dt, t_end, vdd, n_v, n_die,
                                       static_cast<dpn::Index>(die_idx), iv, static_cast<int>(n_iv),
                                       leak, u_const, ev.data(), static_cast<int>(ev.size()),
                                       solver_kind);
    }
    const int64_t n_out = (die_idx >= 0) ? 1 : static_cast<int64_t>(std::max(n_die, 0));
    return copy_tran(r, n_out > 0 ? n_out : n, V_worst, worst_node, worst_v, worst_t, rel_res_max,
                     solve_s, max_steps, wave_t, wave_vmin, wave_itot, n_steps);
  } catch (...) {
    return -3;
  }
}

}  // namespace

extern "C" {

int dpn_index_width(void) { return static_cast<int>(8 * sizeof(dpn::Index)); }

DpnHandle* dpn_setup(int kind, int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                     const double* val) {
  if (!rowptr || n <= 0 || nnz < 0 || rowptr[n] != nnz) {
    return nullptr;
  }
  if (nnz > 0 && (!col || !val)) {
    return nullptr;
  }
  try {
    auto* h = new DpnHandle();
    h->A = dpn::from_csr(static_cast<dpn::Index>(n), rowptr, col, val);
    if (kind == 1) {
      h->solver = dpn::make_amg(h->A);
    } else if (kind == 2) {
      h->solver = dpn::make_ras(h->A);
    } else if (kind == 3) {
      h->solver = dpn::make_bicgstab(h->A);
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

int64_t dpn_n(DpnHandle* h) { return h && h->solver ? static_cast<int64_t>(h->solver->n()) : 0; }

int dpn_n_levels(DpnHandle* h) { return h && h->solver ? h->solver->n_levels() : 0; }

double dpn_setup_s(DpnHandle* h) { return h && h->solver ? h->solver->setup_s() : 0.0; }

const char* dpn_name(DpnHandle* h) { return h && h->solver ? h->solver->name() : ""; }

void dpn_free(DpnHandle* h) { delete h; }

int dpn_timestep_be(DpnHandle* h, const double* C, const double* leak, const double* pad, double dt,
                    double t_end, double vdd, int64_t n_events, const int64_t* ev_idx,
                    const double* ev_t50, const double* ev_dur, const double* ev_ipulse,
                    double* V_worst, int64_t* worst_node, double* worst_v, double* worst_t,
                    double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
                    double* wave_vmin, double* wave_itot, int64_t* n_steps) {
  if (!h || !h->solver || !C || !leak || !pad || dt <= 0.0 || n_ev_ok(n_events) < 0) {
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

int dpn_timestep_be_hist(DpnHandle* h, const double* C, const double* leak, double dt, double t_end,
                         const int64_t* bumps, int64_t n_bumps, const double* bump_v, double pkg_r,
                         double pkg_l, int64_t n_events, const int64_t* ev_idx, const double* ev_t50,
                         const double* ev_dur, const double* ev_ipulse, double* V_worst,
                         int64_t* worst_node, double* worst_v, double* worst_t, double* rel_res_max,
                         double* solve_s, int max_steps, double* wave_t, double* wave_vmin,
                         double* wave_itot, int64_t* n_steps, double* i_L_absmax, double* i_L_worst) {
  if (!h || !h->solver || !C || !leak || dt <= 0.0 || n_bumps <= 0 || !bumps || !bump_v ||
      n_ev_ok(n_events) < 0) {
    return -1;
  }
  if (n_bumps > static_cast<int64_t>(INT_MAX)) {
    return -1;
  }
  try {
    auto ev = pack_events(n_events, ev_idx, ev_t50, ev_dur, ev_ipulse);
    auto r = dpn::timestep_be_hist(*h->solver, h->A, C, leak, dt, t_end, ev.data(),
                                   static_cast<int>(ev.size()), bumps, static_cast<int>(n_bumps),
                                   bump_v, pkg_r, pkg_l);
    if (i_L_absmax) {
      *i_L_absmax = r.i_L_absmax;
    }
    if (i_L_worst) {
      const int64_t nb = static_cast<int64_t>(r.i_L_worst.size());
      for (int64_t i = 0; i < n_bumps && i < nb; ++i) {
        i_L_worst[i] = r.i_L_worst[static_cast<size_t>(i)];
      }
    }
    return copy_tran(r, h->solver->n(), V_worst, worst_node, worst_v, worst_t, rel_res_max, solve_s,
                     max_steps, wave_t, wave_vmin, wave_itot, n_steps);
  } catch (...) {
    return -3;
  }
}

int dpn_timestep_be_hist_cmat(DpnHandle* h, const double* C, int64_t nnz_c, const int64_t* cptr,
                              const int64_t* cidx, const double* cval, const double* leak, double dt,
                              double t_end, const int64_t* bumps, int64_t n_bumps,
                              const double* bump_v, double pkg_r, double pkg_l, const double* v_init,
                              int64_t n_rail0, int64_t n_events, const int64_t* ev_idx,
                              const double* ev_t50, const double* ev_dur, const double* ev_ipulse,
                              double* V_worst, int64_t* worst_node, double* worst_v, double* worst_t,
                              double* V_worst_rail1, int64_t* worst_node_rail1, double* worst_v_rail1,
                              double* worst_t_rail1, double* rel_res_max, double* solve_s,
                              int max_steps, double* wave_t, double* wave_vmin, double* wave_itot,
                              int64_t* n_steps, double* i_L_absmax, double* i_L_worst) {
  if (!h || !h->solver || !C || !leak || dt <= 0.0 || n_bumps <= 0 || !bumps || !bump_v ||
      n_ev_ok(n_events) < 0 || nnz_c < 0 || n_rail0 < 0) {
    return -1;
  }
  if (n_bumps > static_cast<int64_t>(INT_MAX)) {
    return -1;
  }
  const int64_t n = h->solver->n();
  if (nnz_c > 0 && (!cptr || cptr[n] != nnz_c || (nnz_c > 0 && (!cidx || !cval)))) {
    return -1;
  }
  try {
    auto ev = pack_events(n_events, ev_idx, ev_t50, ev_dur, ev_ipulse);
    dpn::Csr Cmat;
    const dpn::Csr* Cptr = nullptr;
    if (nnz_c > 0) {
      Cmat = dpn::from_csr(static_cast<dpn::Index>(n), cptr, cidx, cval);
      Cptr = &Cmat;
    }
    auto r = dpn::timestep_be_hist(*h->solver, h->A, C, leak, dt, t_end, ev.data(),
                                   static_cast<int>(ev.size()), bumps, static_cast<int>(n_bumps),
                                   bump_v, pkg_r, pkg_l, Cptr, v_init,
                                   static_cast<dpn::Index>(n_rail0));
    if (i_L_absmax) {
      *i_L_absmax = r.i_L_absmax;
    }
    if (i_L_worst) {
      const int64_t nb = static_cast<int64_t>(r.i_L_worst.size());
      for (int64_t i = 0; i < n_bumps && i < nb; ++i) {
        i_L_worst[i] = r.i_L_worst[static_cast<size_t>(i)];
      }
    }
    if (worst_node_rail1) {
      *worst_node_rail1 = static_cast<int64_t>(r.worst_node_rail1);
    }
    if (worst_v_rail1) {
      *worst_v_rail1 = r.worst_v_rail1;
    }
    if (worst_t_rail1) {
      *worst_t_rail1 = r.worst_t_rail1;
    }
    if (V_worst_rail1) {
      const int64_t nn = static_cast<int64_t>(r.V_worst_rail1.size());
      for (int64_t i = 0; i < n && i < nn; ++i) {
        V_worst_rail1[i] = r.V_worst_rail1[static_cast<size_t>(i)];
      }
    }
    return copy_tran(r, n, V_worst, worst_node, worst_v, worst_t, rel_res_max, solve_s, max_steps,
                     wave_t, wave_vmin, wave_itot, n_steps);
  } catch (...) {
    return -3;
  }
}

int dpn_timestep_be_adaptive(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                             const double* Gval, const double* C, const int64_t* bumps,
                             int64_t n_bumps, const double* bump_v, double pkg_r, double pkg_l,
                             double vdd, const double* leak, double dt0, double t_end, double atol,
                             double rtol, int64_t n_events, const int64_t* ev_idx,
                             const double* ev_t50, const double* ev_dur, const double* ev_ipulse,
                             double* V_worst, int64_t* worst_node, double* worst_v, double* worst_t,
                             double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
                             double* wave_vmin, double* wave_itot, int64_t* n_steps) {
  if (!rowptr || !C || !leak || n <= 0 || dt0 <= 0.0 || n_ev_ok(n_events) < 0) {
    return -1;
  }
  if (nnz > 0 && (!col || !Gval)) {
    return -1;
  }
  if (n_bumps > static_cast<int64_t>(INT_MAX)) {
    return -1;
  }
  try {
    dpn::Csr G = dpn::from_csr(static_cast<dpn::Index>(n), rowptr, col, Gval);
    auto ev = pack_events(n_events, ev_idx, ev_t50, ev_dur, ev_ipulse);
    const int nb = static_cast<int>(std::max(n_bumps, int64_t{0}));
    std::vector<double> vs(static_cast<size_t>(nb), vdd);
    if (bump_v) {
      for (int k = 0; k < nb; ++k) {
        vs[static_cast<size_t>(k)] = bump_v[k];
      }
    }
    auto r = dpn::timestep_be_adaptive(G, C, bumps, nb, vs.data(), pkg_r, pkg_l, vdd, leak, dt0,
                                       t_end, atol, rtol, ev.data(), static_cast<int>(ev.size()));
    return copy_tran(r, n, V_worst, worst_node, worst_v, worst_t, rel_res_max, solve_s, max_steps,
                     wave_t, wave_vmin, wave_itot, n_steps);
  } catch (...) {
    return -3;
  }
}

DpnMor* dpn_mor_setup(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                      const double* Gval, const double* C, int n_starts, const double* starts,
                      int n_shifts, const double* shifts, int n_moments) {
  if (!rowptr || !C || !starts || !shifts || n <= 0 || n_starts <= 0 || n_shifts <= 0 ||
      rowptr[n] != nnz) {
    return nullptr;
  }
  if (nnz > 0 && (!col || !Gval)) {
    return nullptr;
  }
  try {
    auto* h = new DpnMor();
    dpn::Csr G = dpn::from_csr(static_cast<dpn::Index>(n), rowptr, col, Gval);
    h->mor = dpn::make_mor(G, C, n_starts, starts, n_shifts, shifts, n_moments);
    return h;
  } catch (...) {
    return nullptr;
  }
}

DpnMor* dpn_mor_setup_rlc(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                          const double* Gval, const double* C, const int64_t* bumps, int64_t n_bumps,
                          const double* bump_v, double pkg_r, double pkg_l, int n_starts,
                          const double* starts, int n_shifts, const double* shifts, int n_moments) {
  if (!rowptr || !C || !starts || !shifts || n <= 0 || n_starts <= 0 || n_shifts <= 0 ||
      n_bumps <= 0 || !bumps || !bump_v || rowptr[n] != nnz) {
    return nullptr;
  }
  if (nnz > 0 && (!col || !Gval)) {
    return nullptr;
  }
  if (n_bumps > static_cast<int64_t>(INT_MAX)) {
    return nullptr;
  }
  try {
    auto* h = new DpnMor();
    dpn::Csr G = dpn::from_csr(static_cast<dpn::Index>(n), rowptr, col, Gval);
    h->mor = dpn::make_mor_rlc(G, C, bumps, static_cast<int>(n_bumps), bump_v, pkg_r, pkg_l, n_starts,
                               starts, n_shifts, shifts, n_moments);
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
                     double vdd, int64_t n_events, const int64_t* ev_idx, const double* ev_t50,
                     const double* ev_dur, const double* ev_ipulse, double* V_worst,
                     int64_t* worst_node, double* worst_v, double* worst_t, double* rel_res_max,
                     double* solve_s, int max_steps, double* wave_t, double* wave_vmin,
                     double* wave_itot, int64_t* n_steps) {
  if (!h || !h->mor || !leak || dt <= 0.0 || n_ev_ok(n_events) < 0) {
    return -1;
  }
  if (!pad && !h->mor->rlc()) {
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

int dpn_timestep_descriptor(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                            const double* Aval, const double* E, int n_v, int n_die, int64_t die_idx,
                            int iv, double dt, double t_end, double vdd, const double* leak,
                            int64_t n_events, const int64_t* ev_idx, const double* ev_t50,
                            const double* ev_dur, const double* ev_ipulse, double* V_worst,
                            int64_t* worst_node, double* worst_v, double* worst_t,
                            double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
                            double* wave_vmin, double* wave_itot, int64_t* n_steps) {
  if (!rowptr || !E || n <= 0 || dt <= 0.0 || n_v <= 0 || rowptr[n] != nnz || n_ev_ok(n_events) < 0) {
    return -1;
  }
  if (nnz > 0 && (!col || !Aval)) {
    return -1;
  }
  try {
    dpn::Csr A = dpn::from_csr(static_cast<dpn::Index>(n), rowptr, col, Aval);
    auto ev = pack_events(n_events, ev_idx, ev_t50, ev_dur, ev_ipulse);
    auto r = dpn::timestep_descriptor(A, E, dt, t_end, vdd, n_v, n_die,
                                      static_cast<dpn::Index>(die_idx), iv, leak, ev.data(),
                                      static_cast<int>(ev.size()));
    const int64_t n_out = (die_idx >= 0) ? 1 : static_cast<int64_t>(std::max(n_die, 0));
    return copy_tran(r, n_out > 0 ? n_out : n, V_worst, worst_node, worst_v, worst_t, rel_res_max,
                     solve_s, max_steps, wave_t, wave_vmin, wave_itot, n_steps);
  } catch (...) {
    return -3;
  }
}

int dpn_timestep_descriptor_gen(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                                const double* Aval, int64_t nnz_e, const int64_t* eptr,
                                const int64_t* eidx, const double* eval, int n_v, int n_die,
                                int64_t die_idx, int64_t n_iv, const int64_t* iv, double dt,
                                double t_end, double vdd, const double* leak, const double* u_const,
                                int64_t n_events, const int64_t* ev_idx, const double* ev_t50,
                                const double* ev_dur, const double* ev_ipulse, double* V_worst,
                                int64_t* worst_node, double* worst_v, double* worst_t,
                                double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
                                double* wave_vmin, double* wave_itot, int64_t* n_steps) {
  return run_descriptor_from_c(n, nnz, rowptr, col, Aval, nnz_e, eptr, eidx, eval, n_v, n_die,
                               die_idx, n_iv, iv, dt, t_end, vdd, leak, u_const, 0, 0, 0.0, 0.0,
                               n_events, ev_idx, ev_t50, ev_dur, ev_ipulse, V_worst, worst_node,
                               worst_v, worst_t, rel_res_max, solve_s, max_steps, wave_t, wave_vmin,
                               wave_itot, n_steps);
}

int dpn_timestep_descriptor_workhorse(int64_t n, int64_t nnz, const int64_t* rowptr,
                                      const int64_t* col, const double* Aval, int64_t nnz_e,
                                      const int64_t* eptr, const int64_t* eidx, const double* eval,
                                      int n_v, int n_die, int64_t die_idx, int64_t n_iv,
                                      const int64_t* iv, double dt, double t_end, double vdd,
                                      const double* leak, const double* u_const, int solver_kind,
                                      int64_t n_events, const int64_t* ev_idx, const double* ev_t50,
                                      const double* ev_dur, const double* ev_ipulse, double* V_worst,
                                      int64_t* worst_node, double* worst_v, double* worst_t,
                                      double* rel_res_max, double* solve_s, int max_steps,
                                      double* wave_t, double* wave_vmin, double* wave_itot,
                                      int64_t* n_steps) {
  return run_descriptor_from_c(n, nnz, rowptr, col, Aval, nnz_e, eptr, eidx, eval, n_v, n_die,
                               die_idx, n_iv, iv, dt, t_end, vdd, leak, u_const, solver_kind, 0, 0.0,
                               0.0, n_events, ev_idx, ev_t50, ev_dur, ev_ipulse, V_worst, worst_node,
                               worst_v, worst_t, rel_res_max, solve_s, max_steps, wave_t, wave_vmin,
                               wave_itot, n_steps);
}

int dpn_timestep_descriptor_adaptive(int64_t n, int64_t nnz, const int64_t* rowptr,
                                     const int64_t* col, const double* Aval, int64_t nnz_e,
                                     const int64_t* eptr, const int64_t* eidx, const double* eval,
                                     int n_v, int n_die, int64_t die_idx, int64_t n_iv,
                                     const int64_t* iv, double dt0, double t_end, double vdd,
                                     const double* leak, const double* u_const, double atol,
                                     double rtol, int64_t n_events, const int64_t* ev_idx,
                                     const double* ev_t50, const double* ev_dur,
                                     const double* ev_ipulse, double* V_worst, int64_t* worst_node,
                                     double* worst_v, double* worst_t, double* rel_res_max,
                                     double* solve_s, int max_steps, double* wave_t,
                                     double* wave_vmin, double* wave_itot, int64_t* n_steps) {
  return run_descriptor_from_c(n, nnz, rowptr, col, Aval, nnz_e, eptr, eidx, eval, n_v, n_die,
                               die_idx, n_iv, iv, dt0, t_end, vdd, leak, u_const, 0, 1, atol, rtol,
                               n_events, ev_idx, ev_t50, ev_dur, ev_ipulse, V_worst, worst_node,
                               worst_v, worst_t, rel_res_max, solve_s, max_steps, wave_t, wave_vmin,
                               wave_itot, n_steps);
}

DpnMor* dpn_mor_setup_gen(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                          const double* Aval, int64_t nnz_e, const int64_t* eptr, const int64_t* eidx,
                          const double* eval, int n_v, int n_die, int64_t die_idx, int64_t n_iv,
                          const int64_t* iv, const double* u_const, int n_starts,
                          const double* starts, int n_shifts, const double* shifts, int n_moments) {
  if (!rowptr || !eptr || !starts || !shifts || n <= 0 || n_v <= 0 || n_starts <= 0 || n_shifts <= 0 ||
      rowptr[n] != nnz || eptr[n] != nnz_e) {
    return nullptr;
  }
  if (nnz > 0 && (!col || !Aval)) {
    return nullptr;
  }
  if (nnz_e > 0 && (!eidx || !eval)) {
    return nullptr;
  }
  if (n_iv < 0 || (n_iv > 0 && !iv)) {
    return nullptr;
  }
  if (n_iv > static_cast<int64_t>(INT_MAX) || n_v > n) {
    return nullptr;
  }
  try {
    auto* h = new DpnMor();
    dpn::Csr A = dpn::from_csr(static_cast<dpn::Index>(n), rowptr, col, Aval);
    dpn::Csr E = dpn::from_csr(static_cast<dpn::Index>(n), eptr, eidx, eval);
    h->mor = dpn::make_mor_gen(A, E, n_v, n_die, static_cast<dpn::Index>(die_idx), iv,
                               static_cast<int>(n_iv), u_const, n_starts, starts, n_shifts, shifts,
                               n_moments);
    return h;
  } catch (...) {
    return nullptr;
  }
}

int dpn_timestep_thermal_be(DpnHandle* h, const double* C, const double* P, double dt, double t_end,
                            const double* T0, int64_t n_track, double* T_final, double* T_worst,
                            int64_t* worst_node, double* worst_T, double* worst_t,
                            double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
                            double* wave_tmax, int64_t* n_steps) {
  if (!h || !h->solver || !C || !P || dt <= 0.0 || n_track < 0) {
    return -1;
  }
  try {
    auto r = dpn::timestep_thermal_be(*h->solver, h->A, C, P, dt, t_end, T0,
                                      static_cast<dpn::Index>(n_track));
    const int64_t n = h->solver->n();
    if (worst_node) {
      *worst_node = static_cast<int64_t>(r.worst_node);
    }
    if (worst_T) {
      *worst_T = r.worst_T;
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
    if (T_final) {
      const int64_t nf = static_cast<int64_t>(r.T_final.size());
      for (int64_t i = 0; i < n && i < nf; ++i) {
        T_final[i] = r.T_final[static_cast<size_t>(i)];
      }
    }
    if (T_worst) {
      const int64_t nw = static_cast<int64_t>(r.T_worst.size());
      for (int64_t i = 0; i < n && i < nw; ++i) {
        T_worst[i] = r.T_worst[static_cast<size_t>(i)];
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
        wave_t[i] = r.wave_t[static_cast<size_t>(i)];
      }
      if (wave_tmax) {
        wave_tmax[i] = r.wave_tmax[static_cast<size_t>(i)];
      }
    }
    return 0;
  } catch (...) {
    return -3;
  }
}

}  // extern "C"
