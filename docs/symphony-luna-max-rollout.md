# Symphony + Luna Max rollout plan

This document is the operational plan for using the native Symphony runtime to
coordinate isolated Codex implementation agents for PDflow.

Symphony is an issue scheduler and workspace coordinator. It is not a second
PDflow EDA scheduler, artifact authority, signoff engine, or replacement for
the native OpenROAD/OpenSTA/KLayout/Yosys/Icarus/ngspice toolchain.

## Current verification status

The following checks have been completed on the current Linux host:

- repository workflow validation passes;
- native Codex app-server is available;
- the native Symphony executable is available;
- the PDflow wrapper reaches the Symphony application process;
- the process reports a clear missing_github_token configuration error when
  no tracker credential is present;
- the local Codex configuration currently selects gpt-5.6-luna with
  model_reasoning_effort = "max".

The last item is host-local configuration, not repository state. A live
GitHub issue dispatch is not considered verified until a fresh, operator-owned
credential is configured and the canary gate below completes.

## Model contract: Luna with max reasoning

The installed Symphony command accepts a workflow path, log root, and port; it
does not expose a model-selection flag. The model is therefore selected by the
Codex configuration consumed by codex app-server.

The required host-local profile is:

~~~
model = "gpt-5.6-luna"
model_reasoning_effort = "max"
~~~

The repository must not commit this file, API credentials, or a user-specific
CODEX_HOME. Verify the effective profile without printing the rest of the
configuration:

~~~
grep -nE '^[[:space:]]*(model|model_reasoning_effort)[[:space:]]*=' \
  "$HOME/.codex/config.toml"
./scripts/verify_symphony.sh --require-runtime --require-luna-max
~~~

GPT-5.6 Luna is documented by OpenAI as a model for cost-sensitive,
high-volume workloads and supports reasoning effort max; this makes it a
reasonable choice for multiple bounded coding sessions, while not changing
the resource policy for native EDA jobs.

## Agent topology

The first rollout uses five logical workstreams but only three concurrent
agent sessions:

1. UI shell, responsive layout, and focus mode.
2. FlowLab viewer, artifact synchronization, and native bridge.
3. STA, WNS/slack, gridcheck, IR, and EM evidence contracts.
4. Package/System PDN and explicit GAP/PROXY semantics.
5. E2E tests, installer, documentation, and security hardening.

Each workstream is one or more GitHub issues with a narrow boundary. The
current WORKFLOW.md allows at most three concurrent agents; additional
issues remain queued. Raising the limit to five is a separate capacity gate,
not a harmless configuration change.

Symphony creates one isolated workspace and one Codex app-server session per
issue. This is issue-level parallelism; it is not a promise that one agent can
spawn arbitrary unrestricted child agents.

## Resource and safety policy

Every agent may work on source, tests, UI, scripts, or documentation in its
own workspace. Heavy work must still use PDflow's shared executor:

~~~
./scripts/run_resource_job.sh LABEL COMMAND [ARG ...]
~~~

The heavy executor remains globally serialized and enforces the native
6 GiB/5 GiB high-water/512 MiB swap/400% CPU/600-second policy. Five coding
issues do not permit five simultaneous EDA flows. If cgroup/systemd
isolation is unavailable, the agent must report GAP or blocked verification.

The following actions remain prohibited for agents:

- writing to the canonical Product/FlowLab finish;
- using unguarded EDA or long numerical commands;
- copying dirty files from the main checkout into an agent workspace;
- merging, pushing, deploying, or promoting a Product finish automatically;
- treating GAP, PROXY, PARTIAL, or FAIL as a Product pass;
- placing tokens in issues, prompts, logs, or repository files.

## Rollout gates

### Gate 0 — local contract

Run:

~~~
cd /home/kalishot/PDflow
PD_FLOW_SYMPHONY_BIN=/home/kalishot/.local/bin/symphony \
PD_FLOW_CODEX_BIN=/home/kalishot/.local/bin/codex \
PD_FLOW_REPO_ROOT=/home/kalishot/PDflow \
  ./scripts/verify_symphony.sh --require-runtime --require-luna-max
~~~

This must not contact GitHub, create a workspace, or launch an agent.

### Gate 1 — one documentation canary

Create one disposable GitHub issue with:

- the symphony label;
- a documentation-only scope;
- explicit acceptance criteria;
- exact focused tests;
- no credential or generated artifact in the issue body.

Verify that the agent creates a workspace below the configured Symphony state
root, reads AGENTS.md, commits only the requested change, and stops for
human review. The main checkout and finish hash must be unchanged.

### Gate 2 — two or three lightweight issues

Dispatch independent UI/documentation/test issues. Confirm distinct
workspaces, no duplicate claims, no cross-workspace writes, and no EDA job
started merely by opening an inspector or report.

### Gate 3 — one guarded native issue

Use one narrowly scoped analysis or native-tool issue. Confirm the agent uses
run_resource_job.sh, the job has a cgroup/resource record, logs are bounded,
and missing inputs are classified as GAP rather than PASS.

### Gate 4 — production-like graph

Only after Gates 0–3 pass should the five-workstream graph be enabled. Keep
three concurrent agents until a measured memory/CPU session proves that five
Codex sessions do not destabilize the host. Heavy EDA remains one-at-a-time.

## Safe startup

Use a new credential configured only in the host environment or a secret
manager. Do not reuse a token that was pasted into chat or shell history.

~~~
cd /home/kalishot/PDflow
read -rsp "GitHub token: " GITHUB_TOKEN
printf '\n'
export GITHUB_TOKEN
export PD_FLOW_REPO_ROOT=/home/kalishot/PDflow
export PD_FLOW_SYMPHONY_BIN=/home/kalishot/.local/bin/symphony
export PD_FLOW_CODEX_BIN=/home/kalishot/.local/bin/codex

./scripts/verify_symphony.sh --require-runtime --require-luna-max --require-github-auth
./scripts/run_symphony.sh --ack-preview
~~~

The --ack-preview flag is required by the currently installed engineering
preview runtime. It is an explicit operator acknowledgement and does not
claim that the preview runtime has enterprise guardrails of its own.

## Issue and handoff contract

Every issue should state:

- surface: Product, FlowLab, Package, Lab, UI, agent, test, or documentation;
- allowed files and non-goals;
- dependency issues, if any;
- acceptance criteria and focused commands;
- whether native tools are required;
- the expected report/artifact provenance;
- the condition that requires human review.

The agent handoff must include the commit SHA, files changed, exact commands
and exit codes, resource evidence, unresolved GAP/FAIL/PROXY states, and
the finish-hash result. A completed Codex turn is not a PDflow signoff.

## Recovery

If a run stops, inspect the Symphony log, issue state, workspace Git status,
PDflow job records, and resource lock before retrying. Stop only the known
Symphony/Codex session. Never use broad process killing, destructive checkout
resets, or finish overwrites as recovery shortcuts.

## Definition of ready

The Symphony rollout is ready for normal use when:

- Gate 0 passes with the intended Luna/max profile;
- the single-issue canary completes against GitHub;
- workspace isolation and human handoff are observed, not inferred;
- one guarded native issue records correct resource evidence;
- no finish hash changes;
- three-agent lightweight concurrency is stable;
- the five-workstream graph has explicit dependencies and no overlapping
  ownership of shared contracts.

See symphony-pdflow-integration.md for the PDflow artifact, candidate, UI, and
native-tool boundaries.
