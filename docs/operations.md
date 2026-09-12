# Operations

Use the local machine for reproducible, run-scoped analysis.

On a new workstation, the supported bootstrap is one command from the
repository root:

```bash
./install.sh --yes
pdflow
```

See [`installer.md`](installer.md) for the native dependency matrix and
recovery procedures.

PDflow's certified execution mode is native Linux host execution. Start every
shell session with the native environment and verify the six required EDA
tools before running a flow:

```bash
source scripts/native_eda_env.sh
./scripts/verify_native_eda.sh
```

```bash
export PYTHONPATH=learn:learn/scripts
export PD_FLOW_RUN_DIR="$PWD/learn/sim/dse/live/manual-run"
python3 learn/scripts/run_dse.py
```

Heavy wrappers use a 600-second default timeout. Set `PD_FLOW_TIMEOUT_S=600`
or a larger value only when the selected workflow explicitly needs it; the
process timeout must not be shorter than the solver timeout. Docker/cloud
execution is not a substitute for the native product path.

## Analysis Workbench operations

The Workbench is checkpoint-aware.  Select the design, PDK, stage, and
candidate context first; the agent then resolves the native artifacts and
evaluates the published check descriptors.  Opening a tab, inspector, report,
or viewer is read-only and never starts a process.

The UI's `Preview` action is equivalent to a read-only preflight of
`POST /api/analysis-bundles/preview`.  It expands a bundle into concrete
checks, prerequisites, native actions, resource limits, expected evidence,
and downstream invalidations.  Only `Confirm & queue` submits work through
the agent's single heavy-job queue.  The browser, Tauri shell, and CLI all use
this same boundary; none of them constructs a shell command from UI input.

Useful API examples (with the local agent already running) are:

```bash
curl -sS -H "Origin: http://127.0.0.1:43217" \
  -X POST -H 'Content-Type: application/json' \
  -d '{"bundle_id":"recommended","stage":"finish","variant":"flowlab"}' \
  http://127.0.0.1:43217/api/analysis-bundles/preview

curl -sS http://127.0.0.1:43217/api/analysis-runs?limit=20
```

Treat `GAP`, `PARTIAL`, `PROXY`, and `NOT_RUN` as actionable diagnostic
states, never as Product wins.  A completed native process can still have a
failed requirement (for example negative WNS); inspect the four status
dimensions and the report's input hashes before interpreting the result.

For a FlowLab edit, create a candidate run first.  Candidate dependency
closure is materialized atomically from the protected finish and subsequent
analysis inputs must resolve to that candidate.  The finish hash must remain
unchanged before and after the operation.  A candidate request referencing an
unknown or unpersisted run is refused rather than creating an untracked
workspace.

## Failure semantics

- `READY` means the current artifact was produced and validated.
- `GAP` means an optional engine or required input is unavailable.
- `FAIL` means the current tool ran and failed.
- `REFUSED` means the request violates the current tool contract.

`PROXY`, `PARTIAL`, and `GAP` are useful diagnostic outcomes but are never
Product signoff. A native executable can be `READY` while its current run
still returns `FAIL` because the design violates timing, DRC, LVS, IR, or
another required check.

Never convert `GAP` into a value by reading an older JSON or log. Keep the
input paths and fingerprints in the current report.

## Useful commands

```bash
./scripts/run_studio.sh
./scripts/test_course.sh
./scripts/test_all_phases.sh
timeout 600s ./scripts/test_native_rtl_e2e.sh
python3 learn/scripts/test_signoff_honesty.py
python3 learn/scripts/test_lab_physics.py
```
