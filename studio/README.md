# Studio

Studio is the local app surface for the course, FlowLab, lab, package, and
tool runners. It uses the same scripts as the CLI and does not invent data.
The certified runtime is the native Linux host toolchain described in
[`../docs/native-toolchain.md`](../docs/native-toolchain.md); the local agent
is the only process owner for EDA binaries.

## Run

```bash
./scripts/run_studio.sh
(cd studio && ../scripts/run_resource_job.sh studio-npm-ci npm ci)
(cd studio && ../scripts/run_resource_job.sh studio-lint npm run lint)
(cd studio && npm run build)

# Native desktop shell (requires Rust/Cargo and WebKitGTK development files)
source "$HOME/.cargo/env" 2>/dev/null || true
(cd studio/src-tauri && ../../scripts/run_resource_job.sh studio-tauri-build cargo tauri build)
```

`run_studio.sh` is intended for interactive development. The first Next.js
development compile can use substantial CPU and memory, especially after a
clean checkout. For acceptance runs or constrained desktop sessions, use the
packaged Tauri AppImage/deb instead; it avoids the development compiler while
retaining the native local-agent and EDA-tool integration.

## Routes

| Route | Purpose |
|---|---|
| `/flow` | RTL-to-finish FlowLab workbench |
| `/lab` | current DSE and physics run |
| `/pkg` | package and phase-two tools |
| `/tools` | direct actions, jobs, logs, inspect and viewers |
| `/lessons` | course wizard |
| `/product` | same-invocation product comparison |

## Live job contract

Each action returns a job id, live log, status, and report/artifact paths. The
client refreshes the current report after the job changes state. The server
keeps the action timeout aligned with the 600-second heavy-analysis default.
The job lock is single-flight: one mutating action owns the workspace at a
time, and cancellation or orphan recovery is visible in the operations panel.
Missing inputs or engines are shown as `GAP`, `FAIL`, or `REFUSED`; an older
report is never used to complete a card.

The current-data rules are in
[`../learn/reference/live-analysis.md`](../learn/reference/live-analysis.md).
The API surface includes `/api/run`, `/api/jobs`, `/api/inspect`,
`/api/viewer`, `/api/story`, `/api/lab`, `/api/product`, and `/api/signoff`.

Native OpenROAD windows require the local desktop. Browser-safe ODB inspection
uses the Web Viewer endpoint and still returns the current artifact path.

The canonical finish/candidate isolation contract is documented in
[`docs/flowlab-candidates.md`](docs/flowlab-candidates.md).
