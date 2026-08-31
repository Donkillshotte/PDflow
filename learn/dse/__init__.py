"""Multi-fidelity hardware DSE: memory, Pareto, layered search, physical oracles.

Levels stay separate (architecture / logic / synthesis / physical / pdn).
F4 Dynamic IR is an oracle, never a neural voltage map. Logic ops follow
the BOiLS standard alphabet. Architecture uses a datapath e-graph.
"""

from .layers import ADAPTERS
from .memory import DesignMemory, Candidate
from .metrics import QoR, pareto_front, dominates, qor_delta, baseline_delta_of
from .resources import admit_solve
from .solve_result import SolveResult, normalize_solve, activity_status_of

__all__ = [
    "QoR",
    "pareto_front",
    "dominates",
    "qor_delta",
    "baseline_delta_of",
    "DesignMemory",
    "Candidate",
    "ADAPTERS",
    "SolveResult",
    "normalize_solve",
    "activity_status_of",
    "admit_solve",
]
