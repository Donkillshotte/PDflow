# PDflow Desktop

This directory contains the Linux-first Tauri shell. The web UI remains
available through npm run dev for browser smoke tests; the desktop shell
starts the same React UI and owns the lifecycle of the Python local agent.

The agent remains the only component allowed to launch EDA tools. Tauri only
starts/stops the agent with structured arguments. OpenROAD and KLayout are
deliberately external native windows, while their recognized artifacts and
reports return to the PDflow UI through the agent API.

Prerequisites for a local desktop build:

- Rust/Cargo and the Linux WebKitGTK development libraries;
- Node.js/npm for the Studio frontend;
- Python 3 and the configured local EDA tools.

The checked-in build is native-host only. `build_tauri_frontend.sh` creates a
Next standalone server and bundles the selected native Node runtime; Tauri
starts that server as a local process in release builds and starts the Python
local agent through its structured command bridge. No Docker/container runtime
is used by the desktop shell.

From the repository root, build with:

```bash
source scripts/native_eda_env.sh
export PD_FLOW_NODE=/path/to/node
source "$HOME/.cargo/env" 2>/dev/null || true
cd studio/src-tauri
../../scripts/run_resource_job.sh studio-tauri-build cargo tauri build
```

For a checkout outside the current working directory, set
`PD_FLOW_REPO_ROOT=/absolute/path/to/PDflow` before launching the desktop
binary. The project root is intentionally not guessed from arbitrary user
paths: it is validated for the `learn/` tree and the shared tool registry.

The packaged application requires the same native Linux EDA executables as
the browser/agent deployment. Verify them with
`scripts/verify_native_eda.sh` before running the desktop acceptance gate.

When runtime GTK/WebKit libraries are present but system development packages
are unavailable, use the rootless native sysroot bootstrap from the repository
root:

```bash
./scripts/bootstrap_native_build_sysroot.sh
source scripts/native_eda_env.sh
cd studio
../scripts/run_resource_job.sh studio-tauri-build cargo tauri build
```

It downloads Debian/Kali packages into the user cache and extracts them under
`~/.local/pdflow-build-sysroot`; it does not use Docker, sudo, or the system
package database. Set `PD_FLOW_BUILD_SYSROOT` to use another user-owned
prefix. The shared resource runner exports the required pkg-config, compiler,
linker, and native `pkgconf` facade settings automatically.

## Runtime diagnostics

The release shell starts Next and the local agent as owned child processes.
It clears AppImage-specific `PYTHONHOME`/`PYTHONSTARTUP` values before
starting the host Python interpreter, and uses `/usr/bin/python3` by default.
Set `PD_FLOW_AGENT_PYTHON` when a different host interpreter is required.
Startup and child-process diagnostics are kept under
`.pdflow/agent/desktop-bootstrap.log`, `.pdflow/agent/next-server.log`, and
`.pdflow/agent/agent.log`. Each current log is bounded at 16 MiB and the
previous session is retained as a single `.1` rotation; the bootstrap log is
bounded as well. stdout/stderr are drained by native background pumps, so a
chatty child cannot block on a full pipe or grow the desktop process memory
without limit. When the desktop exits, it terminates both child processes and
waits for them, and each child is placed in its own process group. Normal
shutdown sends TERM and escalates to KILL after a bounded wait; on Linux a
parent-death signal also stops the child if the Tauri process crashes before
its exit hook runs. A failed launch therefore does not leave a Next server or
local agent orphaned on ports `43217` or `43219`.

Run the packaged AppImage directly during desktop acceptance. The AppImage
must not be placed around `run_resource_job.sh` for its entire lifetime: the
shared heavy-job lease is intended for individual builds, tests, and EDA
jobs, and a long-lived shell wrapper would block those jobs. OpenROAD and
KLayout are launched natively by the local agent, which still applies the
single-slot cgroup and reports the native PID, log, resource sample, and
termination cause back to Studio.
