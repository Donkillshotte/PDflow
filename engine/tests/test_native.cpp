#include "dpn/c_api.h"
#include "dpn/csr.hpp"
#include "dpn/solvers.hpp"

#include <cmath>
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
  }
  {
    // 1-node implicit Euler: (g + c/dt) v = g*vdd - i + (c/dt) vprev
    const double vdd = 1.1, r = 2.0, c = 50e-12, dt = 10e-12, i = 5e-3;
    const double g = 1.0 / r;
    const double a = g + c / dt;
    const double vprev = vdd;
    const double rhs = g * vdd - i + (c / dt) * vprev;
    const double v_closed = rhs / a;
    int rowptr[2] = {0, 1};
    int col[1] = {0};
    double val[1] = {a};
    DpnHandle* h = dpn_setup(0, 1, 1, rowptr, col, val);
    check(h != nullptr, "c_api setup direct 1-node");
    double b = rhs, x = 0.0, rel = 0.0;
    check(dpn_solve(h, &b, &x, nullptr, &rel) == 0, "c_api solve 1-node");
    check(std::abs(x - v_closed) < 1e-12, "1-node BE matches closed form");
    dpn_free(h);
  }
  if (fails) {
    std::fprintf(stderr, "%d checks failed\n", fails);
    return 1;
  }
  std::printf("ALL dpn_test PASSED\n");
  return 0;
}
