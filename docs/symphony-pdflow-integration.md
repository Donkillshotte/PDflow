# Symphony integration for PDflow

Status: integration contract and launcher implemented; the Symphony runtime
remains an explicit, operator-installed dependency.

This document defines how PDflow can use Symphony to dispatch several coding
tasks to Codex agents without creating a second EDA scheduler or weakening the
resource and artifact guarantees already implemented by PDflow.

The design follows the [Symphony service specification](https://github.com/openai/symphony/blob/main/SPEC.md)
and the [OpenAI Symphony announcement](https://openai.com/index/open-source-codex-orchestration-symphony/).
Symphony is a scheduler and runner for coding-agent sessions. It is not the
authority for PDflow runs, artifact identity, Product signoff, or native EDA
processes.

The currently installed native runtime is an engineering preview. Its own
startup warning says that the usual runtime guardrails are not present, so
PDflow never acknowledges that mode implicitly. The operator must pass
`--ack-preview` to the PDflow launcher for each start (or set the equivalent
host-local `PD_FLOW_SYMPHONY_ACK_PREVIEW=1`). This is an explicit consent
boundary, not a claim that the preview runtime is enterprise-hardened.

## Decision

Use a two-level architecture:

```text
GitHub Issues + `symphony` opt-in label
                 |
                 v
       Symphony control plane
       - polling and claims
       - retry and reconciliation
       - one workspace per issue
       - one Codex app-server session per agent
                 |
                 v
       isolated PDflow coding workspaces
       - source/UI/agent/documentation changes
       - focused tests and review commits
                 |
                 +---- heavy build or EDA request ----+
                                                      v
                                       PDflow local agent
                                       - artifact/run authority
                                       - native tool registry
                                       - candidate/finish policy
                                       - SSE and reports
                                                      |
                                                      v
                                       shared Linux resource executor
                                       - one heavy slot
                                       - cgroup v2/systemd --user
                                       - 6 GiB / 4 CPU / 600 s defaults
                                                      |
                                                      v
                                  OpenROAD, OpenSTA, KLayout, Yosys,
                                  Icarus, ngspice, Xyce and native tests
```

Symphony may run multiple lightweight implementation agents concurrently.
Every expensive build, native EDA flow, signoff, or long numerical test still
passes through `scripts/run_resource_job.sh`. The existing lock makes that
boundary global across PDflow, the Studio, command-line runs, and agent
workspaces.

This separation is important for three reasons:

1. Symphony knows about issues, workspaces, agent turns, retries, and human
   handoff. It does not know whether an ODB, GDS, SPEF, report, or mesh is
   authoritative.
2. PDflow already knows how to resolve artifacts, protect finish, create
   candidates, enforce run-scoped comparisons, classify `GAP`/`PROXY`/`FAIL`,
   and terminate resource-controlled descendants.
3. Allowing each coding agent to invent its own EDA launcher would reintroduce
   duplicate timeouts, unbounded processes, stale-report reuse, and unsafe
   writes to the canonical FlowLab tree.

## Repository contract

The repository root contains [`WORKFLOW.md`](../WORKFLOW.md), the
Symphony-owned policy and prompt contract. It is intentionally opt-in:

- the GitHub adapter is scoped to `Donkillshotte/PDflow`;
- only issues carrying the `symphony` label are dispatchable;
- `open` is active and `closed` is terminal;
- an agent handoff removes `symphony` and adds `human-review` when provider
  mutation is available;
- closing, merging, deploying, or promoting a Product finish is not automatic.

The `symphony` label is a safety gate. Creating or editing an ordinary GitHub
issue does not start an agent. A human must deliberately add the label after
the issue has a sufficiently narrow scope, acceptance criteria, and affected
surface.

The workflow also fixes these runtime properties:

- at most three coding agents at once;
- at most sixteen turns per agent invocation;
- retries use a five-minute maximum backoff;
- each issue receives its own workspace;
- Codex is launched through `codex app-server`;
- Codex uses `workspace-write` and an approval-required policy;
- the workspace is populated from the committed HEAD of the configured local
  checkout, not from uncommitted changes in the main checkout;
- the prompt requires `AGENTS.md`, current-scope tests, native tools, and
  PDflow resource guards.

The workflow does not contain a GitHub token. The token is supplied by the
host environment and must never be copied into a repository file, issue body,
agent prompt, or log.

## What is implemented in PDflow

### `WORKFLOW.md`

This is the versioned policy consumed by a Symphony-compatible runtime. It
contains GitHub issue selection, workspace creation, Codex settings, and the
PDflow-specific agent prompt.

### `scripts/run_symphony.sh`

This is the native Linux launcher. It:

- resolves a single executable path from `PD_FLOW_SYMPHONY_BIN` or `PATH`;
- verifies that the configured Codex exposes `app-server` mode;
- verifies that `PD_FLOW_REPO_ROOT` is a Git checkout;
- creates state, workspace, and log directories with mode `0700` when the host
  permits it;
- exports only explicit, non-secret path settings used by the workflow;
- passes arguments as an argv array rather than constructing a shell command;
- starts Symphony without acquiring PDflow's heavy EDA slot.

Symphony is a lightweight coordinator and should not hold the heavy-job lease
for its lifetime. Heavy work launched by an agent is guarded independently.

### `scripts/verify_symphony.sh`

This is a side-effect-free preflight. It validates the workflow, checks the
local Codex app-server, and reports the Symphony executable as `READY` or
`GAP`. The default mode is suitable for CI and documentation checks; pass
`--require-runtime` when an operator is about to start the service.

### `learn/scripts/validate_symphony_workflow.py`

This validator checks the repository policy without contacting GitHub, creating
workspaces, starting Codex, or running EDA. It protects against accidental
drift in the issue gate, workspace boundary, approval policy, and PDflow
resource rules.

## Installation and startup

The Symphony runtime is not vendored into PDflow. Install or build a native
Symphony executable using the official distribution or a reviewed build, then
point PDflow to that executable. The executable is expected to support the
workflow contract and Codex app-server protocol.

The current host provides native Codex app-server mode and has the official
Linux x86_64 Symphony `v0.0.2` release installed at
`/home/kalishot/.local/bin/symphony`. The binary is deliberately outside the
repository and is not committed. A different checkout or host must provide
and verify its own runtime; until then its correct status is `GAP`.

From the PDflow repository:

```bash
cd /home/kalishot/PDflow
export PD_FLOW_SYMPHONY_BIN=/home/kalishot/.local/bin/symphony
export GITHUB_TOKEN='set-this-outside-the-repository'
./scripts/verify_symphony.sh --require-runtime
./scripts/run_symphony.sh --ack-preview
```

`--ack-preview` is a PDflow wrapper option. It is translated into the native
runtime flag
`--i-understand-that-this-will-be-running-without-the-usual-guardrails` and
is not forwarded as an unknown Symphony option. If it is omitted, the wrapper
exits before creating or starting a Symphony process.

Recommended explicit paths for this host are:

```bash
export PD_FLOW_REPO_ROOT=/home/kalishot/PDflow
export PD_FLOW_SYMPHONY_BIN=/home/kalishot/.local/bin/symphony
export PD_FLOW_SYMPHONY_WORKSPACE_ROOT=/home/kalishot/.local/state/pdflow/symphony/workspaces
export PD_FLOW_SYMPHONY_STATE_ROOT=/home/kalishot/.local/state/pdflow/symphony
export PD_FLOW_SYMPHONY_LOG_ROOT=/home/kalishot/.local/state/pdflow/symphony/logs
export PD_FLOW_CODEX_BIN=/home/kalishot/.local/bin/codex
```

The launcher supplies safe defaults for state paths when they are omitted. It
does not silently fetch a repository or switch to Docker. The current host
uses the official prebuilt native release, whose SHA-256 is recorded in the
installation evidence; source builds remain an explicit operator choice.

The `GITHUB_TOKEN` value above is illustrative only. Never replace it with a
literal token in `WORKFLOW.md`, shell history committed to the repository, or
an issue description. The Symphony GitHub adapter should keep tracker
credentials on the host side and out of the Codex child environment.

## Workspace and branch policy

The `after_create` hook makes a local clone from `PD_FLOW_REPO_ROOT` using
`--local --no-hardlinks --no-tags`. This gives each issue an independent Git
directory and avoids sharing a working tree between agents. It starts from a
committed revision; uncommitted files in `/home/kalishot/PDflow` are not
silently copied into an agent workspace.

Before enabling the first issue, commit or otherwise preserve any changes that
must be part of the agent's base. The current PDflow checkout is allowed to be
dirty for normal local development, but a Symphony workspace is intentionally
based on a known commit.

Each agent must:

1. read `AGENTS.md` and the relevant documentation;
2. identify one coherent surface and its contracts;
3. change only its own workspace;
4. commit a focused change if the task is ready for review;
5. report exact tests, exit codes, resource evidence, and limitations;
6. stop at human review rather than merging or deploying.

The workflow prompt explicitly forbids broad destructive commands, direct
finish mutation, unguarded heavy jobs, and a second process/resource launcher.
The prompt is a policy aid; PDflow's backend checks remain authoritative.

## Task decomposition for PDflow

The most efficient issue graph is a small set of narrow, contract-oriented
tasks. Avoid assigning one agent a vague “finish PDflow” issue.

Recommended parallelizable tasks are:

- **UI shell:** one application-shell or responsive-layout boundary, with
  deterministic fixture tests and no EDA execution.
- **FlowLab surface:** one phase or one viewer integration, preserving
  artifact identity, candidate policy, and native-tool links.
- **Analysis contract:** one check family such as STA, gridcheck, IR, or EM;
  the issue must state its valid checkpoints, inputs, status mapping, and
  report provenance.
- **Package/System PDN:** package-only read-only work, never producing a
  Product signoff badge and never writing the Product finish.
- **Lab/DSE:** experiment, mesh, oracle, or proxy work with explicit
  `PROXY`/`GAP` semantics and no historical baseline oracle.
- **Agent/API:** one additive endpoint, report normalizer, event, or recovery
  behavior, with compatibility tests for the existing route.
- **Test infrastructure:** one fixture matrix, crash/recovery case, viewport
  assertion set, or native tool probe.
- **Documentation:** one operator or developer guide updated from verified
  behavior.

If two tasks change the same contract or shared component, make the dependency
explicit instead of relying on parallel agents to resolve conflicts later. A
good sequence is:

1. contract/schema or fixture;
2. backend/adapter behavior;
3. UI integration;
4. focused and regression tests;
5. documentation and human review.

## EDA and resource boundary

The following operations are heavy and MUST use the existing PDflow wrapper:

- Next/Tauri builds;
- native RTL simulation or synthesis;
- OpenROAD floorplan, placement, CTS, route, and finish;
- OpenSTA, DRC, LVS, signoff, IR/EM, and System PDN;
- DSE, extraction, transient simulation, and long numerical suites;
- full native or desktop end-to-end acceptance tests.

Use:

```bash
./scripts/run_resource_job.sh LABEL COMMAND [ARG ...]
```

The wrapper provides the cgroup v2/systemd user service, one host-wide heavy
slot, host-headroom and PSI preflight, native numerical thread limits,
descendant termination, bounded complete logs, and the default 600-second
timeout. An agent must not bypass it because multiple Symphony workspaces can
otherwise overload the same host.

Three coding agents may be useful for source work, but they do not imply three
concurrent EDA jobs. If two agents request heavy verification, the executor
queues the second. If cgroup/systemd isolation is unavailable, the test must
be reported as blocked or `GAP`; the agent must not run it directly on the
host.

Native EDA tools remain native. Symphony does not replace OpenROAD, OpenSTA,
KLayout, Yosys, Icarus, ngspice, Xyce, or PDflow's local agent with Docker.

## Artifact, candidate, and Product rules

Coding agents may modify source, tests, UI, scripts, and documentation inside
their workspace. They must not treat a generated output as a Product oracle.

For flow and analysis work:

- canonical FlowLab finish artifacts are read-only;
- mutating experiments use a candidate or isolated run directory;
- every report carries input artifact references, hashes/revisions, run ID,
  status, and tool version;
- modifying an input invalidates derived reports;
- `GAP`, `PROXY`, `PARTIAL`, and `NOT_RUN` are never Product signoff;
- Package and Lab evidence cannot create a Product badge;
- comparisons are valid only inside a compatible live invocation;
- no agent may promote a candidate automatically.

An agent may request a PDflow job from its workspace when the relevant action
is registered and the resource executor is available. It must not construct a
new shell string from issue text or UI input, pass arbitrary script paths to
the local agent, or write directly under the protected ORFS finish tree.

## UI and observability integration

The first integration keeps Symphony's optional orchestration dashboard
separate from PDflow Studio. This avoids two competing sources of truth:

- Symphony displays issue claim, workspace, Codex session, turn, retry, and
  human-handoff state.
- PDflow displays run, job, artifact, report, native process, resource, stale,
  candidate, and signoff state.

The future PDflow integration point is an additive orchestration read model,
not a second scheduler. It should expose, at minimum:

- issue identifier and URL;
- Symphony workspace path and agent session ID;
- current attempt, turn, retry, and handoff state;
- related PDflow run/job/report IDs;
- last resource record and termination cause;
- links to the exact log and commit;
- explicit stale/GAP/blocked reasons.

The UI must never infer that an agent is healthy because an SSE connection is
open, or that a job passed because a Codex turn completed. A completed agent
turn means only that the agent stopped at its own handoff point. PDflow
evidence and Product checks retain their existing authority.

## Recovery and failure handling

If Symphony stops, its tracker reconciliation should leave the issue
dispatchable or blocked according to the provider state. PDflow separately
recovers persisted `QUEUED`/`RUNNING` jobs as `ORPHANED`; it never silently
relabels them as completed.

Use the following recovery sequence:

1. inspect the Symphony log and issue state;
2. inspect the affected workspace and its Git status;
3. inspect PDflow job/report records and the resource executor status;
4. stop only the known Symphony or Codex process/session when required;
5. verify the heavy-job lock was released;
6. rerun only after confirming the workspace, run ID, input hashes, and
   dependency state.

Do not use `pkill -f`, broad recursive deletion, `git reset --hard`, or a
finish overwrite as a recovery shortcut. A failed or resource-killed run is
diagnostic evidence, not a validated result.

## Rollout gates

### Gate 0: contract-only

Run:

```bash
./scripts/verify_symphony.sh
```

Expected result: workflow valid, Codex app-server `READY`, Symphony runtime
`READY` or an explicit executable `GAP`. No tracker call, agent, workspace, or
EDA process is started.

### Gate 1: one documentation issue

Use one disposable, low-risk issue with the `symphony` label. Verify:

- one workspace is created outside the main checkout;
- the agent can read `AGENTS.md`;
- the issue remains open until human handoff;
- the agent produces a focused commit and test report;
- no finish artifact or unrelated checkout is modified.

### Gate 2: parallel lightweight work

Dispatch two or three independent UI/documentation/test issues. Verify:

- each issue has a distinct workspace;
- no duplicate claims or cross-workspace writes occur;
- retries do not create duplicate commits or reports;
- removal of the `symphony` label stops dispatch on reconciliation.

### Gate 3: one guarded native task

Give one agent a narrowly scoped native-tool or analysis task. Verify:

- the agent uses `run_resource_job.sh`;
- the local agent and resource executor record the same run/job boundary;
- peak memory, CPU, timeout, and termination cause are visible;
- the finish hash is unchanged;
- a missing dependency is `GAP`, not `PASS`.

### Gate 4: production-like adoption

Only after the previous gates pass should the team add a larger issue graph.
Keep concurrency conservative, require review commits, and retain the human
promotion gate for all Product/Package/Lab changes.

## Known limits

The host installation is verified, but this slice does not claim that a
GitHub token is configured or that a live GitHub issue has been dispatched. It
also does not add a second local task database, automatic PR merger, or
automatic Product promotion. Those features would expand the trust boundary
and should be implemented only after the contract-only and single-issue gates
pass.

The repository's current local `codex app-server` probe is `READY`, and the
installed native Symphony runtime is also `READY` after
`./scripts/verify_symphony.sh --require-runtime`. A clean host without that
external installation must report `GAP`, not a simulated success.
