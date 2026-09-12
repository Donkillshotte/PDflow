# Product DSE contract

Product DSE evaluates a base and one or more challengers emitted by the same
live invocation. It is intentionally separate from the lab controller and
from the teaching FlowLab.

## Required identity

Every candidate comparison must carry a shared `run_id`, design id, clock and
constraint contract, netlist/RTL fingerprint, geometry fingerprint, and
compatible metric provenance. Missing or incompatible data yields
`incomplete`.

The same-die comparator evaluates timing, area, power, leakage, and IR. A die
or shape change is a geometry change and cannot be presented as an ordinary
QoR win. No result is inferred from files outside the current run directory.

## Entrypoints

- `cook.py` — execute one explicitly requested live recipe.
- `run_recipe_loop.py` — coordinate current candidates.
- `run_tpe.py` — optional current-run tuner.
- `win_rule.py` — calculate a verdict only after contract validation.
- `f6_finish.py` — parse current ORFS finish artifacts.

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/run_recipe_loop.py --dry-run
python3 learn/scripts/test_dse_next.py
```

Transient records belong under `learn/sim/dse/live/<design>/<run-id>/`.
