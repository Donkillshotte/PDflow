# Installation

Full environment setup for Ubuntu 22.04 / 24.04. For day-to-day commands after install, see [operations.md](operations.md).

## Cloud Agent (recommended for a fast bootstrap)

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

The ORFS script derives the quarterly tag from the installed OpenROAD version
(for example `26Q2-...` → `26Q2`). Override with `ORFS_TAG=...`.

## Tool versions (reference)

| Tool | Version | Source |
|---|---|---|
| [OpenROAD](https://github.com/The-OpenROAD-Project/OpenROAD) | 26Q2 | Precision Innovations `.deb` ([VaultLink](https://vaultlink.precisioninno.com/)) |
| [OpenSTA](https://github.com/parallaxsw/OpenSTA) | 3.1.0 | built from source (with CUDD) |
| [ORFS](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts) | 26Q2 | tag aligned to OpenROAD |
| [Yosys](https://github.com/YosysHQ/yosys) | 0.63 | submodule from ORFS |
| [KLayout](https://www.klayout.de/) | 0.30.11 | official `.deb` |

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

`openroad` and `klayout` install system-wide from `.deb` packages.

## Quick verification

```bash
openroad -version
sta -version
yosys -V
klayout -v
./scripts/run_opensta_example.sh   # min/max timing smoke on Nangate45
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
| ORFS tag mismatch | `ORFS_TAG` aligned to `openroad -version` (26Q2) |

## Notes

- Precision Innovations OpenROAD binaries include OpenSTA internally; standalone `sta` is for STA outside the flow.
- `run_gcd_flow.sh` passes `openroad`, `sta`, and `yosys` from `PATH` into ORFS.
- `tcl-dev` is required for yosys Tcl integration (`-c` scripts in ORFS).
- OpenROAD GUI (`openroad -gui`) needs Qt/X11; use Desktop on Cloud Agents or `Xvfb` headless.
