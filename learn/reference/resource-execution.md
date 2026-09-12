# Bounded local resource execution

PDflow runs builds, native EDA jobs, and long test suites through one Linux
resource executor. The executor is intentionally strict: it requires cgroup
v2 and a working `systemd --user` manager, and refuses a heavy job when that
isolation cannot be established. It never falls back to an unbounded host
process or to Docker.

## Default policy

The shared slot is a host-wide advisory lock under
`$XDG_RUNTIME_DIR/pdflow/heavy-job.lock`. Only one heavy workload can own the
slot at a time. A queued workload waits until the slot is free, the host
reports at least 4 GiB of `MemAvailable`, and PSI reports `full_avg10` at or
below the configured pressure threshold. If either telemetry source is
unavailable, PDflow refuses to start the heavy job instead of guessing.

Each workload runs as a transient user service with these limits:

| Resource | Default |
|---|---:|
| `MemoryMax` | 6 GiB |
| `MemoryHigh` | 5 GiB |
| `MemorySwapMax` | 512 MiB |
| `CPUQuota` | 400% (four CPU equivalents) |
| subprocess timeout | 600 seconds |
| complete log cap | 64 MiB per job |
| in-memory log tail | 16 KiB |
| maximum memory `full_avg10` | 10% |
| native numerical/build workers | 4 (or lower CPU quota) |

`MemoryHigh` applies containment before the hard limit. A cgroup OOM is
reported as a resource failure and cannot produce a validated result. The
host is not killed along with the workload.

## Commands

Run a top-level build, test, or EDA suite from the repository root:

```bash
./scripts/run_resource_job.sh native-check ./scripts/verify_native_eda.sh
```

The wrapper writes a complete bounded log below `/tmp/pdflow-resource-logs/`
unless `PD_FLOW_RESOURCE_LOG_FILE` is supplied. It passes argv as structured
arguments and sets `PD_FLOW_RESOURCE_ACTIVE=1` inside the service so nested
PDflow wrappers continue in the same cgroup instead of acquiring the slot
again. Nested execution is accepted only when `/proc/self/cgroup` also proves
that the process is inside a PDflow-owned transient service; setting the
environment variable manually cannot bypass the guard.

The local agent uses the same executor for every allowlisted job. Its health
response exposes `resources.available`, the backend, limits, host headroom,
and the lock path. Job and report records add `resource` and
`termination_cause` fields. The cause is one of `memory`, `timeout`,
`cancelled`, `refused`, `crash`, or `resource_isolation` when a completed
result cannot be trusted. `refused` is reserved for a repository-owned safety
refusal such as an attempt to recook an existing finish or to run a controlled
preview with missing inputs; it is reported as job state `GAP` and never as a
validated result.

## Configuration

The safe defaults are active without configuration. A local operator may set
the following variables for diagnostics or a controlled machine profile:

```bash
PD_FLOW_RESOURCE_MEMORY_MAX=6GiB
PD_FLOW_RESOURCE_MEMORY_HIGH=5GiB
PD_FLOW_RESOURCE_SWAP_MAX=512MiB
PD_FLOW_RESOURCE_CPU_QUOTA_PERCENT=400
PD_FLOW_RESOURCE_MIN_AVAILABLE=4GiB
PD_FLOW_RESOURCE_LOG_MAX=64MiB
PD_FLOW_RESOURCE_LOG_TAIL=16KiB
PD_FLOW_RESOURCE_MAX_FULL_PRESSURE_AVG10=10
PD_FLOW_NUM_THREADS=4
PD_FLOW_TIMEOUT_S=600
```

Any value that increases the memory, swap, or CPU defaults is rejected unless
`PD_FLOW_RESOURCE_ALLOW_INCREASE=1` is explicitly present. A timeout above the
600-second default is rejected unless `PD_FLOW_ALLOW_TIMEOUT_INCREASE=1` is
also explicitly present, and the maximum accepted timeout is 3600 seconds.
The pressure threshold is a percentage from Linux PSI; increasing it above
10% additionally requires `PD_FLOW_RESOURCE_ALLOW_INCREASE=1`. Lowering the
host headroom below 4 GiB additionally requires
`PD_FLOW_RESOURCE_ALLOW_UNSAFE_OVERRIDE=1`. These overrides belong in a local
operator environment and should be recorded with the run provenance.

The executor caps common OpenMP/BLAS/Rayon and CMake worker variables to the
same four-CPU budget (or a lower configured quota). Direct native-tool shell
launches receive the same defaults after sourcing `scripts/native_eda_env.sh`.

### User-owned build tools

The fast gate also supports a native, user-owned CMake/CTest and Eigen prefix
when the host does not provide those packages system-wide. Set
`PD_FLOW_BUILD_TOOLS_PREFIX` to the prefix containing
`usr/bin/cmake`, `usr/bin/ctest`, and `usr/share/eigen3/cmake`, and include its
runtime library directory in `LD_LIBRARY_PATH` when required by the packaged
CMake binary:

```bash
export PD_FLOW_BUILD_TOOLS_PREFIX=/absolute/path/to/pdflow-build-tools
export LD_LIBRARY_PATH="${PD_FLOW_BUILD_TOOLS_PREFIX}/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
./scripts/ci_fast_gates.sh
```

This path is used only to configure and test the native engine; it does not
replace OpenROAD, OpenSTA, KLayout, Yosys, Icarus, ngspice, or any other EDA
executable. `ci_fast_gates.sh` fails if the explicitly selected CMake/CTest
tool cannot configure, build, or run `dpn_native`; it skips that gate only
when neither a system toolchain nor an explicitly configured local prefix is
available.

## Diagnostics and recovery

Check the backend without starting a workload:

```bash
PYTHONPATH=learn python3 learn/pdflow_resource_runner.py status
```

Inspect a running or recently completed unit with:

```bash
systemctl --user status pdflow-job-<job-id>.service --no-pager
journalctl --user -u pdflow-job-<job-id>.service --no-pager
```

The agent terminates the complete cgroup on cancellation and timeout. An
agent restart marks persisted `QUEUED` and `RUNNING` records as `ORPHANED`.
Transient service units are stopped and their result is recorded before the
resource lock is released.

## Non-destructive behavior

The executor never writes a protected FlowLab finish. Generated build caches,
stale standalone bundles, and fetched source trees are moved to uniquely
named `.stale-*` or temporary directories before replacement. GUI capture
helpers terminate only the OpenROAD process they launched, using its process
group or recorded PID; they do not scan and kill unrelated user sessions.
