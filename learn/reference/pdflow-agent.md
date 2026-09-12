# PDflow local agent

The local agent is the runtime authority used by the desktop shell and by
browser development mode. It is intentionally dependency-free Python so that
PDflow can start even when optional EDA tools are not installed.

Start it from the repository root:

    ./scripts/run_pdflow_agent.sh

The default endpoint is http://127.0.0.1:43219. The agent owns process
launch, structured arguments, timeout, cancellation, logs, PID tracking,
artifact resolution, candidate copies, reports and the filesystem event
stream. Local launchers generate a random token by default, persist it in
`.pdflow/agent/agent.token` with mode 0600, and the Next/Tauri facades send it
as `X-PDFlow-Token`. Set `PD_FLOW_AGENT_TOKEN` only when an explicit token is
needed. The default timeout for heavy work is 600 seconds. Set
PD_FLOW_AGENT_PORT or PD_FLOW_AGENT_POLL_SECONDS only when the local
environment requires it.

Every allowlisted job also passes through the shared Linux resource executor.
The executor requires cgroup v2 and `systemd --user`, serializes heavy work,
and applies the documented memory, swap, CPU, timeout, and log limits. Health,
job, and report responses expose the resource backend and termination cause.
See [resource-execution.md](resource-execution.md) for the operator contract
and recovery procedure.

## Contracts

The versioned JSON contracts live in config/pdflow/schemas/:

- ArtifactRef identifies a file by path, hash, size, mtime, revision,
  producer, run and authority.
- RunContext identifies the design, PDK, profile, inputs and tool versions.
- ReportEnvelope records status, input/output fingerprints, mesh/oracle,
  report paths and invalidation state.

finish artifacts are immutable. An edit request for a finish is refused unless
it has a run ID; the agent then creates a copy under
.pdflow/runs/<run_id>/candidate/. The original path is never passed to an
editable process.

## Registries

config/pdflow/tool_registry.json describes host executables, capabilities,
launch profiles, version probes, parsers and status mapping. Discovery reports
READY, MISSING or MISCONFIGURED.

config/pdflow/action_registry.json describes repository-owned batch actions.
Only commands in this registry can be requested through POST /api/jobs;
arbitrary shell strings and arbitrary script paths are not accepted. Missing
action dependencies produce GAP, never a synthetic pass.

## API

The agent exposes the following versioned endpoints:

    GET  /v1/health
    GET  /v1/registry
    GET  /v1/context?surface=flow
    GET  /v1/artifacts
    GET  /v1/artifacts/<artifact_id>
    GET  /v1/runs
    POST /v1/runs
    GET  /v1/jobs
    POST /v1/jobs
    POST /v1/jobs/<job_id>/cancel
    GET  /v1/viewer
    GET  /v1/reports/<report_id>
    POST /v1/compare
    GET  /v1/events?since=<event_id|latest>
    POST /v1/candidates
    POST /v1/refresh

The Next routes under /api/ are additive facades over these contracts.
Legacy /api/open, /api/run, /api/run/stream, /api/signoff and
/api/system-pdn remain available during migration.

## Native inspection and viewers

`GET /api/inspect?stage=<stage>&variant=<variant>` submits the registered
`inspect_stage` action. The agent resolves the ODB, netlist and timing inputs,
then runs native OpenROAD, OpenSTA and Yosys inside the job cgroup. The
response contains the validated ODB/STA/Yosys summaries, input fingerprints,
the job/report IDs and the resource record. The Next process never imports a
process-launch API for inspection.

`POST /api/viewer` and the web-viewer targets in `/api/open` submit an
agent-owned OpenROAD `operation=web` job. The agent returns the loopback URL,
native PID, port and artifact identity; `GET /v1/viewer` reports the active
session. `POST /api/viewer` with `{"action":"stop"}` cancels the same job
through the agent. Native Qt OpenROAD and KLayout launches use the analogous
`operation=gui` request. A finish artifact is always opened read-only; an
editable session must be tied to a validated FlowLab candidate run.

## Events and recovery

On Linux the agent uses inotify and emits coalesced artifact.added,
artifact.changed, artifact.removed, comparison.invalidated and job events
through SSE. A client that does not have a cursor must request `latest`; a
zero cursor is treated as the same live-stream request so an older client
cannot replay the complete event history accidentally. Reconnects with a
numeric cursor receive a bounded 64-event batch. The in-memory replay window
is capped at 256 events and 2 MiB, with oversized individual payloads reduced
to a diagnostic summary; durable job and report files remain authoritative.
If inotify is unavailable it reports polling in health and uses the same event
contract. Revisions are persisted in .pdflow/agent/revisions.json.

Jobs and run manifests are atomically persisted below .pdflow/runs/. After an
agent restart, a persisted QUEUED or RUNNING record is surfaced as ORPHANED;
it is never silently shown as completed.

## Status semantics

GAP means a required input or dependency is unavailable, or a repository
safety policy deliberately refused to start the operation. A controlled
refusal carries `termination_cause=refused` and preserves the refusal line in
the bounded job log; it is not a crash and cannot be treated as a pass.
PROXY and PARTIAL are informative only. A comparison is generated only when
reports share a run, mesh, oracle and identical input artifact
hashes/revisions. Neither package nor Lab evidence can create a Product
signoff badge.
