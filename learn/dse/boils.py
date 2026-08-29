"""BOiLS-style SSK-GP + EI, plus DRiLLS-style sequential append.

References (concepts, not a fork):
  BOiLS DATE'22 — subsequence kernel GP, trust-region, EI on ABC sequences
  DRiLLS     — sequential synthesis-op decisions (append one STD op)

This is the *logic* level only. Sequences are from BOILS_STD_OPS.
Physical / PDN knobs never enter the kernel.
"""

from __future__ import annotations

import math
import numpy as np

from .abc_space import BOILS_STD_OPS, CATALOG, subsequence_kernel
from .fingerprint import knobs_fp
from .memory import DesignMemory
from .policy import drills_propose


def ssk(a: list[str], b: list[str], ell: int = 3) -> float:
    return subsequence_kernel(a, b, ell=ell)


def _phi_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _phi_pdf(z: float) -> float:
    return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


def ei_min(mu: float, sigma: float, best: float, xi: float = 0.02) -> float:
    """Expected improvement for *minimization* (area)."""
    if sigma <= 1e-12:
        return 0.0
    z = (best - mu - xi) / sigma
    return float((best - mu - xi) * _phi_cdf(z) + sigma * _phi_pdf(z))


def gp_predict(
    train_seqs: list[list[str]],
    y: list[float],
    test_seqs: list[list[str]],
    noise: float = 2e-2,
    ell: int = 3,
) -> list[tuple[float, float]]:
    """Kernel ridge / GP posterior (mean, std) with a normalized SSK.

    n is small (tens). Numpy Cholesky; falls back to lstsq if K is singular.
    """
    n = len(train_seqs)
    if n == 0 or len(y) != n:
        return [(float("nan"), float("inf")) for _ in test_seqs]
    yv = np.asarray(y, dtype=float)
    ymean = float(yv.mean())
    ystd = float(yv.std()) if n > 1 else 1.0
    if ystd < 1e-9:
        ystd = 1.0
    yn = (yv - ymean) / ystd
    K = np.array([[ssk(a, b, ell) for b in train_seqs] for a in train_seqs], dtype=float)
    K = K + noise * np.eye(n)
    try:
        L = np.linalg.cholesky(K)
        chol = True
        alpha = np.linalg.solve(L.T, np.linalg.solve(L, yn))
    except np.linalg.LinAlgError:
        chol = False
        L = None
        alpha = np.linalg.lstsq(K, yn, rcond=None)[0]
    out: list[tuple[float, float]] = []
    for t in test_seqs:
        k = np.array([ssk(t, s, ell) for s in train_seqs], dtype=float)
        mu_n = float(k @ alpha)
        if chol and L is not None:
            v = np.linalg.solve(L, k)
            var_n = max(1e-6, 1.0 - float(v @ v))
        else:
            var_n = 0.25
        mu = mu_n * ystd + ymean
        std = math.sqrt(var_n) * ystd
        out.append((mu, std))
    return out


def catalog_knobs(spec: dict) -> dict:
    return {
        "name": spec["name"],
        "abc_args": list(spec["abc_args"]),
        "abc_ops": list(spec["abc_ops"]),
        "abc_script": "file",
    }


def _name_for(ops: list[str], prefix: str) -> str:
    if not ops:
        return f"{prefix}_empty"
    tail = "_".join(o.replace(" ", "")[:8] for o in ops[:5])
    return f"{prefix}_{tail}"[:48]


def generate_candidates(seen_ops: list[list[str]], best: list[str] | None) -> list[dict]:
    """Catalog leftovers + DRiLLS append + BOiLS trust-region mutations."""
    out: list[dict] = []
    for spec in CATALOG:
        out.append(catalog_knobs(spec))
    if best is not None:
        for op in BOILS_STD_OPS:
            seq = [*best, op]
            if len(seq) > 12:
                continue
            out.append(
                {
                    "name": _name_for(seq, "drills"),
                    "abc_args": [],
                    "abc_ops": seq,
                    "abc_script": "file",
                    "via": "drills_append",
                }
            )
        # Trust region: swap / insert / delete one op (BOiLS-style neighbourhood)
        for i, op in enumerate(best):
            for alt in BOILS_STD_OPS:
                if alt == op:
                    continue
                seq = list(best)
                seq[i] = alt
                out.append(
                    {
                        "name": _name_for(seq, "boils"),
                        "abc_args": [],
                        "abc_ops": seq,
                        "abc_script": "file",
                        "via": "trust_region_swap",
                    }
                )
        if len(best) >= 2:
            for i in range(len(best)):
                seq = list(best)
                seq.pop(i)
                out.append(
                    {
                        "name": _name_for(seq, "boils"),
                        "abc_args": [],
                        "abc_ops": seq,
                        "abc_script": "file",
                        "via": "trust_region_delete",
                    }
                )
        if len(best) < 12:
            for i in range(len(best) + 1):
                for alt in BOILS_STD_OPS:
                    seq = [*best[:i], alt, *best[i:]]
                    if len(seq) > 12:
                        continue
                    out.append(
                        {
                            "name": _name_for(seq, "boils"),
                            "abc_args": [],
                            "abc_ops": seq,
                            "abc_script": "file",
                            "via": "trust_region_insert",
                        }
                    )
    # de-dup by ops tuple + args
    uniq: dict[tuple, dict] = {}
    for k in out:
        key = (tuple(k["abc_ops"]), tuple(k["abc_args"]))
        uniq.setdefault(key, k)
    return list(uniq.values())


def propose_logic_boils(mem: DesignMemory, focus: str = "chip") -> dict | None:
    """Next logic knobs: DRiLLS UCB first, then EI on the SSK-GP."""
    seen_fp = mem.seen_knobs("logic")
    ok = [c for c in mem.by_level("logic") if c.status == "ok" and c.qor.area_um2 is not None]
    train_seqs = [list(c.knobs.get("abc_ops") or []) for c in ok]
    y = [float(c.qor.area_um2) for c in ok]
    best_seq = train_seqs[int(np.argmin(y))] if y else None
    pool = []
    if best_seq is not None:
        ucb = drills_propose(mem, best_seq, focus)
        if ucb and knobs_fp("logic", ucb) not in seen_fp:
            pool.append(ucb)
    for knobs in generate_candidates(train_seqs, best_seq):
        fp = knobs_fp("logic", knobs)
        if fp in seen_fp:
            continue
        pool.append(knobs)
    if not pool:
        return None
    if len(y) >= 2:
        preds = gp_predict(train_seqs, y, [list(k["abc_ops"]) for k in pool])
        best_y = min(y)
        scored = []
        for knobs, (mu, std) in zip(pool, preds):
            scored.append((ei_min(mu, std, best_y), -std, knobs, mu, std))
        scored.sort(key=lambda t: (-t[0], t[1]))
        pick = scored[0][2]
        pick = dict(pick)
        pick["acq"] = {
            "ei": scored[0][0],
            "mu": scored[0][3],
            "std": scored[0][4],
            "via": "ssk_gp_ei",
        }
        return pick
    # Cold start: unused catalog first (named), then lowest SSK to seen
    named = [k for k in pool if any(k["name"] == s["name"] for s in CATALOG)]
    if named:
        return named[0]
    from .abc_space import min_kernel_to_seen

    named_ops = [list(k["abc_ops"]) for k in pool]
    idx = int(np.argmin([min_kernel_to_seen(ops, train_seqs) for ops in named_ops])) if train_seqs else 0
    return pool[idx]


def should_pay_f1(pred: dict, best_area: float | None) -> tuple[bool, str]:
    """Skip F1 when even an optimistic F0 draw is worse than the incumbent."""
    if best_area is None or pred.get("mean") is None or pred.get("std") is None:
        return True, "no F0 confidence — pay F1"
    n = int(pred.get("n") or 0)
    if n < 3:
        return True, "n<3 — pay F1"
    optimistic = float(pred["mean"]) - 2.0 * float(pred["std"])
    if optimistic > float(best_area) * 1.05:
        return False, "F0 optimistic still worse than incumbent — skip F1"
    return True, "uncertainty or EI — pay F1"
