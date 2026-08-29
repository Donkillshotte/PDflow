#pragma once

#include "dpn/csr.hpp"

#include <memory>
#include <string>
#include <vector>

namespace dpn {

class Solver {
 public:
  virtual ~Solver() = default;
  virtual void solve(const double* b, double* x, const double* x0) = 0;
  virtual const char* name() const = 0;
  virtual int n_levels() const { return 1; }
  virtual double setup_s() const { return setup_s_; }
  Index n() const { return n_; }
  double last_relres() const { return last_relres_; }

 protected:
  Index n_ = 0;
  double setup_s_ = 0.0;
  double last_relres_ = 0.0;
};

std::unique_ptr<Solver> make_direct(const Csr& A);
std::unique_ptr<Solver> make_amg(const Csr& A);
std::unique_ptr<Solver> make_ras(const Csr& A);
/* Eigen BiCGSTAB + ILUT (diag fallback). Unsymmetric CPU Krylov — not Ginkgo. */
std::unique_ptr<Solver> make_bicgstab(const Csr& A);

double residual_rel(const Csr& A, const double* x, const double* b);

}  // namespace dpn
