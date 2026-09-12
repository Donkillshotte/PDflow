# FlowLab candidate workspaces

FlowLab finish artifacts are canonical, immutable references. A native ORFS
recook must never write into `tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab`.
When a canonical finish exists, PDflow therefore refuses an unscoped stage
recook with `GAP` and explains that an isolated candidate run is required.

## Starting a candidate recook

From FlowLab, choose **Start isolated candidate recook** in the read-only finish
banner. PDflow creates a run-scoped workspace under:

```text
.pdflow/runs/<run_id>/candidate/orfs/
```

The local agent snapshots the FlowLab RTL and parameters, resolves the native
toolchain, and executes the requested stage with structured arguments. The
candidate workspace is the only writable FlowLab output root for that run.

The UI labels the active workspace as **CANDIDATE · EDITABLE** and keeps the
canonical finish visible as **FINISH · READ ONLY**. Candidate results, reports,
logs, hashes, and revisions are filtered by `run_id`; they must not silently
fall back to the canonical result tree.

## Supported behavior

- Candidate FlowLab stages are `synth`, `floorplan`, `gridcheck`, `place`,
  `cts`, `route`, and `finish`.
- The standard heavy-job timeout is 600 seconds and is recorded on the job.
- Native OpenROAD inspection uses its Tcl database API, so it works with the
  installed host build even when the optional OpenROAD Python bridge is absent.
- A candidate preview is generated only from the candidate ODB. A missing or
  invalid live artifact produces an empty/GAP state; a pedagogical screenshot
  is not substituted for a candidate database.
- Product signoff remains attached to the canonical finish. Candidate stage
  exploration does not create a Product pass badge or promote files.
- The finish hash is expected to remain unchanged throughout candidate work.

The API equivalent is an additive run/job sequence:

```json
POST /api/runs
{
  "surface": "flow",
  "profile": "flowlab-candidate",
  "design_id": "gcd",
  "pdk_id": "nangate45"
}
```

Then submit the stage through `/api/jobs` with both `run_id` and
`candidate_run_id` set to the created run. The local agent validates that the
IDs match, that the run manifest is a FlowLab candidate, and that every output
path stays inside the candidate allowlist.
