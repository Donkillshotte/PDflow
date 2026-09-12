# DSE

The package has two contracts:

- product DSE evaluates same-invocation physical comparisons;
- lab DSE explores architecture, synthesis, place/route, PDN, and solvers.

Both contracts consume measurements emitted by the current invocation. Start
with [`../reference/live-analysis.md`](../reference/live-analysis.md).

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/run_dse.py
python3 learn/scripts/test_dse.py
```

`Candidate` keeps actions (`knobs`), observations (`artifacts`), predictions
(`pred`), and compatible deltas (`delta`) separate. Each live run has its own
JSONL memory. A caller can share a run explicitly with `PD_FLOW_RUN_DIR`.

The lab can mark optional solver/PDK stages `GAP`; it never fabricates a
missing measurement. The product layer requires matching geometry and
measurement provenance before it emits a verdict.
