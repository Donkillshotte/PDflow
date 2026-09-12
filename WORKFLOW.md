---
tracker:
  kind: github
  provider:
    repo: Donkillshotte/PDflow
    api_url: https://api.github.com
  required_labels:
    - symphony
  active_states:
    - open
  terminal_states:
    - closed
polling:
  interval_ms: 30000
workspace:
  root: $PD_FLOW_SYMPHONY_WORKSPACE_ROOT
hooks:
  after_create: |
    set -eu
    : "${PD_FLOW_REPO_ROOT:?PD_FLOW_REPO_ROOT must point to the canonical PDflow checkout}"
    test -d "$PD_FLOW_REPO_ROOT"
    test "$(git -C "$PD_FLOW_REPO_ROOT" rev-parse --is-inside-work-tree)" = true
    git clone --local --no-hardlinks --no-tags "$PD_FLOW_REPO_ROOT" .
    # WORKFLOW.md may be newly introduced or intentionally uncommitted while
    # the operator is bootstrapping Symphony. Copy only this policy file; do
    # not copy the main checkout's arbitrary dirty tree.
    test -f "$PD_FLOW_REPO_ROOT/WORKFLOW.md"
    cp "$PD_FLOW_REPO_ROOT/WORKFLOW.md" ./WORKFLOW.md
  before_run: |
    set -eu
    test -f AGENTS.md
    test -f WORKFLOW.md
  after_run: |
    set -eu
    # Keep cleanup and evidence collection explicit. Never delete or rewrite
    # generated evidence from a workflow hook.
    true
agent:
  max_concurrent_agents: 3
  max_turns: 16
  max_retry_backoff_ms: 300000
codex:
  command: codex app-server
  approval_policy: on-request
  thread_sandbox: workspace-write
  turn_timeout_ms: 3600000
  read_timeout_ms: 5000
  stall_timeout_ms: 300000
---

You are an implementation agent for PDflow. Work only on the issue assigned to
this isolated workspace.

Issue: {{ issue.identifier }}
Title: {{ issue.title }}
Description: {{ issue.description }}
Attempt: {{ attempt }}

Before changing code:

1. Read `AGENTS.md`, the relevant surface documentation, and the nearest
   existing tests. Treat the repository as a safety-critical EDA/UI
   orchestration project, not as a disposable demo.
2. Classify the work as Product, FlowLab, Package/System PDN, Lab, UI, agent,
   documentation, or test infrastructure. Keep one issue focused on one
   coherent boundary.
3. Inspect the current checkout and identify the exact files and contracts that
   will change. Do not assume that a path, report, or metric from another run is
   valid for this issue.

Implementation rules:

- This workspace is disposable and isolated per issue. Never use another
  agent's workspace, the main checkout, or an absolute path outside the
  declared workspace unless the task explicitly requires a read-only host tool
  probe.
- Never mutate a protected finish artifact. Product finish is read-only;
  physical experiments belong in a candidate or an isolated run directory.
- Never use `git reset --hard`, `git checkout --`, `pkill -f`, broad recursive
  deletion, or forceful cleanup of paths that were not created by this run.
- Never invent a PASS from a missing dependency, stale report, PROXY result,
  PARTIAL result, or a completed process with failed requirements.
- Never add a second process launcher, timeout policy, artifact resolver,
  resource lock, or event stream. Reuse PDflow's local agent and shared
  executor.
- Heavy builds, native EDA, RTL-to-GDS, DRC/LVS/signoff, long numerical runs,
  and full browser/desktop builds MUST use
  `./scripts/run_resource_job.sh`. The executor owns the single heavy slot,
  cgroup limits, descendant termination, logs, and 600-second default timeout.
  If isolation is unavailable, report the verification as blocked/GAP instead
  of running unguarded.
- Keep native tools native. Do not replace OpenROAD, OpenSTA, KLayout, Yosys,
  Icarus, ngspice, Xyce, or the PDflow resource executor with Docker.
- Do not start a job merely by reading an inspector, opening a report, or
  navigating the UI. Mutating or recalculation actions must remain explicit.
- Preserve additive API compatibility, artifact/run provenance, stale
  propagation, candidate isolation, and the Product/Package/Lab boundary.

Verification rules:

- Run focused unit/contract tests first, then the narrowest relevant smoke
  test. Run heavy tests only when their resource guard is available and the
  issue requires them.
- Record exact commands, exit codes, and meaningful limitations in the issue
  handoff. Include the relevant artifact/report IDs and hashes when the issue
  changes flow or analysis behavior.
- Do not hide unrelated pre-existing changes. If a failure is outside the
  issue, identify it and continue with scoped evidence.
- Do not push, merge, deploy, or promote a Product finish automatically. Leave
  the implementation ready for human review.

Handoff:

- Commit a focused change only when the workspace contains a coherent,
  verified implementation. Do not create a merge commit.
- Add a concise handoff containing summary, files changed, tests run, resource
  evidence, unresolved gaps, and the commit SHA.
- If the GitHub provider tool is available, remove the `symphony` label and
  add `human-review` when the task is ready for a person. Do not close the
  issue unless the issue explicitly asks for that. If provider mutation is not
  available, state the exact manual label transition and stop.
