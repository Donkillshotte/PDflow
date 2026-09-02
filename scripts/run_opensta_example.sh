#!/usr/bin/env bash
# OpenSTA smoke test: min/max timing on the bundled Nangate45 example
# included in the OpenSTA source tree.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLES="${ROOT}/tools/src/OpenSTA/examples"

cd "${EXAMPLES}"
exec sta -no_init -exit min_max_delays.tcl
