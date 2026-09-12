# Testing and release gates

PDflow uses a layered validation strategy. Fast checks run on every change;
native signoff and RTL-to-GDS checks run with an explicit 600-second process
timeout; desktop and UI checks verify the same live artifacts that the CLI
uses. A process exit code alone is never treated as signoff evidence.

## Required environment

```bash
source scripts/native_eda_env.sh
./scripts/verify_native_eda.sh
```

The native verification script must report all six core tools. A missing
optional tool is represented as `GAP` and is allowed only on lab paths that
declare that dependency optional. No test may use a historical report as a
current oracle.

## Fast gates

```bash
python3 -m compileall -q learn/pdflow_agent learn/scripts
python3 learn/scripts/test_pdflow_agent.py
python3 learn/scripts/test_candidate_schema.py
python3 learn/scripts/test_signoff_honesty.py
python3 learn/scripts/test_lab_physics.py
./scripts/test_studio_api.sh
./scripts/test_all_phases.sh
```

For the Studio package:

```bash
cd studio
npm run lint
npm run build
```

On a Linux workstation without a system-wide `npm`, the release gate uses
the checked-in native Node runtime and local `node_modules` automatically.
For the native engine, set `PD_FLOW_BUILD_TOOLS_PREFIX` to a user-owned
prefix containing CMake/CTest and Eigen; the gate then performs a fresh
source configure, build, and CTest run instead of silently accepting a stale
binary.

The final gate also runs `git diff --check`, shell syntax checks, JSON
validation, and the API contract tests. Any generated report that is
modified by a test is inspected for its status, input hashes, tool versions,
and report paths before the run is accepted.

## Native RTL-to-GDS gate

`scripts/test_native_rtl_e2e.sh` performs the following in one isolated
variant, by default `enterprise-e2e`:

1. probes the native executables and captures their versions;
2. runs ORFS `make finish` from the real GCD RTL;
3. validates final ODB, DEF, GDS, SPEF, CDL, and gate netlist artifacts;
4. runs RTL and gate simulation with Icarus and VCD checks;
5. runs Yosys equivalence and formal checks;
6. runs native grid, KLayout DRC/LVS, OpenSTA, ngspice System PDN,
   vectorless, dynamic IR, and EM/IR reports;
7. validates every required report and rejects missing, stale, or malformed
   output;
8. verifies the immutable FlowLab finish hash before and after the gate.

The `FLOW_VARIANT` directory is never mixed with `flowlab` or `learn`.
`PD_FLOW_TIMEOUT_S` defaults to 600 and may be increased explicitly for a
machine-specific heavy run only with `PD_FLOW_ALLOW_TIMEOUT_INCREASE=1` (up to
3600 seconds). It must not be replaced by a shorter implicit timeout in a
wrapper. The resource executor remains the authority for the effective
timeout and records it in the job provenance. Before the workload starts, the
executor also requires verifiable `MemAvailable` and Linux PSI memory pressure;
it queues while host headroom or `full_avg10` pressure is above policy and
refuses the job when either telemetry source cannot be read.

## Status semantics

- `PASS` means the required checks ran and passed.
- `WARN` is non-blocking only when the check is explicitly optional.
- `FAIL` means the native tool ran and reported a failure, crash, or timeout.
- `GAP` means the result is not verifiable because an input, dependency, PDK,
  or license is absent.
- `PROXY` is useful analysis but is never Product signoff.
- `PARTIAL` and `NOT_RUN` are never Product wins.

Timing can therefore be a successfully generated report while still exposing
negative WNS/TNS or leftover violations. The UI must show those metrics and
leftovers instead of converting them into a green signoff badge.

## Artifact and provenance gates

Every generated report is checked against `ArtifactRef` records containing the
relative path, content hash, size, mtime, revision, authority, and producer.
Finish artifacts are immutable. Edit-mode actions create a candidate copy
under the current run and cannot write the finish path. A watcher increments
the candidate revision after a real write and invalidates dependent reports;
the application then requires refresh/revalidation before showing them as
current.

Comparisons require the same run ID, mesh, oracle, input artifact hashes and
revisions, compatible profile, and available metrics. Otherwise the API
returns `GAP` with the reason and does not calculate a delta.

## UI and desktop acceptance

The application shell is exercised at desktop and narrow viewport sizes. The
acceptance path is:

1. start the local agent and Studio/Tauri shell;
2. open FlowLab and inspect the live RTL, pipeline, artifact revision, and
   status bar;
3. inspect each available stage through the agent-owned native ODB/STA/Yosys
   action and verify input hashes, report ID, resource cgroup and status;
4. open Floorplan in native OpenROAD and confirm PID/log/session visibility;
5. save only to a candidate, observe `artifact.changed`, and confirm preview
   and dependent reports refresh or become stale;
6. open the current GDS in native KLayout and run DRC/LVS;
7. open Package and confirm real System PDN or an honest `GAP`;
8. open Lab and confirm experimental results never produce a Product badge;
9. close a native tool manually and confirm the session becomes stopped or
   orphaned without corrupting the finish;
10. restart the agent and confirm orphan recovery and lock cleanup;
11. compare the finish hash with the pre-run hash.

### Timing requirement policy in the native E2E gate

The default native gate uses the real GCD constraint file
`designs/nangate45/gcd-tutorial/constraint.sdc`.  The current reference design
may produce a valid, completed OpenSTA report whose measured requirement is
still failing.  This is represented explicitly as
`execution_status=COMPLETED`, `evidence_status=PASS`,
`requirement_status=FAIL`, `signoff_status=FAIL`, and
`product_signoff=false`.

For toolchain, provenance, and artifact-integrity certification, the gate may
continue past that known design requirement result with the explicit setting:

```bash
PD_FLOW_E2E_ALLOW_TIMING_FAIL=1 \
PD_FLOW_TIMEOUT_S=600 \
bash scripts/test_native_rtl_e2e.sh
```

To require timing closure as a release condition, use
`PD_FLOW_E2E_ALLOW_TIMING_FAIL=0`; the command must then stop on a timing
requirement failure.  A relaxed exploratory SDC can be selected explicitly,
but it does not mask a failed DRC/LVS or other native check:

```bash
PD_FLOW_E2E_SDC_FILE=./designs/nangate45/gcd-tutorial/constraint_relaxed.sdc \
PD_FLOW_E2E_ALLOW_TIMING_FAIL=0 \
PD_FLOW_TIMEOUT_S=600 \
bash scripts/test_native_rtl_e2e.sh
```

The relaxed profile is an experiment, not the certified Product oracle; its
generated geometry and LVS outcome must still be inspected.  Neither a
completed process nor finite timing numbers are sufficient for signoff.
The latest certified toolchain gate records `protected_finish_hash=UNCHANGED`
and keeps timing, proxy, and gap states visible in the reports.

The browser facade remains available for smoke tests. It delegates process
execution to the same local agent and is not a second orchestration
implementation.

For deterministic shell geometry and responsive regressions, run the
Chromium-backed viewport matrix against a running Studio instance:

```bash
STUDIO_URL=http://127.0.0.1:43227 \
  python3 learn/scripts/test_ui_layout_matrix.py
```

The matrix covers `980x680`, `1280x720`, `1920x1080`, `768x1024`, and
`390x844` across Overview, FlowLab ASAP7, all Lab views, all Package views,
all Product views, all Tools views, Lessons, the lesson wizard, and Materials.
It asserts full application width/height, no document-level horizontal
overflow, a present design canvas on design surfaces, and that the migrated
secondary surfaces do not regress to opaque light cards or controls. It is
read-only and does not enqueue a job. Hosts without `/usr/bin/node` use the repository's
`studio/node-runtime/node` and the configured Playwright CLI automatically;
override `PLAYWRIGHT_NODEJS_PATH`, `PLAYWRIGHT_CLI_PATH`, or `CHROMIUM_BIN`
only when the local installation requires it.

For browser-level controls and navigation, run the interaction contract as
well:

```bash
STUDIO_URL=http://127.0.0.1:43227 \
  python3 learn/scripts/test_ui_interactions.py
```

This gate covers phase tabs, viewer controls, profile selectors, finish
confirmation and cancellation, inspector/dock/focus mode, command-palette
navigation, Package/Lab/Product/Tools tabs, deep links, the narrow mobile
navigation drawer, and the Package → System PDN visual path. The visual path
loads both TRAN/AC plots, exercises lane/cursor controls, and runs one bounded
scenario through the local agent into an isolated report. All other long
actions are cancelled at the confirmation boundary; the scenario writes only
`.pdflow/runs` and does not replace canonical finish artifacts. The safe
toolchain action smoke and native RTL-to-GDS gate still cover broader native
execution.

### Desktop process and log isolation

The packaged desktop shell is started directly so its window can remain
interactive. The shell owns only the Next and local-agent lifecycle; the
agent owns every OpenROAD, KLayout, and batch-tool process and places each
heavy job in the shared single-slot cgroup. Wrapping the whole long-lived
AppImage in `run_resource_job.sh` is therefore not a valid acceptance mode:
it would hold the heavy-job lease for the lifetime of the window and queue
the EDA jobs that the desktop is meant to launch. Desktop builds themselves
must still use `run_resource_job.sh`.

The desktop frontend build defaults the native Node webpack worker to a
3,072 MiB old-space heap so native buffers and the Tauri compiler remain below
the cgroup high watermark. `PD_FLOW_NEXT_HEAP_MB` may be set from 2,048 to
5,120 MiB; values above 3,072 MiB require
`PD_FLOW_RESOURCE_ALLOW_INCREASE=1` and must be justified in the run log.
The release gate accepts a package only after the frontend command has run as
Tauri's `beforeBuild` step and the standalone `server.js`, native desktop
binary, and both bundle files are present. The recorded build log and file
mtimes are checked together so an older stale bundle cannot be reported as the
current release.

Next and agent stdout/stderr are drained by bounded native log pumps. The
current `next-server.log` and `agent.log` are capped at 16 MiB each; the
previous session is retained as one `.1` rotation. The bootstrap log uses the
same cap. Resource-job logs have their independent 64 MiB default cap and
16 KiB in-memory tail. A cap marker is diagnostic only and never makes a
truncated log a passing result.

The desktop assigns Next and the local agent to dedicated Linux process groups.
Normal shutdown sends TERM, waits up to three seconds, then sends KILL to the
group. A Linux parent-death signal also kills either child if the Tauri process
is terminated before it can emit its normal exit event; this is verified with
an intentional shell-crash test. The agent's EDA jobs remain owned by their
individual systemd user cgroups, so their resource reports and lock recovery
are independent of the UI process lifetime.

The runtime event channel is a persistent SSE stream. When no event is
available, the local agent emits an SSE comment heartbeat every 15 seconds;
the UI reconnects with exponential backoff and keeps its 2.5-second health
poll as a fallback. A new UI connection starts at the live event cursor rather
than replaying the agent's history. Explicit numeric cursors receive at most
64 events per batch; the in-memory event bus retains at most 256 events and
2 MiB, and oversized payloads are replaced by a bounded summary. Browser
refreshes and FlowLab metadata reads are coalesced, so a burst of tool log or
watcher events cannot trigger one network refresh and React render per line.
An idle stream therefore does not masquerade as an agent failure. The
`test_events.py` gate covers the byte/event caps and live-cursor semantics.

The frontend build is source-owned CSS with no workspace-wide Tailwind scan and
uses local system font stacks; it does not fetch Google fonts during a build.
This keeps generated Tauri bundles out of the compiler's input tree and makes
the release build deterministic on an offline Linux host.

When a native GUI is cancelled, PDflow reports `CANCELLED` with a `PARTIAL`
report and `termination_cause=cancelled`. systemd may expose a raw stop
`Result=timeout` while a GUI closes; that raw value remains in resource
diagnostics, but it is not surfaced as a job timeout and cannot validate a
signoff.

Repository safety guards use `REFUSED:` or `PREVIEW_GAP` log markers. The
agent classifies these as job state `GAP`, report status `GAP`, and
`termination_cause=refused`, preserving the bounded reason in the API. This
keeps a protected-finish refusal distinct from a tool crash and prevents a
failed recook request from being mistaken for a valid result.
