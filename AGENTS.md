# AGENTS

These rules keep every result attributable to the design and tools that
produced it.

## Scope

- Treat every analysis as a fresh invocation.
- Store transient DSE data below `learn/sim/dse/live/<design>/<run-id>/` or an
  explicit `PD_FLOW_RUN_DIR` supplied by the caller.
- A comparison requires the same `run_id`, design, clock/constraint contract,
  geometry fingerprint, netlist fingerprint, mesh fingerprint, and activity
  scenario. Otherwise mark it unavailable.
- Reports must carry `comparison_scope`; use `same-live-invocation` for a
  comparison made inside one run.
- Missing tools or inputs produce `GAP`, `FAIL`, or `REFUSED`; never read an
  older report to make a green result.

## Safety

- Run one heavy EDA job at a time. Heavy wrappers default to 600 seconds and
  must keep their subprocess timeout aligned with that value.
- Never use `pkill -f`; terminate a known PID only.
- Do not overwrite a run directory while another job is active.
- Keep source RTL, generated netlists, reports, and logs attributable to the
  current run.

## Product and lab

- Product evaluation uses the official design contract and compares base and
  challenger artifacts emitted by the same invocation.
- Lab DSE proposes experiments; it does not turn a solver result into a
  product verdict.
- Physical changes that alter die geometry must be labelled as a geometry
  change, not treated as an apples-to-apples QoR improvement.
- `Candidate.knobs` records the action, `artifacts` the observation, `pred`
  the prediction, and `delta` only a declared compatible delta.

## Verification

```bash
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/test_dse.py
python3 learn/scripts/test_signoff_honesty.py
python3 learn/scripts/test_lab_physics.py
./scripts/test_course.sh
./scripts/test_all_phases.sh
```

Changes to Studio should also be checked with `npm run lint` and
`npm run build` from `studio/`.

When Symphony integration files change, also run
`./scripts/verify_symphony.sh` and
`PYTHONPATH=learn:learn/scripts python3 learn/scripts/test_symphony_workflow.py`.
