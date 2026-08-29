#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct DpnHandle DpnHandle;
typedef struct DpnMor DpnMor;

/* Storage index width in bits (64). Call this before dpn_setup to confirm ABI. */
int dpn_index_width(void);

/* kind: 0 = direct SparseLU, 1 = SA-AMG + CG, 2 = restricted additive Schwarz,
   3 = BiCGSTAB + ILUT (unsymmetric CPU Krylov; not Ginkgo).
   rowptr has n+1 entries, col/val have nnz. Indices are int64. Data is copied. */
DpnHandle* dpn_setup(int kind, int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                     const double* val);

/* Solve A x = b. x0 may be NULL. Returns 0 on success. relres may be NULL. */
int dpn_solve(DpnHandle* h, const double* b, double* x, const double* x0, double* relres);

int64_t dpn_n(DpnHandle* h);
int dpn_n_levels(DpnHandle* h);
double dpn_setup_s(DpnHandle* h);
const char* dpn_name(DpnHandle* h);
void dpn_free(DpnHandle* h);

/* Fixed-Δt BE loop on a factored handle. wave_* must hold max_steps entries.
   Returns 0 on success. */
int dpn_timestep_be(DpnHandle* h, const double* C, const double* leak, const double* pad, double dt,
                    double t_end, double vdd, int64_t n_events, const int64_t* ev_idx,
                    const double* ev_t50, const double* ev_dur, const double* ev_ipulse,
                    double* V_worst, int64_t* worst_node, double* worst_v, double* worst_t,
                    double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
                    double* wave_vmin, double* wave_itot, int64_t* n_steps);

/* BE with series R+L companion *and* inductor current history.
   A must include g_eq=1/(R+L/Δt) on bump diagonals. bump_v[n_bumps] are ideal sources. */
int dpn_timestep_be_hist(DpnHandle* h, const double* C, const double* leak, double dt, double t_end,
                         const int64_t* bumps, int64_t n_bumps, const double* bump_v, double pkg_r,
                         double pkg_l, int64_t n_events, const int64_t* ev_idx, const double* ev_t50,
                         const double* ev_dur, const double* ev_ipulse, double* V_worst,
                         int64_t* worst_node, double* worst_v, double* worst_t, double* rel_res_max,
                         double* solve_s, int max_steps, double* wave_t, double* wave_vmin,
                         double* wave_itot, int64_t* n_steps, double* i_L_absmax, double* i_L_worst);

/* Sparse-C BE with mixed-rail UIC. Cmat CSR (nnz_c=0 → diagonal C). n_rail0 splits VDD|VSS. */
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
                              int64_t* n_steps, double* i_L_absmax, double* i_L_worst);
int dpn_timestep_be_adaptive(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                             const double* Gval, const double* C, const int64_t* bumps,
                             int64_t n_bumps, const double* bump_v, double pkg_r, double pkg_l,
                             double vdd, const double* leak, double dt0, double t_end, double atol,
                             double rtol, int64_t n_events, const int64_t* ev_idx,
                             const double* ev_t50, const double* ev_dur, const double* ev_ipulse,
                             double* V_worst, int64_t* worst_node, double* worst_v, double* worst_t,
                             double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
                             double* wave_vmin, double* wave_itot, int64_t* n_steps);

/* Rational Krylov MOR. starts is n × n_starts column-major. */
DpnMor* dpn_mor_setup(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                      const double* Gval, const double* C, int n_starts, const double* starts,
                      int n_shifts, const double* shifts, int n_moments);
/* Descriptor RLC MOR: G is the mesh without pad stamp. starts is n × n_starts column-major
   (voltage ports). Unsymmetric A+sE (SparseLU). */
DpnMor* dpn_mor_setup_rlc(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                          const double* Gval, const double* C, const int64_t* bumps, int64_t n_bumps,
                          const double* bump_v, double pkg_r, double pkg_l, int n_starts,
                          const double* starts, int n_shifts, const double* shifts, int n_moments);
int dpn_mor_m(DpnMor* h);
double dpn_mor_setup_s(DpnMor* h);
const char* dpn_mor_name(DpnMor* h);
void dpn_mor_free(DpnMor* h);
int dpn_mor_timestep(DpnMor* h, const double* leak, const double* pad, double dt, double t_end,
                     double vdd, int64_t n_events, const int64_t* ev_idx, const double* ev_t50,
                     const double* ev_dur, const double* ev_ipulse, double* V_worst,
                     int64_t* worst_node, double* worst_v, double* worst_t, double* rel_res_max,
                     double* solve_s, int max_steps, double* wave_t, double* wave_vmin,
                     double* wave_itot, int64_t* n_steps);

/* Descriptor BE on Eẋ+Ax=u. E is diagonal length n. die_idx<0 ⇒ I on nodes 0..n_die-1. */
int dpn_timestep_descriptor(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                            const double* Aval, const double* E, int n_v, int n_die, int64_t die_idx,
                            int iv, double dt, double t_end, double vdd, const double* leak,
                            int64_t n_events, const int64_t* ev_idx, const double* ev_t50,
                            const double* ev_dur, const double* ev_ipulse, double* V_worst,
                            int64_t* worst_node, double* worst_v, double* worst_t,
                            double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
                            double* wave_vmin, double* wave_itot, int64_t* n_steps);

/* Descriptor BE with sparse E (CSR). iv[n_iv] get +Vdd. u_const may be NULL. SparseLU gold. */
int dpn_timestep_descriptor_gen(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                                const double* Aval, int64_t nnz_e, const int64_t* eptr,
                                const int64_t* eidx, const double* eval, int n_v, int n_die,
                                int64_t die_idx, int64_t n_iv, const int64_t* iv, double dt,
                                double t_end, double vdd, const double* leak, const double* u_const,
                                int64_t n_events, const int64_t* ev_idx, const double* ev_t50,
                                const double* ev_dur, const double* ev_ipulse, double* V_worst,
                                int64_t* worst_node, double* worst_v, double* worst_t,
                                double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
                                double* wave_vmin, double* wave_itot, int64_t* n_steps);

/* Same as gen; solver_kind 0=SparseLU, 2=RAS+GMRES, 3=BiCGSTAB. Never AMG. */
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
                                      int64_t* n_steps);

/* Adaptive Δt descriptor BE. LTE on voltage states. Not the fixed-Δt gold when L>0. */
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
                                     double* wave_vmin, double* wave_itot, int64_t* n_steps);

/* Sparse-E descriptor MOR. starts is n_v × n_starts column-major. */
DpnMor* dpn_mor_setup_gen(int64_t n, int64_t nnz, const int64_t* rowptr, const int64_t* col,
                          const double* Aval, int64_t nnz_e, const int64_t* eptr, const int64_t* eidx,
                          const double* eval, int n_v, int n_die, int64_t die_idx, int64_t n_iv,
                          const int64_t* iv, const double* u_const, int n_starts,
                          const double* starts, int n_shifts, const double* shifts, int n_moments);

/* Thermal BE C Ṫ + G T = P. A = G+C/Δt already in the handle. Tracks max ΔT, not min V.
   T0 may be NULL (UIC 0). n_track<=0 tracks all nodes. wave_* must hold max_steps. */
int dpn_timestep_thermal_be(DpnHandle* h, const double* C, const double* P, double dt, double t_end,
                            const double* T0, int64_t n_track, double* T_final, double* T_worst,
                            int64_t* worst_node, double* worst_T, double* worst_t,
                            double* rel_res_max, double* solve_s, int max_steps, double* wave_t,
                            double* wave_tmax, int64_t* n_steps);

#ifdef __cplusplus
}
#endif
