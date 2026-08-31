#!/usr/bin/env bash
# Refuse AES / large-mesh / Krylov work unless explicitly opted in.
# Prior Cloud Agent session expired after Krylov MOR on an AES 73k-R mesh.
require_heavy_analysis() {
  local reason="${1:-heavy PDN/AES/DSE analysis}"
  if [[ "${ALLOW_HEAVY_ANALYSIS:-}" != "1" ]]; then
    echo "REFUSED: ${reason}" >&2
    echo "Set ALLOW_HEAVY_ANALYSIS=1 to run this (not part of Cloud Agent setup)." >&2
    return 2
  fi
  return 0
}
