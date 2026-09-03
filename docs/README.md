# Documentation

Single entry point. Frozen plans stay in their original files (`learn/dse/*.md`);
this tree is for navigation. Do not rewrite I1–I5 or §5 P0–P7.

## Three surfaces

| Surface | What it is | Where wins are decided |
|---|---|---|
| **Product** | Physical knobs on the official netlist, fixed die, real finish | [`win_rule.py`](../learn/dse/win_rule.py) · [`product.md`](product.md) |
| **Lab** | e-graph, Verilog rewrite, F4 IR, refine, GNN | [`learn/dse/README.md`](../learn/dse/README.md) (Lab section) |
| **Course / Studio** | RTL→GDS lessons, FlowLab, GUI | [`learn/README.md`](../learn/README.md) · [`studio/README.md`](../studio/README.md) |

Studio shows all three on one path (`/#story`, `GET /api/story`).
Wins stay in `win_rule.py`. Lab IR gold stays 45.298 mV.

## Reading order

### Product

1. [`product.md`](product.md) — constraints, win rule, cycle
2. [`operations.md`](operations.md) — commands, tests, refuse rules
3. [`results.md`](results.md) — honest results
4. [`../learn/dse/tpe_plan.md`](../learn/dse/tpe_plan.md) — tuner (frozen before trials)
5. [`../learn/dse/arch_review.md`](../learn/dse/arch_review.md) — after gcd/ibex/aes: walls and transfer

### Lab

1. [`lab.md`](lab.md)
2. [`../PLAN.md`](../PLAN.md) — Phase 2 IR controller (closed)
3. [`../learn/reference/dse.md`](../learn/reference/dse.md) — F0–F6 stack
4. [`../engine/README.md`](../engine/README.md) — native solvers

### Course / Studio

1. [`course.md`](course.md)
2. [`../learn/README.md`](../learn/README.md) · [`../learn/CURRICULUM.md`](../learn/CURRICULUM.md)
3. [`../studio/README.md`](../studio/README.md)

## Repository map

- [`install.md`](install.md) — environment setup, tool versions, GCD flow launcher
- [`architecture.md`](architecture.md) — directories, ownership, what not to move
- [`script.md`](script.md) — wrappers in `scripts/` and `learn/scripts/`
- [`plans.md`](plans.md) — frozen plan index
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — how to contribute
- [`../AGENTS.md`](../AGENTS.md) — operational rules for agents
- [`../learn/reference/suite-status.md`](../learn/reference/suite-status.md) — live flow WORKS / FAIL / GAP table

## Product code

Module map: [`learn/dse/README.md`](../learn/dse/README.md).
