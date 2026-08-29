#pragma once

#include "dpn/csr.hpp"
#include "dpn/transient.hpp"

#include <memory>
#include <vector>

namespace dpn {

/* Rational Krylov model-order reduction for C dv/dt + G v = pad - I(t).
   Expansion points s_j, block starts B, moments of (G + s C)^{-1}.
   Integrates the deviation δv = v - Vdd (G Vdd = pad on this RC+pad model).
   Not a neural voltage map. Not Ginkgo. */
class RationalMor {
 public:
  RationalMor(const Csr& G, const double* C, int n_starts, const double* starts, int n_shifts,
              const double* shifts, int n_moments);

  TranResult timestep(const double* leak, const double* pad, double dt, double t_end, double vdd,
                      const TriangleSrc* ev, int n_ev) const;

  Index n() const { return n_; }
  int m() const { return m_; }
  double setup_s() const { return setup_s_; }
  const char* name() const { return "C_rational_krylov_mor"; }

 private:
  Index n_ = 0;
  int m_ = 0;
  double setup_s_ = 0.0;
  Csr G_;
  std::vector<double> C_;
  std::vector<double> V_;  // n × m, column-major, orthonormal
  std::vector<double> Gr_;  // m × m row-major
  std::vector<double> Cr_;
};

std::unique_ptr<RationalMor> make_mor(const Csr& G, const double* C, int n_starts,
                                      const double* starts, int n_shifts, const double* shifts,
                                      int n_moments);

}  // namespace dpn
