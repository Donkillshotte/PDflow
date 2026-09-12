# PDflow

PDflow is a local RTL-to-GDS and power-integrity workspace built around
OpenROAD/ORFS. It contains three deliberately separate surfaces:

| Surface | Purpose | Entry point |
|---|---|---|
| Course / Studio | guided RTL → GDS learning and live signoff | [`learn/README.md`](learn/README.md), [`studio/README.md`](studio/README.md) |
| Lab | multi-fidelity DSE, PDN and solver experiments | [`learn/dse/README.md`](learn/dse/README.md) |
| Product | same-invocation design comparisons | [`learn/dse/product.md`](learn/dse/product.md) |

## Live-data rule

Reports are observations of the invocation that produced them. No committed
campaign snapshot, frozen measurement, historical ledger, or fixed QoR value
is used to label a current design. A comparison is valid only when the report
declares a shared `run_id`, compatible artifact fingerprints, and an explicit
`comparison_scope`.

The contract is documented in
[`learn/reference/live-analysis.md`](learn/reference/live-analysis.md).

## Quick start

For a new Linux workstation, use the native installer once:

```bash
./install.sh --yes
pdflow
```

The installer provisions the native toolchain and creates the single-command
desktop launcher. Read [`docs/installer.md`](docs/installer.md) before using
custom prefixes or a non-interactive host. It never installs Docker as a
runtime substitute for EDA.

For an already prepared checkout:

```bash
./scripts/run_studio.sh                 # http://127.0.0.1:43217
./scripts/learn_physical_design.sh --check
export PYTHONPATH=learn:learn/scripts
python3 learn/scripts/test_signoff_honesty.py
python3 learn/scripts/test_lab_physics.py
```

For heavy local analysis, set `ALLOW_HEAVY_ANALYSIS=1` where required. The
repository wrappers use a 600-second analysis timeout and keep every run in
its own output directory. Missing optional engines are reported as `GAP`; no
previous report is substituted.

## Studio

Studio exposes FlowLab at `/flow`, the DSE lab at `/lab`, the package surface
at `/pkg`, and tool actions at `/tools`. Each action returns a live job and
report path. The UI reads those artifacts after the job completes and does not
silently merge results from another invocation.

See [`docs/README.md`](docs/README.md) for the repository map and
[`docs/operations.md`](docs/operations.md) for local commands.

## Optional Symphony orchestration

Symphony can dispatch opt-in GitHub issues to isolated Codex app-server
workspaces. It is a coding-task coordinator; PDflow's local agent remains the
only authority for native EDA, resources, artifacts, and signoff. Validate the
contract with `./scripts/verify_symphony.sh`, then see
[`docs/symphony-pdflow-integration.md`](docs/symphony-pdflow-integration.md)
before starting the native launcher.
