#!/usr/bin/env bash
# ORFS usa ancora l'opzione storica "-c" per indicare uno script yosys.
# Da yosys 0.68 l'opzione equivalente è "-s". Questo wrapper mantiene
# compatibili le revisioni correnti senza modificare il checkout di ORFS.
set -euo pipefail

YOSYS_REAL="${YOSYS_REAL:-$(command -v yosys)}"
args=()

for arg in "$@"; do
  if [[ "${arg}" == "-c" ]]; then
    args+=("-s")
  else
    args+=("${arg}")
  fi
done

exec "${YOSYS_REAL}" "${args[@]}"
