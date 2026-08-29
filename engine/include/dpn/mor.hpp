#pragma once

#include "dpn/csr.hpp"
#include "dpn/transient.hpp"

#include <memory>
#include <vector>

namespace dpn {

/* Rational Krylov MOR.
   RC mode: C dv/dt + G v = pad - I(t), deviation δv = v - Vdd.
   RLC mode: descriptor Eẋ + A x = u on x = [v; i_L].
   Stamp matches the BE companion: C v' + G v − i = −I, L i' + R i + v = Vsrc
   (A unsymmetric; (A+sE) via SparseLU, not AMG).
   Not a neural voltage map. Not Ginkgo. */
class RationalMor {
 public:
  RationalMor(const Csr& G, const double* C, int n_starts, const double* starts, int n_shifts,
              const double* shifts, int n_moments);

  RationalMor(const Csr& Gmesh, const double* C, const Index* bumps, int n_bumps,
              const double* bump_v, double pkg_r, double pkg_l, int n_starts, const double* starts,
              int n_shifts, const double* shifts, int n_moments);

  TranResult timestep(const double* leak, const double* pad, double dt, double t_end, double vdd,
                      const TriangleSrc* ev, int n_ev) const;

  Index n() const { return n_volt_; }
  int m() const { return m_; }
  double setup_s() const { return setup_s_; }
  const char* name() const { return rlc_ ? "C_rational_krylov_rlc" : "C_rational_krylov_mor"; }
  bool rlc() const { return rlc_; }

 private:
  void build_basis(const Csr& A, const double* Ediag, Index n_aug, int n_starts,
                   const double* starts_aug, int n_shifts, const double* shifts, int n_moments);

  Index n_volt_ = 0;
  Index n_aug_ = 0;
  int m_ = 0;
  double setup_s_ = 0.0;
  bool rlc_ = false;
  Csr A_;
  std::vector<double> Ediag_;
  std::vector<double> bump_v_;
  std::vector<double> V_;   /* n_aug × m column-major, orthonormal */
  std::vector<double> Ar_;  /* m × m row-major */
  std::vector<double> Er_;
};

std::unique_ptr<RationalMor> make_mor(const Csr& G, const double* C, int n_starts,
                                      const double* starts, int n_shifts, const double* shifts,
                                      int n_moments);

std::unique_ptr<RationalMor> make_mor_rlc(const Csr& Gmesh, const double* C, const Index* bumps,
                                          int n_bumps, const double* bump_v, double pkg_r,
                                          double pkg_l, int n_starts, const double* starts,
                                          int n_shifts, const double* shifts, int n_moments);

}  // namespace dpn
