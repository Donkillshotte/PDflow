#!/usr/bin/env bash
# OpenSTA smoke test: min/max timing on the bundled Nangate45 example
# included in the OpenSTA source tree.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" opensta-example bash "${BASH_SOURCE[0]}" "$@"
fi
EXAMPLES="${ROOT}/tools/src/OpenSTA/examples"

cd "${EXAMPLES}"
exec sta -no_init -exit min_max_delays.tcl
