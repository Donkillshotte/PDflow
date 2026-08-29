#pragma once

#include "dpn/csr.hpp"
#include "dpn/solvers.hpp"

#include <vector>

namespace dpn {

struct TriangleSrc {
  Index idx = 0;
  double t50 = 0.0;
  double dur = 0.0;
  double ipulse = 0.0;
};

struct TranResult {
  int steps = 0;
  Index worst_node = 0;
  double worst_v = 0.0;
  double worst_t = 0.0;
  double rel_res_max = 0.0;
  double solve_s = 0.0;
  double i_L_absmax = 0.0;
  std::vector<double> V_worst;
  std::vector<double> wave_t;
  std::vector<double> wave_vmin;
  std::vector<double> wave_itot;
  std::vector<double> i_L_worst;
};

/* Same triangle as learn/scripts/pdn_dynamic.py. */
double triangle(double t, double t50, double dur, double ipulse);

void fill_idraw(Index n, double t, const double* leak, const TriangleSrc* ev, int n_ev, double* I);

/* BE companion of series R+L: g_eq = 1/(R+L/Δt). i_hist scale = g_eq·L/Δt. */
void rl_companion(double pkg_r, double pkg_l, double dt, double* g_eq, double* hist_scale);

/* Fixed-Δt backward Euler on a pre-factored A = G + C/Δt.
   Matches the Python loop: IC V=Vdd, I(t) at the new time, then solve. */
TranResult timestep_be(Solver& solver, const Csr& A, const double* C, const double* leak,
                       const double* pad, double dt, double t_end, double vdd,
                       const TriangleSrc* ev, int n_ev);

/* Same A, but package R+L uses inductor current history (not memoryless L/Δt).
   A must already include g_eq on bump diagonals. bump_v[k] is the ideal source at bump k. */
TranResult timestep_be_hist(Solver& solver, const Csr& A, const double* C, const double* leak,
                            double dt, double t_end, const TriangleSrc* ev, int n_ev,
                            const Index* bumps, int n_bumps, const double* bump_v, double pkg_r,
                            double pkg_l);

/* Adaptive BE with RL history. g_eq follows the current Δt; i_L is the MNA state.
   LTE ≈ ½|Δ²V| vs atol + rtol|V|. SparseLU only. */
TranResult timestep_be_adaptive(const Csr& Gmesh, const double* C, const Index* bumps, int n_bumps,
                                const double* bump_v, double pkg_r, double pkg_l, double vdd,
                                const double* leak, double dt0, double t_end, double atol,
                                double rtol, const TriangleSrc* ev, int n_ev);

Csr form_be_operator(const Csr& Gmesh, const double* C, double dt, const Index* bumps, int n_bumps,
                     const double* bump_v, double pkg_r, double pkg_l, std::vector<double>& pad);

/* Fixed-Δt BE on the descriptor Eẋ + A x = u(t). E is diagonal (length n).
   n_v voltage states start at Vdd; inductor states (the rest) start at 0.
   die_idx>=0: scalar I_draw on that node. die_idx<0: I_draw[0:n_die] on the first n_die nodes.
   u[iv] += vdd (VRM inductor KVL). */
TranResult timestep_descriptor(const Csr& A, const double* E, double dt, double t_end, double vdd,
                               int n_v, int n_die, int die_idx, int iv, const double* leak,
                               const TriangleSrc* ev, int n_ev);

}  // namespace dpn
