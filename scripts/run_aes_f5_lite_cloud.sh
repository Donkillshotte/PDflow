#!/usr/bin/env bash
# AES F5-lite (2 DRT iters, ideal clock). No CTS. 6 GiB cap. Not Krylov.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" aes-f5-lite-cloud \
    bash "${BASH_SOURCE[0]}" "$@"
fi
source "${ROOT}/scripts/lib/heavy_analysis.sh"
require_heavy_analysis "AES F5-lite DRT+OpenRCX (not CTS)" || exit 2
if [[ "${AES_F5_ALLOW_CTS:-0}" == "1" ]]; then
  echo "REFUSED: AES F5-CTS is not part of this cloud shot." >&2
  exit 2
fi
export ALLOW_HEAVY_ANALYSIS=1
export AES_F5_TIMEOUT_S="${AES_F5_TIMEOUT_S:-1200}"
export OPENROAD_F5_LOG="${OPENROAD_F5_LOG:-/tmp/aes_f5_openroad.log}"
export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts:/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
AS_BYTES="${PDN_AS_BYTES:-6442450944}"
CPU_S="${PDN_CPU_S:-1500}"
echo "AES F5-lite cloud: timeout=${AES_F5_TIMEOUT_S}s as=${AS_BYTES} cpu=${CPU_S}s cts=off log=${OPENROAD_F5_LOG}"
exec prlimit --as="${AS_BYTES}" --cpu="${CPU_S}" \
  python3 -u "${ROOT}/learn/scripts/run_aes_f5_lite.py" "$@"
