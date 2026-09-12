#!/usr/bin/env bash
# Run one build, test, or EDA workload through PDflow's shared Linux guard.
#
# Usage: run_resource_job.sh LABEL COMMAND [ARG ...]
# The guard serializes heavy work across PDflow processes and creates a
# transient systemd --user cgroup. There is deliberately no unisolated path.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# A resource-isolated job must still receive the same native EDA environment
# as an interactive PDflow launch. systemd --user may start the transient unit
# with a minimal PATH, so do not rely on the caller having sourced this file.
if [[ -f "${ROOT}/scripts/native_eda_env.sh" ]]; then
  # shellcheck source=scripts/native_eda_env.sh
  source "${ROOT}/scripts/native_eda_env.sh"
fi

# Rustup is intentionally installed per user on Linux workstations. Make its
# native Cargo tools available to guarded desktop builds even when the
# interactive shell has not sourced ~/.cargo/env yet.
_PD_FLOW_CARGO_HOME="${CARGO_HOME:-${HOME:-/home/kalishot}/.cargo}"
if [[ -d "${_PD_FLOW_CARGO_HOME}/bin" ]]; then
  export PATH="${_PD_FLOW_CARGO_HOME}/bin:${PATH}"
fi
unset _PD_FLOW_CARGO_HOME

# Keep native desktop builds usable on workstations where the runtime GTK/WebKit
# libraries are installed but the corresponding development packages cannot be
# installed system-wide.  The sysroot is optional and completely user-owned;
# when present it supplies pkg-config metadata, headers and linker search paths
# without replacing the host runtime or using a container.
_PD_FLOW_BUILD_SYSROOT="${PD_FLOW_BUILD_SYSROOT:-${HOME:-/home/kalishot}/.local/pdflow-build-sysroot}"
_PD_FLOW_SYSROOT_PKG_CONFIG="${_PD_FLOW_BUILD_SYSROOT}/usr/bin/pkg-config"
if [[ -x "${_PD_FLOW_SYSROOT_PKG_CONFIG}" ]]; then
  export PD_FLOW_BUILD_SYSROOT="${_PD_FLOW_BUILD_SYSROOT}"
  export PATH="${ROOT}/scripts:${PD_FLOW_BUILD_SYSROOT}/usr/bin:${PATH}"
  export PKG_CONFIG="${_PD_FLOW_SYSROOT_PKG_CONFIG}"
  export PKG_CONFIG_SYSROOT_DIR="${_PD_FLOW_BUILD_SYSROOT}"
  export PKG_CONFIG_PATH="${PD_FLOW_BUILD_SYSROOT}/usr/lib/x86_64-linux-gnu/pkgconfig:${PD_FLOW_BUILD_SYSROOT}/usr/share/pkgconfig${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}"
  export C_INCLUDE_PATH="${PD_FLOW_BUILD_SYSROOT}/usr/include/x86_64-linux-gnu:${PD_FLOW_BUILD_SYSROOT}/usr/include${C_INCLUDE_PATH:+:${C_INCLUDE_PATH}}"
  export CPLUS_INCLUDE_PATH="${PD_FLOW_BUILD_SYSROOT}/usr/include/x86_64-linux-gnu:${PD_FLOW_BUILD_SYSROOT}/usr/include${CPLUS_INCLUDE_PATH:+:${CPLUS_INCLUDE_PATH}}"
  export LIBRARY_PATH="${PD_FLOW_BUILD_SYSROOT}/usr/lib/x86_64-linux-gnu:${PD_FLOW_BUILD_SYSROOT}/usr/lib${LIBRARY_PATH:+:${LIBRARY_PATH}}"
  export LD_LIBRARY_PATH="${PD_FLOW_BUILD_SYSROOT}/usr/lib/x86_64-linux-gnu:${PD_FLOW_BUILD_SYSROOT}/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
fi
unset _PD_FLOW_BUILD_SYSROOT _PD_FLOW_SYSROOT_PKG_CONFIG

if [[ "$#" -lt 2 ]]; then
  echo "usage: $0 LABEL COMMAND [ARG ...]" >&2
  exit 2
fi

LABEL="$1"
shift
TIMEOUT="${PD_FLOW_TIMEOUT_S:-600}"
if [[ ! "${TIMEOUT}" =~ ^[1-9][0-9]*$ ]] || [[ "${TIMEOUT}" -gt 3600 ]]; then
  echo "PDflow resource runner requires PD_FLOW_TIMEOUT_S in the range 1..3600" >&2
  exit 2
fi

# Nested stages inherit this marker and run inside the already acquired slot.
# The marker is accepted only when /proc confirms a PDflow-owned cgroup; an
# operator cannot bypass isolation by exporting the variable manually.
if "${ROOT}/scripts/resource_guard.sh"; then
  exec "$@"
fi

WORKDIR="${PD_FLOW_RESOURCE_CWD:-${PWD}}"
if [[ ! -d "${WORKDIR}" ]]; then
  echo "PDflow resource runner working directory is missing: ${WORKDIR}" >&2
  exit 2
fi

RUNNER_LOG_ARGS=()
if [[ -n "${PD_FLOW_RESOURCE_LOG_FILE:-}" ]]; then
  RUNNER_LOG_ARGS+=(--log-file "${PD_FLOW_RESOURCE_LOG_FILE}")
fi

export PYTHONPATH="${ROOT}/learn${PYTHONPATH:+:${PYTHONPATH}}"
exec python3 "${ROOT}/learn/pdflow_resource_runner.py" run \
  --label "${LABEL}" \
  --cwd "${WORKDIR}" \
  --timeout "${TIMEOUT}" \
  "${RUNNER_LOG_ARGS[@]}" \
  -- "$@"
