# Live DSE reference

The DSE stack is multi-fidelity: architecture → logic → synthesis →
placement → routing → PDN. Each candidate stores the action, raw artifacts,
interpretation, prediction, and compatible deltas in separate fields.

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/run_dse.py
python3 learn/scripts/test_dse.py
```

An invocation owns its JSONL memory. Set `PD_FLOW_RUN_DIR` when several
commands are deliberately part of one experiment. A solver result may be
compared only when the design, constraints, netlist, geometry, mesh, activity
scenario, and run id agree. The lab can propose changes and label them
`READY`, `GAP`, `FAIL`, or `REFUSED`; product evaluation is a separate layer.

The native and Python solver paths are equivalent only when they consume the
same matrix and inputs. The report records which backend actually ran.
