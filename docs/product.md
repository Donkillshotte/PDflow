# Product comparison

Product experiments evaluate physical knobs and synthesis choices under one
explicit design contract. A run must emit both the same-run reference and
candidate reports before a verdict is calculated.

## Contract

The comparator checks, at minimum:

- same design and clock constraint;
- same RTL/netlist contract unless the experiment explicitly changes it;
- same die geometry for a physical-knob comparison;
- area, power, leakage, timing, and IR from compatible artifacts;
- one `run_id` and `comparison_scope` declaring the relationship.

If any required axis or fingerprint is missing, the result is `incomplete`,
not a win or loss. A geometry change is reported separately from a same-die
comparison. The implementation is [`learn/dse/win_rule.py`](../learn/dse/win_rule.py).

## Workflow

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/run_recipe_loop.py --dry-run
python3 learn/scripts/cook_recipe.py --design gcd --recipes place_sparse_setup
python3 learn/scripts/test_dse_next.py
```

The coordinator records only the current invocation. It does not infer a
verdict when the current run has not emitted both sides of a comparison.
