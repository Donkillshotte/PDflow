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
  std::vector<double> V_worst;
  std::vector<double> wave_t;
  std::vector<double> wave_vmin;
  std::vector<double> wave_itot;
};

/* Same triangle as learn/scripts/pdn_dynamic.py. */
double triangle(double t, double t50, double dur, double ipulse);

void fill_idraw(Index n, double t, const double* leak, const TriangleSrc* ev, int n_ev, double* I);

/* Fixed-Δt backward Euler on a pre-factored A = G + C/Δt.
   Matches the Python loop: IC V=Vdd, I(t) at the new time, then solve. */
TranResult timestep_be(Solver& solver, const Csr& A, const double* C, const double* leak,
                       const double* pad, double dt, double t_end, double vdd,
                       const TriangleSrc* ev, int n_ev);

/* Adaptive BE. Pad conductance is frozen at analysis Δt (R + L/Δt0) so shrinking
   the step does not open the package. True inductor MNA history is not in this slice.
   LTE ≈ ½|Δ²V| vs atol + rtol|V|. SparseLU only (AMG rebuild is too dear). */
TranResult timestep_be_adaptive(const Csr& Gmesh, const double* C, const Index* bumps, int n_bumps,
                                double pkg_r, double pkg_l, double vdd, const double* leak,
                                double dt0, double t_end, double atol, double rtol,
                                const TriangleSrc* ev, int n_ev);

Csr form_be_operator(const Csr& Gmesh, const double* C, double dt, const Index* bumps, int n_bumps,
                     double pkg_r, double pkg_l, std::vector<double>& pad, double vdd,
                     double dt_pkg = -1.0);

}  // namespace dpn
