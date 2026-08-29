#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct DpnHandle DpnHandle;
typedef struct DpnMor DpnMor;

/* kind: 0 = direct SparseLU, 1 = SA-AMG + CG, 2 = restricted additive Schwarz.
   rowptr has n+1 entries, col/val have nnz. Data is copied. */
DpnHandle* dpn_setup(int kind, int n, int nnz, const int* rowptr, const int* col,
                     const double* val);

/* Solve A x = b. x0 may be NULL. Returns 0 on success. relres may be NULL. */
int dpn_solve(DpnHandle* h, const double* b, double* x, const double* x0, double* relres);

int dpn_n(DpnHandle* h);
int dpn_n_levels(DpnHandle* h);
double dpn_setup_s(DpnHandle* h);
const char* dpn_name(DpnHandle* h);
void dpn_free(DpnHandle* h);

/* Fixed-Δt BE loop on a factored handle. wave_* must hold max_steps entries.
   Returns 0 on success. */
int dpn_timestep_be(DpnHandle* h, const double* C, const double* leak, const double* pad, double dt,
                    double t_end, double vdd, int n_events, const int* ev_idx, const double* ev_t50,
                    const double* ev_dur, const double* ev_ipulse, double* V_worst, int* worst_node,
                    double* worst_v, double* worst_t, double* rel_res_max, double* solve_s,
                    int max_steps, double* wave_t, double* wave_vmin, double* wave_itot,
                    int* n_steps);

/* BE with series R+L companion *and* inductor current history.
   A must include g_eq=1/(R+L/Δt) on bump diagonals. bump_v[n_bumps] are ideal sources. */
int dpn_timestep_be_hist(DpnHandle* h, const double* C, const double* leak, double dt, double t_end,
                         const int* bumps, int n_bumps, const double* bump_v, double pkg_r,
                         double pkg_l, int n_events, const int* ev_idx, const double* ev_t50,
                         const double* ev_dur, const double* ev_ipulse, double* V_worst,
                         int* worst_node, double* worst_v, double* worst_t, double* rel_res_max,
                         double* solve_s, int max_steps, double* wave_t, double* wave_vmin,
                         double* wave_itot, int* n_steps, double* i_L_absmax, double* i_L_worst);

/* Adaptive BE. G is the mesh without package pad. bumps[n_bumps] are V-source nodes.
   bump_v[n_bumps] are ideal sources (NULL → fill with vdd). */
int dpn_timestep_be_adaptive(int n, int nnz, const int* rowptr, const int* col, const double* Gval,
                             const double* C, const int* bumps, int n_bumps, const double* bump_v,
                             double pkg_r, double pkg_l, double vdd, const double* leak, double dt0,
                             double t_end,
                             double atol, double rtol, int n_events, const int* ev_idx,
                             const double* ev_t50, const double* ev_dur, const double* ev_ipulse,
                             double* V_worst, int* worst_node, double* worst_v, double* worst_t,
                             double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
                             double* wave_vmin, double* wave_itot, int* n_steps);

/* Rational Krylov MOR. starts is n × n_starts column-major. */
DpnMor* dpn_mor_setup(int n, int nnz, const int* rowptr, const int* col, const double* Gval,
                      const double* C, int n_starts, const double* starts, int n_shifts,
                      const double* shifts, int n_moments);
/* Descriptor RLC MOR: G is the mesh without pad stamp. starts is n × n_starts column-major
   (voltage ports). Unsymmetric A+sE (SparseLU). */
DpnMor* dpn_mor_setup_rlc(int n, int nnz, const int* rowptr, const int* col, const double* Gval,
                          const double* C, const int* bumps, int n_bumps, const double* bump_v,
                          double pkg_r, double pkg_l, int n_starts, const double* starts,
                          int n_shifts, const double* shifts, int n_moments);
int dpn_mor_m(DpnMor* h);
double dpn_mor_setup_s(DpnMor* h);
const char* dpn_mor_name(DpnMor* h);
void dpn_mor_free(DpnMor* h);
int dpn_mor_timestep(DpnMor* h, const double* leak, const double* pad, double dt, double t_end,
                     double vdd, int n_events, const int* ev_idx, const double* ev_t50,
                     const double* ev_dur, const double* ev_ipulse, double* V_worst, int* worst_node,
                     double* worst_v, double* worst_t, double* rel_res_max, double* solve_s,
                     int max_steps, double* wave_t, double* wave_vmin, double* wave_itot,
                     int* n_steps);

#ifdef __cplusplus
}
#endif
