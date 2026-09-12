#!/usr/bin/env bash
set -euo pipefail

# Build and install the native OpenDB Python extension used by ODB-aware
# analysis helpers.  This is deliberately a separate target from the
# OpenROAD executable: upstream Bazel releases can ship a CLI/Tcl executable
# with embedded Python disabled while still providing the official ODB
# binding.  The extension is compiled on the host from the same OpenROAD
# checkout and is never replaced by a text parser or a container image.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${REPO_ROOT}/scripts/run_resource_job.sh" build-openroad-odb \
    bash "${BASH_SOURCE[0]}" "$@"
fi
PREFIX="${PD_FLOW_EDA_PREFIX:-${HOME:-/home/kalishot}/.local/pdflow-eda}"
OPENROAD_ROOT="${PDFLOW_OPENROAD_ODB_ROOT:-${PREFIX}/src/openroad-26q3}"
BAZELISK="${PDFLOW_BAZELISK:-${PREFIX}/bin/bazelisk}"
JOBS="${PDFLOW_OPENROAD_BUILD_JOBS:-4}"
TIMEOUT_SECONDS="${PDFLOW_OPENROAD_BUILD_TIMEOUT:-1800}"
DEST="${PDFLOW_OPENROAD_DEST:-${PREFIX}/native-openroad}/python"

if [[ ! -d "${OPENROAD_ROOT}" ]]; then
  printf 'OpenROAD source checkout not found: %s\n' "${OPENROAD_ROOT}" >&2
  printf 'Set PDFLOW_OPENROAD_ODB_ROOT to the matching native source tree.\n' >&2
  exit 1
fi
if [[ ! -x "${BAZELISK}" ]]; then
  printf 'Bazelisk not found or not executable: %s\n' "${BAZELISK}" >&2
  exit 1
fi

source "${REPO_ROOT}/scripts/native_eda_env.sh"
export PATH="$(dirname "${BAZELISK}"):${PATH}"

cd "${OPENROAD_ROOT}"
timeout "${TIMEOUT_SECONDS}s" "${BAZELISK}" build \
  --config=release \
  --jobs="${JOBS}" \
  "--action_env=PATH=${PATH}" \
  //src/odb:_odb.so

BAZEL_BIN="$(${BAZELISK} info bazel-bin)"
ODB_BUILD="${BAZEL_BIN}/src/odb"
[[ -f "${ODB_BUILD}/odb.py" ]] || { printf 'Missing generated odb.py\n' >&2; exit 1; }
[[ -f "${ODB_BUILD}/_odb.so" ]] || { printf 'Missing generated _odb.so\n' >&2; exit 1; }

mkdir -p "${DEST}"
install -m 0644 "${ODB_BUILD}/odb.py" "${DEST}/odb.py"
install -m 0755 "${ODB_BUILD}/_odb.so" "${DEST}/_odb.so"

PYTHONPATH="${DEST}${PYTHONPATH:+:${PYTHONPATH}}" python3 - <<'PY'
import odb
from pathlib import Path

candidate = Path("/home/kalishot/PDflow/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.odb")
if candidate.exists():
    db = odb.dbDatabase.create()
    odb.read_db(db, str(candidate))
    assert db.getChip().getBlock() is not None
print("NATIVE_OPENDB_BINDING_INSTALLED")
PY

printf 'Native OpenDB binding installed to %s\n' "${DEST}"
