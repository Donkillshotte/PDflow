## Summary

What changed and why (one paragraph).

## Surface

- [ ] Product (physical knobs, official netlist, real finish)
- [ ] Lab (e-graph, rewrite, DSE, ASAP7 research)
- [ ] Course / Studio (lessons, FlowLab, teaching)

Do not mix surfaces in one PR unless the change is explicitly cross-cutting (docs, CI, install).

## Tests

```bash
# Fast gates (required)
./scripts/ci_fast_gates.sh

# If touching product DSE
PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_dse_next.py
```

## Metrics honesty

If comparing finishes, report **area, power, leakage, and IR** together. State win/lose honestly per [`learn/dse/win_rule.py`](learn/dse/win_rule.py).

## Checklist

- [ ] No `if design ==` in tuner/space/score/coordinator/transfer
- [ ] No cross-invocation report or fixed QoR value is used
- [ ] No writes to locked `flowlab` / `learn` product trees without explicit intent
- [ ] Docs updated if entry points changed
