# Documentation map

PDflow is a live-analysis workspace. The primary rule is in
[`../learn/reference/live-analysis.md`](../learn/reference/live-analysis.md):
current results are derived from the current invocation only.

## Surfaces

- [symphony-luna-max-rollout.md](symphony-luna-max-rollout.md) — Symphony
  setup, Luna/max model contract, agent topology, rollout gates, and canary.
- [`installer.md`](installer.md) — one-command native Linux installation,
  launcher, resource policy, troubleshooting, and repository boundaries.
- [`course.md`](course.md) — course and Studio workflow.
- [`lab.md`](lab.md) — multi-fidelity DSE and physics experiments.
- [`product.md`](product.md) — same-invocation product comparison contract.
- [`operations.md`](operations.md) — local commands, timeouts, and failure
  handling.
- [`native-toolchain.md`](native-toolchain.md) — installed native host tools,
  discovery, GUI launch, and rebuild procedure.
- [`testing.md`](testing.md) — fast gates, native RTL-to-GDS acceptance, and
  desktop/UI validation.
- [`../learn/reference/resource-execution.md`](../learn/reference/resource-execution.md)
  — cgroup limits, queueing, diagnostics, and non-destructive execution.
- [`architecture.md`](architecture.md) — ownership and artifact flow.
- [`symphony-pdflow-integration.md`](symphony-pdflow-integration.md) — isolated
  coding-agent orchestration and the PDflow resource/artifact boundary.
- [`script.md`](script.md) — launcher and script catalogue.

## Learn materials

The lessons, GUI atlas, Tcl walkthroughs, workbook, and tool references live
under [`../learn/`](../learn/). Start at [`../learn/README.md`](../learn/README.md).

## Studio routes

- `/flow` — RTL-to-finish workbench.
- `/lab` — current physics and DSE run.
- `/pkg` — packaging and phase-two tools.
- `/tools` — direct tool execution and live job output.

Every route reads current reports and displays unavailable inputs explicitly.
