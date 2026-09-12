#!/usr/bin/env bash
set -euo pipefail

# Build the pinned OpenROAD checkout as a native host executable.
#
# The two host flags work around the glibc 2.42 C23 memchr macro exposed to
# Bazel's bundled sed tools. The tinycthread include makes SCIP see glibc's
# once_flag declaration before its compatibility header. Both flags are
# narrowly scoped to the affected source files and are needed on current
# Kali/Debian headers.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${REPO_ROOT}/scripts/run_resource_job.sh" build-openroad \
    bash "${BASH_SOURCE[0]}" "$@"
fi
OPENROAD_ROOT="${PDFLOW_OPENROAD_ROOT:-${REPO_ROOT}/tools/OpenROAD-flow-scripts/tools/OpenROAD}"
PREFIX="${PD_FLOW_EDA_PREFIX:-${HOME:-/home/kalishot}/.local/pdflow-eda}"
BAZELISK="${PDFLOW_BAZELISK:-${PREFIX}/bin/bazelisk}"
JOBS="${PDFLOW_OPENROAD_BUILD_JOBS:-4}"
TIMEOUT_SECONDS="${PDFLOW_OPENROAD_BUILD_TIMEOUT:-1800}"
DEST="${PDFLOW_OPENROAD_DEST:-${PREFIX}/native-openroad}"

if [[ ! -d "${OPENROAD_ROOT}" ]]; then
  printf 'OpenROAD checkout not found: %s\n' "${OPENROAD_ROOT}" >&2
  exit 1
fi

if [[ ! -x "${BAZELISK}" ]]; then
  printf 'Bazelisk not found or not executable: %s\n' "${BAZELISK}" >&2
  printf 'Set PDFLOW_BAZELISK or install it below %s/bin.\n' "${PREFIX}" >&2
  exit 1
fi

source "${REPO_ROOT}/scripts/native_eda_env.sh"
export PATH="$(dirname "${BAZELISK}"):${PATH}"
mkdir -p "${DEST}"

cd "${OPENROAD_ROOT}"
timeout "${TIMEOUT_SECONDS}s" "${BAZELISK}" run \
  --config=release \
  --jobs="${JOBS}" \
  --//:platform=gui \
  "--action_env=PATH=${PATH}" \
  "--host_per_file_copt=.*memchr[.]c@-Dweak_alias(...)=" \
  "--host_per_file_copt=.*rawmemchr[.]c@-Dweak_alias(...)=" \
  '--per_file_copt=.*tinycthread[.]c@-include/usr/include/stdlib.h' \
  //packaging:install -- "${DEST}"

# bazel/install.sh removes the main-repository runfiles after extraction, but
# OpenROAD's Tcl bootstrap uses them to locate the embedded Tcl library. Keep
# that small resource tree in the native installation.
TARFILE="$("${BAZELISK}" info bazel-bin)/packaging/openroad.tar"
if [[ -f "${TARFILE}" ]]; then
  tar -xf "${TARFILE}" -C "${DEST}" openroad.runfiles/_main
fi

printf 'Native OpenROAD installed from %s to %s\n' "${OPENROAD_ROOT}" "${DEST}"

# Install the matching native ODB binding when the modern source checkout is
# available.  It is required by vectorless ODB inspection and is intentionally
# kept beside the executable so the runtime can verify both files together.
ODB_ROOT="${PDFLOW_OPENROAD_ODB_ROOT:-${PREFIX}/src/openroad-26q3}"
if [[ -d "${ODB_ROOT}" ]]; then
  PDFLOW_OPENROAD_ODB_ROOT="${ODB_ROOT}" \
    PDFLOW_OPENROAD_DEST="${DEST}" \
    PDFLOW_BAZELISK="${BAZELISK}" \
    "${REPO_ROOT}/scripts/build_native_openroad_odb.sh"
else
  printf 'Native OpenDB source tree not found; set PDFLOW_OPENROAD_ODB_ROOT to enable it.\n' >&2
fi
