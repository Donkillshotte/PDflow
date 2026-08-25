#!/usr/bin/env bash
# Smoke test di OpenSTA: analisi timing min/max sull'esempio Nangate45
# incluso nei sorgenti di OpenSTA.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLES="${ROOT}/tools/src/OpenSTA/examples"

cd "${EXAMPLES}"
exec sta -no_init -exit min_max_delays.tcl
