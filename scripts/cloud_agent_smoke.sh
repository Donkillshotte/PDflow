#!/usr/bin/env bash
# Version-only smoke for Cloud Agent install. Does not run ORFS, DSE, AES, or IR.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAIL=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; FAIL=1; }

need_cmd() {
  local c="$1"
  if command -v "${c}" >/dev/null 2>&1; then
    ok "${c}: $(${c} -version 2>/dev/null | head -1 || ${c} -V 2>/dev/null | head -1 || echo present)"
  else
    bad "manca ${c}"
  fi
}

echo "== Cloud Agent core smoke (versions only) =="
need_cmd openroad
need_cmd yosys
need_cmd klayout

if command -v sta >/dev/null 2>&1; then
  ok "sta: $(sta -version 2>/dev/null | head -1)"
else
  echo "SKIP sta standalone (OpenROAD embeds STA; core profile does not build OpenSTA)"
fi

if [[ -d "${ROOT}/tools/OpenROAD-flow-scripts/flow" ]]; then
  ok "ORFS flow dir"
else
  bad "manca tools/OpenROAD-flow-scripts/flow"
fi

if [[ -d "${ROOT}/studio/node_modules" ]]; then
  ok "studio/node_modules"
else
  echo "SKIP studio/node_modules (SKIP_STUDIO=1?)"
fi

if [[ "${FAIL}" -ne 0 ]]; then
  echo "CLOUD_SMOKE_FAIL"
  exit 1
fi
echo "CLOUD_SMOKE_OK"
exit 0
