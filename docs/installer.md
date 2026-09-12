# PDflow Native Linux Installer

This document is the operator guide for installing a complete PDflow
workstation from a clean checkout. The supported deployment is Linux x86-64
with native host processes. Docker, Podman, cloud workers, and containerized
EDA are not part of the certified runtime path.

## Quick start

From a fresh checkout:

```bash
git clone https://github.com/Donkillshotte/PDflow.git
cd PDflow
./install.sh --yes
~/.local/bin/pdflow
```

The installer asks `apt` to install missing system prerequisites through
`sudo`, installs user-owned build helpers, verifies the native EDA toolchain,
installs Studio dependencies, builds the Tauri desktop bundle, and creates a
launcher at `~/.local/bin/pdflow`. The first run can take a long time because
OpenROAD may be compiled from its pinned source revision.

If the desktop shell is not needed yet:

```bash
./install.sh --yes --no-desktop
~/.local/bin/pdflow --web
```

The browser Studio remains a development and diagnostic surface. It uses the
same local agent and native tool registry as the desktop shell.

## Check without changing the host

Use the read-only check before or after installation:

```bash
./install.sh --check
```

The check never runs `apt`, downloads an archive, changes a checkout, builds a
tool, or starts the application. It reports missing Node, Bazelisk, ORFS,
native EDA, Cargo/Tauri, or the installed AppImage as `GAP` and exits nonzero
until the requested profile is complete.

The lower-level checks are useful when diagnosing one layer:

```bash
./scripts/install_node_runtime.sh --check
./scripts/install_bazelisk.sh --check
source scripts/native_eda_env.sh
./scripts/verify_native_eda.sh
./scripts/test_installer.sh
```

`verify_native_eda.sh` performs real native version probes and smoke operations
for OpenROAD, OpenSTA, KLayout, Yosys, Icarus Verilog, and ngspice. A passing
probe is not a Product signoff: the flow still has to generate the required
current-run artifacts and reports.

## What the installer installs

The installer has three layers:

1. **Distribution prerequisites.** On Debian, Ubuntu, and Kali it installs
   missing compiler, CMake, Python, GTK/WebKitGTK, Rust, and EDA packages with
   `apt`. Package names are selected for the WebKitGTK and AppIndicator
   variants available in the current apt indexes.
2. **User-owned pinned tools.** Node.js `20.19.5` and Bazelisk `1.29.0` are
   downloaded over HTTPS and verified against pinned SHA-256 digests before
   extraction. They are installed below `~/.local/share/pdflow` and
   `~/.local/pdflow-eda` respectively.
3. **PDflow runtime.** ORFS is cloned at the pinned 26Q2 revision when the
   checkout does not already contain it. If a usable native OpenROAD/OpenSTA
   installation is not already present, the installer clones OpenROAD 26Q3 at
   the pinned commit and builds the native executable and OpenDB binding.
   Studio dependencies are installed with `npm ci`; the Tauri AppImage is
   built and copied atomically to the user application directory.

The installer does not silently replace a dirty ORFS or OpenROAD checkout. It
reports the exact path and asks for an explicit operator override after the
tree has been reviewed. Existing local finish artifacts are never used as a
write target by the installer.

## Native tool policy

The runtime registry resolves tools through `tools/native/bin`. These wrappers
prefer the user-owned PDflow prefix and fall back to explicitly known native
host locations such as `/usr/bin` when no prefix copy exists. They do not
launch a container or reinterpret a missing native executable as a successful
proxy.

The reference inventory is:

| Tool | Role | Reference |
|---|---|---|
| OpenROAD | floorplan, placement, CTS, route, PDN, native GUI | 26Q3 pinned source build |
| OpenSTA | timing analysis and WNS/TNS/slack reports | 2.7.0 from matching source |
| KLayout | GDS inspection, DRC/LVS GUI and batch checks | 0.30.x native host package |
| Yosys/ABC | RTL synthesis and equivalence support | 0.66 native host package |
| Icarus Verilog | RTL and gate-level simulation | 13.0 native host package |
| ngspice | native SPICE and System PDN analysis | 47 native host package |

Xyce, FasterCap, HotSpot, and other Lab adapters remain optional. Their
absence is reported as `GAP`; it does not change the status of the required
native tools and never becomes an implicit Product signoff.

## Resource safety

Every build, long test, and heavy EDA workload is sent through
`scripts/run_resource_job.sh`. The executor requires cgroup v2 and a working
`systemd --user` manager. If those prerequisites are unavailable, a heavy job
is refused rather than run unbounded.

The default policy is:

| Limit | Default |
|---|---:|
| MemoryMax | 6 GiB |
| MemoryHigh | 5 GiB |
| Swap | 512 MiB |
| CPU quota | 400% |
| Job timeout | 600 seconds |
| Complete log | 64 MiB per job |
| In-memory log tail | 16 KiB |

Only one heavy workload owns the shared slot. The installer therefore queues
or refuses a concurrent build instead of competing with a running EDA flow.
Timeout, cancellation, crash, and cgroup memory exhaustion are recorded as
different termination causes. A resource stop cannot produce a validated
report.

To inspect the executor without launching a job:

```bash
PYTHONPATH=learn python3 learn/pdflow_resource_runner.py status
```

Increasing memory, CPU, swap, or timeout limits requires the explicit override
variables documented in
[`../learn/reference/resource-execution.md`](../learn/reference/resource-execution.md).
Record such overrides in the run provenance and remove them after the
controlled experiment.

## Desktop launchers

After a successful full install:

```bash
pdflow                 # native AppImage, the default
pdflow --desktop       # require the native AppImage
pdflow --web           # start the browser Studio and open port 43217
pdflow --verify        # native EDA verification through the resource guard
```

The installer also creates a desktop entry under
`~/.local/share/applications/PDflow.desktop` and stores the AppImage under
`~/.local/share/pdflow/PDflow.AppImage` by default. The application does not
hold the heavy-job lease for its entire lifetime. Individual jobs launched by
the local agent acquire and release the guarded slot independently.

The packaged shell starts the Next standalone server and Python local agent as
owned child processes. OpenROAD and KLayout remain native external windows;
their recognized artifacts, session state, logs, revisions, and stale
invalidations return to the PDflow UI through the agent.

## Alternate locations

All persistent installation locations can be changed without editing the
repository:

```bash
./install.sh --yes \
  --eda-prefix "$HOME/.local/pdflow-eda-workstation" \
  --node-prefix "$HOME/.local/share/pdflow/node-v20.19.5-linux-x64" \
  --app-dir "$HOME/.local/share/pdflow" \
  --bin-dir "$HOME/.local/bin"
```

The same values can be supplied with `PD_FLOW_EDA_PREFIX`,
`PD_FLOW_NODE_PREFIX`, `PD_FLOW_APP_DIR`, and `PD_FLOW_BIN_DIR`. The final
launcher records the resolved repository, EDA prefix, Node path, AppImage
path, and installation timestamp in the non-secret
`~/.local/share/pdflow/install.json` manifest.

## Troubleshooting

### The installer stops at a missing apt candidate

Refresh the distribution indexes and retry:

```bash
sudo apt-get update
./install.sh --yes
```

On a distribution with different package names, install equivalent native
development packages manually and use `--no-system-packages`; the final
verification still has to pass.

### OpenROAD source is dirty or at another commit

The installer refuses to realign it automatically. Preserve or copy the
checkout, inspect its changes, and either point `PD_FLOW_OPENROAD_ROOT` at a
clean pinned checkout or explicitly acknowledge the local build with
`PD_FLOW_ALLOW_DIRTY_OPENROAD=1`. A dirty build is not a certified reference
until its provenance and native verification have been reviewed.

### The resource executor is unavailable

Do not bypass it for a heavy build. Check cgroup and user-systemd support:

```bash
systemd-run --user --wait true
mount | grep cgroup2
PYTHONPATH=learn python3 learn/pdflow_resource_runner.py status
```

Fix the host session or run the installer again. A missing isolation backend is
an operational `GAP`, not a reason to run an unbounded OpenROAD build.

### The browser launcher cannot find Node

Install the pinned runtime explicitly and retry:

```bash
./scripts/install_node_runtime.sh
pdflow --web
```

The browser path accepts native Node 20.9+ through Node 22, while the
installer pins Node 20.19.5 for reproducible desktop builds. Node 24 is not
accepted by the Studio engine range.

### Tauri builds but no AppImage is installed

Inspect the guarded build log and bundle directory:

```bash
find studio/src-tauri/target/release/bundle -maxdepth 2 -type f -name '*.AppImage' -print
find /tmp/pdflow-resource-logs -maxdepth 1 -type f -print
```

The installer only publishes an AppImage after the guarded build completes
and the file exists. A previous installed AppImage is left intact when a new
build fails.

## Verification sequence

The recommended acceptance order is:

```bash
./scripts/test_installer.sh
source scripts/native_eda_env.sh
./scripts/verify_native_eda.sh
./scripts/ci_fast_gates.sh
timeout 600s ./scripts/test_native_rtl_e2e.sh
./scripts/test_studio_api.sh
./scripts/test_all_phases.sh
```

The E2E fixtures must use an isolated candidate workspace. Verify before and
after the run that the finish artifact hashes are identical. A `GAP`, `PROXY`,
`PARTIAL`, or `NOT_RUN` result is useful diagnostic information but cannot
close a Product signoff gate.

## Repository and synchronization policy

The Git repository contains source code, schemas, manifests, tests, scripts,
documentation, and small deterministic fixtures. It intentionally excludes:

- native tool installations and ORFS/PDK checkouts below `tools/`;
- `node_modules`, Next/Tauri build output, AppImages, and Debian packages;
- `.pdflow` runtime state, logs, simulation output, and generated reports;
- SSH key material, tokens, credentials, and other local secrets.

Those exclusions are safety and reproducibility boundaries, not missing
implementation. A new workstation recreates them with `./install.sh` and the
native verification gates. Before publishing a branch, inspect both tracked
and ignored state:

```bash
git status --short --ignored
git diff --check
git diff --stat
```

Never add a PAT, private key, generated finish, or local runtime directory to
the repository. The SSH artifacts used by a local developer checkout are
ignored explicitly and remain on the workstation.
