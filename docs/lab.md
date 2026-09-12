# Lab

The lab contains multi-fidelity DSE, PDN extraction, solver comparison,
thermal analysis, and optional PDK experiments. It reports observations; the
product comparator remains separate.

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/run_dse.py
python3 learn/scripts/validate_lab_physics.py
python3 learn/scripts/test_dse.py
```

Each invocation gets a unique directory under
`learn/sim/dse/live/`. Set `PD_FLOW_RUN_DIR` when several stages must share the
same run. A solver comparison is allowed only when the matrix, mesh,
activity, constraint, and geometry fingerprints agree.

Optional engines such as ngspice, Xyce, and FasterCap are detected at runtime.
Unavailable engines remain explicit gaps. No lab output is copied into a
product report without a compatible live contract.

ASAP7 is an independent exploratory track. It may produce live GDS and
signoff evidence, but its PDK and geometry contract must not be mixed with a
Nangate45 comparison.

The ASAP7+BSPDN Lab contract is documented in
[`asap7_eval_contract.md`](asap7_eval_contract.md), with the implementation
tracker at [`../bspdn/impl/BSPDN_IMPLEMENTATION_PLAN.md`](../bspdn/impl/BSPDN_IMPLEMENTATION_PLAN.md).
Ladder B starts with the explicit `asap7_bspdn_proxy_m89` PROXY mesh; thermal
GAP evidence is shown separately and never becomes Product signoff.
