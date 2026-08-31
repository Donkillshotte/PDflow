#!/usr/bin/env bash
# GCD FlowLab DSE with an 8 GiB address-space cap. Does not run AES.
# Resume by default (do not set DSE_FRESH). Krylov on GCD meshes is small;
# the cap still stops a runaway worker from recycling the Cloud Agent pod.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${DSE_FRESH:-0}" == "1" ]]; then
  echo "REFUSED: DSE_FRESH=1 would wipe GCD FlowLab memory. Resume only." >&2
  exit 2
fi
if [[ "${FLOW_VARIANT:-flowlab}" == *aes* ]] || [[ "${DESIGN_ID:-}" == *aes* ]]; then
  echo "REFUSED: this wrapper is GCD FlowLab only. AES uses run_aes_f4_cloud.sh." >&2
  exit 2
fi
export FLOW_VARIANT="${FLOW_VARIANT:-flowlab}"
export DSE_BUDGET_S="${DSE_BUDGET_S:-45}"
export DSE_F1_MAX="${DSE_F1_MAX:-6}"
export PDN_SOLVE_TIMEOUT_S="${PDN_SOLVE_TIMEOUT_S:-90}"
export PYTHONPATH="${ROOT}/learn:/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
AS_BYTES="${PDN_AS_BYTES:-8589934592}"
CPU_S="${PDN_CPU_S:-120}"
echo "GCD DSE cloud: variant=${FLOW_VARIANT} budget=${DSE_BUDGET_S}s as=${AS_BYTES}"
exec prlimit --as="${AS_BYTES}" --cpu="${CPU_S}" \
  bash "${ROOT}/learn/scripts/run_dse.sh"
