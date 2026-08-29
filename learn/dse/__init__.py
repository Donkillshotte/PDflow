"""Multi-fidelity hardware DSE: memory, Pareto, layered search, physical oracles.

Levels stay separate (architecture / logic / synthesis / physical / pdn).
F4 Dynamic IR is an oracle, never a neural voltage map. Logic ops follow
the BOiLS standard alphabet. Architecture uses a datapath e-graph.
"""

from .layers import ADAPTERS
from .memory import DesignMemory, Candidate
from .metrics import QoR, pareto_front, dominates

__all__ = ["QoR", "pareto_front", "dominates", "DesignMemory", "Candidate", "ADAPTERS"]
