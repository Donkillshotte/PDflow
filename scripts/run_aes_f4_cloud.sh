#!/usr/bin/env bash
# AES F4 on a Cloud Agent VM: DirectLU, raised timeout, 8 GiB address-space cap.
# Uncapped solve_f4 recycled this 15 GiB pod. Krylov is refused by RSS budget.
# Does not run during Cloud Agent install.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT}/scripts/lib/heavy_analysis.sh"
require_heavy_analysis "AES F4 on Cloud Agent (DirectLU, not Krylov)" || exit 2

export ALLOW_HEAVY_ANALYSIS=1
export PDN_SOLVE_TIMEOUT_S="${PDN_SOLVE_TIMEOUT_S:-90}"
export PYTHONPATH="${ROOT}/learn:${ROOT}/learn/scripts:/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
AS_BYTES="${PDN_AS_BYTES:-8589934592}" # 8 GiB
CPU_S="${PDN_CPU_S:-120}"

echo "AES F4 cloud: PDN_SOLVE_TIMEOUT_S=${PDN_SOLVE_TIMEOUT_S} as=${AS_BYTES} cpu=${CPU_S}s"
exec prlimit --as="${AS_BYTES}" --cpu="${CPU_S}" \
  python3 -u "${ROOT}/learn/scripts/run_aes_f4.py" "$@"
