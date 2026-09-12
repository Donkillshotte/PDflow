# Native installation

> New users should start with [`installer.md`](installer.md): from the
> repository root, `./install.sh --yes` installs the native toolchain and
> creates the `pdflow` launcher. The lower-level commands below remain useful
> for diagnostics, controlled source rebuilds, and older workstations.

PDflow is certified for a Linux-first, native-host deployment. The runtime
does not use Docker as a substitute for the EDA toolchain: OpenROAD, OpenSTA,
KLayout, Yosys, Icarus Verilog and ngspice are launched as host processes by
the local agent. For day-to-day commands see [operations.md](operations.md).

The tested host installation is recorded in
[`config/pdflow/native_toolchain.json`](../config/pdflow/native_toolchain.json)
and uses the user-owned prefix `~/.local/pdflow-eda`. The certified inventory
currently contains OpenROAD 26Q3, OpenSTA 2.7.0, KLayout 0.30.0, Yosys 0.66,
Icarus Verilog 13.0 and ngspice 47.

After installing or rebuilding the tools, initialise the environment and run
the native verification gate:

```bash
source scripts/native_eda_env.sh
bash scripts/verify_native_eda.sh
```

The gate performs version probes plus real native smoke operations and ends
with `NATIVE EDA TOOLCHAIN VERIFIED` on success.

## Native source/build paths

OpenROAD and its standalone OpenSTA/ODB Python binding can be rebuilt with
the pinned source helpers:

```bash
source scripts/native_eda_env.sh
bash scripts/build_native_openroad.sh
bash scripts/build_native_openroad_odb.sh
```

The helpers install into `~/.local/pdflow-eda/native-openroad` and update no
system package database. The remaining host tools may be installed by the
distribution package manager or an audited user prefix; update the manifest
when versions change and rerun the verification gate. Optional Xyce,
FasterCap and HotSpot are repository-local lab adapters and do not replace a
required core tool.

## Desktop build

The Tauri shell is also built natively. It bundles a local Next standalone
server and starts both that server and the Python agent as local processes:

```bash
source scripts/native_eda_env.sh
export PD_FLOW_NODE=/absolute/path/to/node
source "$HOME/.cargo/env" 2>/dev/null || true
cd studio
../scripts/run_resource_job.sh studio-tauri-build cargo tauri build
```

### Rootless native desktop build dependencies

If the host already has the GTK/WebKit runtime but the `-dev` packages cannot
be installed system-wide, prepare the user-owned native build sysroot once:

```bash
./scripts/bootstrap_native_build_sysroot.sh
source scripts/native_eda_env.sh
cd studio
../scripts/run_resource_job.sh studio-tauri-build cargo tauri build
```

The bootstrap uses the existing Debian/Kali apt indexes, downloads packages to
`~/.cache/pdflow-apt/`, and extracts them to
`~/.local/pdflow-build-sysroot/`. It does not invoke `sudo`, modify the system
package database, use Docker, or write into the repository. The resource
runner detects this sysroot automatically through `PD_FLOW_BUILD_SYSROOT` and
configures `pkg-config`, headers, linker paths, and the bounded `pkgconf`
facade used by linuxdeploy. Override the locations explicitly when needed:

```bash
PD_FLOW_BUILD_SYSROOT=/absolute/sysroot \
PD_FLOW_BUILD_SYSROOT_CACHE=/absolute/deb-cache \
  ./scripts/bootstrap_native_build_sysroot.sh
```

The sysroot is a build input, not a replacement for the host GTK/WebKit
runtime. The packaged application still runs with the native Linux runtime
libraries installed on the target workstation.

Set `PD_FLOW_REPO_ROOT` when launching a packaged binary against a checkout
that is not the process working directory. See
[`studio/src-tauri/README.md`](../studio/src-tauri/README.md).

## Legacy installers and cloud bootstrap

The older `scripts/01_install_openroad.sh` … `04_setup_orfs.sh` scripts are
kept for controlled system-wide installations and are not the certified
runtime path. They require `sudo`, must be reviewed before use, and should be
followed by `verify_native_eda.sh`.

The historical cloud bootstrap scripts remain for compatibility and static
regression tests. They are not a substitute for the native-host acceptance
gate required for Product, Package and Lab validation.

## Cloud Agent (compatibility bootstrap)

Default profile is **core** (RTL→GDS + Studio, without standalone OpenSTA or heavy DSE/AES/Krylov):

```bash
PD_FLOW_PROFILE=core EDA_JOBS=2 bash scripts/cloud_agent_install.sh
./scripts/cloud_agent_smoke.sh          # versions only
./scripts/test_cloud_bootstrap.sh       # static checks
```

Profiles:

| Profile | Adds |
|---|---|
| `core` | RTL→GDS + Studio |
| `analysis` | `libdpn` / synthetic `dpn_test` |
| `full` | OpenSTA built from source |

AES, PDN meshes above ~20k R, and Krylov require `ALLOW_HEAVY_ANALYSIS=1`.
Crash-resilient log: [`.cursor/SETUP_LOG.md`](../.cursor/SETUP_LOG.md).

## Local install (step by step)

Scripts require `sudo` for apt packages:

```bash
./scripts/01_install_openroad.sh   # OpenROAD from prebuilt binaries
./scripts/02_install_opensta.sh    # CUDD + OpenSTA from source
./scripts/03_install_klayout.sh    # KLayout (for final GDS)
./scripts/04_setup_orfs.sh         # clone ORFS + build yosys
```

The installers are pinned by default: OpenROAD `26Q2-1164-g08f67ee5ec`,
KLayout `0.30.11`, CUDD/OpenSTA commit IDs, and ORFS `26Q2` commit
`036d106273e66855cd5214d49518fd0f0df7de61`. The binary installers verify
size and checksums before invoking `apt`. Deliberate upgrades must provide
`OPENROAD_VERSION` + `OPENROAD_SHA256`, or `KLAYOUT_VERSION` +
`KLAYOUT_SHA256`; source refs can be overridden with `CUDD_REF`,
`OPENSTA_REF`, and `ORFS_COMMIT`.

## Tool versions (reference)

| Tool | Version | Source |
|---|---|---|
| [OpenROAD](https://github.com/The-OpenROAD-Project/OpenROAD) | 26Q3 (`a9147cf3`) | native source build |
| [OpenSTA](https://github.com/parallaxsw/OpenSTA) | 2.7.0 | native source target from the OpenROAD tree |
| [ORFS](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts) | 26Q2 @ `036d106` | pinned tag commit |
| [Yosys](https://github.com/YosysHQ/yosys) | 0.66 | native host binary |
| Icarus Verilog | 13.0 | native host binary |
| [KLayout](https://www.klayout.de/) | 0.30.0 | native host binary |
| [ngspice](https://ngspice.sourceforge.io/) | 47 | native host binary |

Also in the tree: ngspice, **vyges-em-ir** (v0.1.33), HotSpot, Xyce (optional), FasterCap (optional).
OSS matrix: [learn/reference/oss-integrations.md](../learn/reference/oss-integrations.md).

## Layout under `tools/` (gitignored)

```
tools/
├── OpenROAD-flow-scripts/   # ORFS: flow, PDK, example designs
├── src/                     # OpenSTA and CUDD sources
├── cudd/                    # CUDD install
├── opensta/                 # OpenSTA install → /usr/local/bin/sta
├── yosys/                   # yosys install → /usr/local/bin/yosys
└── vyges-em-ir/             # Apache-2.0 binary (GitHub Releases)
```

The certified wrappers in `tools/native/bin` resolve the user-owned native
prefix and keep executable paths explicit for the registry and local agent.

## Quick verification

```bash
source scripts/native_eda_env.sh
bash scripts/verify_native_eda.sh
./scripts/run_opensta_example.sh   # native STA smoke on Nangate45
```

## Run the GCD reference flow

```bash
./scripts/run_gcd_flow.sh
```

Output: `tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/`
(`6_final.gds`, `6_final.odb`, reports).

Default `CORE_UTILIZATION=35` for the aggressive 0.46 ns tutorial SDC.
Override with `CORE_UTILIZATION=45`, for example.

Other PDK / design:

```bash
DESIGN_CONFIG=./designs/sky130hd/gcd/config.mk ./scripts/run_gcd_flow.sh
```

GUI (needs X11 / Desktop):

```bash
./scripts/run_gcd_flow.sh gui_final
```

## ORFS troubleshooting

| Problem | Fix |
|---|---|
| Missing `1_synth.odb` | `make synth` or FlowLab Synthesis phase |
| Floorplan 412 in Studio | Run synth first; verify `results/.../flowlab/` |
| Timing fail @ 0.46 ns | Normal on aggressive GCD tutorial; relax SDC in FlowLab |
| Lock `.studio-run.lock` | `./scripts/test_studio_api.sh` cleans it; or remove manually if stale |
| ORFS tag mismatch | `ORFS_TAG`/ `ORFS_COMMIT` are pinned to the tested 26Q2 pair |

## Notes

- The certified OpenROAD and OpenSTA binaries are native source-built executables; standalone `sta` is also used for STA outside the flow.
- `run_gcd_flow.sh` passes `openroad`, `sta`, and `yosys` from `PATH` into ORFS.
- `tcl-dev` is required for yosys Tcl integration (`-c` scripts in ORFS).
- OpenROAD GUI (`openroad -gui`) needs Qt/X11. The desktop shell opens it as an external native window and tracks recognized artifacts through the local agent.
