# Native Linux toolchain

PDflow is certified against a native host toolchain. The production path does
not use Docker, a cloud worker, a browser-side shell, or a synthetic layout
fallback. The local agent launches allowlisted host processes and records the
executable, version, inputs, outputs, hashes, logs, and status for every run.

## Installed reference host

The current Linux x86-64 reference installation is recorded in
[`../config/pdflow/native_toolchain.json`](../config/pdflow/native_toolchain.json):

| Tool | Native version | Role |
|---|---:|---|
| OpenROAD | 26Q3 | database, physical design, GUI, OpenRCX |
| OpenSTA | 2.7.0 | standalone static timing |
| KLayout | 0.30.0 | native GUI, DRC, filtered LVS comparison |
| Yosys / ABC | 0.66 | synthesis, equivalence, formal helpers |
| Icarus Verilog | 13.0 | RTL and gate-level simulation |
| ngspice | 47 | System PDN and SPICE simulation |

OpenROAD and OpenSTA are built from the same pinned native OpenROAD checkout.
The OpenDB Python binding is built from that checkout as well, so ODB-aware
analysis cannot silently read an incompatible schema. Xyce and FasterCap are
repository-local native lab backends; HotSpot remains optional. Commercial
tools are represented as explicit `GAP` entries when no licensed binary and
PDK setup are present.

## Prefix and environment

New workstations should use [`installer.md`](installer.md) and run
`./install.sh --yes`; the installer creates the prefix and performs the native
verification gate. The commands below are for an existing or custom prefix.

The default per-user prefix is `~/.local/pdflow-eda`. Source the environment
before invoking a shell flow, a local agent, or a native GUI:

```bash
source scripts/native_eda_env.sh
./scripts/verify_native_eda.sh
```

`PD_FLOW_EDA_PREFIX` selects another native prefix. The environment exports
the wrapper paths, shared-library paths, Tcl/Yosys data paths, SPICE data
paths, and the matching OpenDB binding location. It does not invoke a
container or rewrite the system package database.

The checked wrappers in `tools/native/bin/` are intentionally the first
registry candidates. They resolve to native executables and are used by both
the browser development facade and the Tauri desktop shell.

The Tauri shell sanitizes the Python child environment before starting the
agent: `PYTHONHOME` and `PYTHONSTARTUP` are removed, the host Python module
path is rebuilt from the repository and system packages, and
`PYTHONNOUSERSITE=1` prevents an AppImage mount or a user-site package from
changing the agent runtime. `PD_FLOW_AGENT_PYTHON` may be set to an explicit
host interpreter when the workstation uses a virtual environment. Desktop
startup diagnostics are written to `.pdflow/agent/desktop-bootstrap.log` and
the agent's stdout/stderr to `.pdflow/agent/agent.log`; neither log contains
the authentication token.

## Provisioning and rebuilds

The existing `scripts/01_install_openroad.sh` through
`scripts/04_setup_orfs.sh` are legacy system-wide Ubuntu installers and still
require root privileges. The current Linux reference host uses the native
prefix above because it is also valid on Debian/Kali hosts without changing
the system installation. Do not replace a missing native dependency with a
Docker image.

To rebuild the native OpenROAD/OpenDB components from source:

```bash
source scripts/native_eda_env.sh
PDFLOW_OPENROAD_ROOT="$PD_FLOW_EDA_PREFIX/src/openroad-26q3" \
  PDFLOW_OPENROAD_ODB_ROOT="$PD_FLOW_EDA_PREFIX/src/openroad-26q3" \
  scripts/build_native_openroad.sh
```

`scripts/build_native_openroad.sh` uses the pinned source checkout and a
600-second-or-longer build timeout by default for each controlled build step.
`scripts/build_native_openroad_odb.sh` can be run independently when only the
Python binding needs to be refreshed.

## Discovery policy

`config/pdflow/tool_registry.json` is the single declarative registry. Each
descriptor states whether the tool is required, its executable candidates,
version probe, capabilities, accepted inputs, outputs, launch profiles, and
default timeout. The agent reports one of:

- `READY`: executable and version probe succeeded;
- `MISCONFIGURED`: executable exists but its probe failed;
- `MISSING`: no allowlisted executable was found;
- `GAP`: a requested action cannot run because a required tool or input is not
  available.

The six core tools are required for the native product flow. Xyce, FasterCap,
and HotSpot are optional lab capabilities and never promote a Product report.

Native tools do not all implement a conventional `--version` option. The
registry therefore records the exact bounded probe and, where an upstream
utility returns a documented non-zero code for help/version output, the
allowed exit code explicitly. For example, FasterCap is probed with
`--version` and HotSpot with `-h`; the declared non-zero exit codes are
accepted only for those bounded probes, neither probe is treated as a
successful job, and neither is allowed to launch a GUI. A `version_label` is
used for HotSpot because its native banner does not contain a release string.
This keeps the
registry honest while still allowing the actual native executable to be
verified.

## Native GUI contract

The UI sends a typed tool request to the local agent. It never constructs a
shell string. The agent resolves an `artifact_id` against the project
allowlist, verifies finish/candidate authority, launches the native process
with an argument array, and records its PID and log. OpenROAD and KLayout are
external native windows. A layout is updated in PDflow only after the tool
writes a recognized artifact; unsaved GUI state is shown as pending, not
reconstructed by the application.

## Verification evidence

The reference RTL-to-GDS gate is:

```bash
source scripts/native_eda_env.sh
timeout 600s scripts/test_native_rtl_e2e.sh
```

The gate uses the real `gcd.v` RTL, invokes native Yosys, OpenROAD, OpenSTA,
KLayout, Icarus, ngspice, and repository-local Xyce/FasterCap where their
surface is applicable. It validates that final GDS/ODB/DEF/SPEF/netlist
artifacts exist, are non-empty, remain inside the expected variant directory,
and that the protected FlowLab finish hash is unchanged. See
[`testing.md`](testing.md) for the complete quick, heavy, UI, and recovery
matrix.
