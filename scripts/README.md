# scripts/

Root launchers. Surface catalog: [`docs/script.md`](../docs/script.md).
Repo index: [`docs/README.md`](../docs/README.md).

## Legacy system-wide installers

```bash
./scripts/01_install_openroad.sh
./scripts/02_install_opensta.sh
./scripts/03_install_klayout.sh
./scripts/04_setup_orfs.sh
```

Cloud Agent: `PD_FLOW_PROFILE=core bash scripts/cloud_agent_install.sh`.

The commands above are retained for older Ubuntu installations. The current
certified path is the native per-user host prefix; it never uses Docker as a
runtime substitute:

```bash
source scripts/native_eda_env.sh
./scripts/verify_native_eda.sh
timeout 600s ./scripts/test_native_rtl_e2e.sh
```

See [`../docs/native-toolchain.md`](../docs/native-toolchain.md) for the
installed version inventory and source rebuild procedure.

## Resource guard

Builds, native EDA runs, and long suites should enter through the shared Linux
executor. It serializes heavy work and places the command in a systemd user
cgroup with the 600-second default timeout:

```bash
./scripts/run_resource_job.sh LABEL COMMAND [ARG ...]
PYTHONPATH=learn python3 learn/pdflow_resource_runner.py status
```

See [`../learn/reference/resource-execution.md`](../learn/reference/resource-execution.md)
for limits, explicit override policy, log caps, and recovery diagnostics.

## Symphony coding-agent orchestration

The optional `run_symphony.sh` launcher starts a native Symphony control plane
using the repository-owned [`WORKFLOW.md`](../WORKFLOW.md). Symphony assigns
isolated coding workspaces to Codex app-server sessions; PDflow remains the
authority for native EDA, artifacts, reports, candidates, and resource limits.

Validate the contract without starting anything:

```bash
./scripts/verify_symphony.sh
```

Start it only after installing a reviewed native Symphony executable and
setting `PD_FLOW_SYMPHONY_BIN` plus `GITHUB_TOKEN` on the host:

```bash
./scripts/verify_symphony.sh --require-runtime
./scripts/run_symphony.sh --ack-preview
```

The installed Symphony runtime is an engineering preview and requires a
deliberate operator acknowledgement. `--ack-preview` is consumed by the
PDflow wrapper and translated to the runtime's required
`--i-understand-that-this-will-be-running-without-the-usual-guardrails` flag.
Without it, the wrapper exits before starting any process. The equivalent
host-local setting is `PD_FLOW_SYMPHONY_ACK_PREVIEW=1`.

See [`../docs/symphony-pdflow-integration.md`](../docs/symphony-pdflow-integration.md)
for the task taxonomy, workspace policy, rollout gates, and the separation
between lightweight agent concurrency and PDflow's single heavy-job queue.

For a native Tauri build on a host without system-wide GTK/WebKit development
packages, `bootstrap_native_build_sysroot.sh` creates a user-owned Debian/Kali
sysroot without sudo or Docker. The shared runner detects it automatically;
`pkgconf` preserves sysroot compiler flags while exposing host install paths to
linuxdeploy's GTK plugin.

## Product

`run_design_finish.sh` is the isolated `make finish` entrypoint.
Product cooks are launched by `learn/dse/cook.py` with an explicit
`PD_FLOW_EXPERIMENT_LOG` for the active invocation; no persisted campaign
registry or fixed comparison scene is consulted.

## Course

`learn_physical_design.sh`, `run_studio.sh`, `test_course.sh`.
`run_gcd_flow.sh` is the RTL→GDS demo, not the product oven.
