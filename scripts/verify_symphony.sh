#!/usr/bin/env bash
# Verify the local PDflow/Symphony contract without starting any service.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREVIEW_ACK_FLAG="--i-understand-that-this-will-be-running-without-the-usual-guardrails"
WORKFLOW="${PD_FLOW_SYMPHONY_WORKFLOW:-${ROOT}/WORKFLOW.md}"
CODEX_BIN="${PD_FLOW_CODEX_BIN:-$(command -v codex || true)}"
SYMPHONY_BIN="${PD_FLOW_SYMPHONY_BIN:-$(command -v symphony || true)}"
REQUIRE_RUNTIME=0
if [[ "${1:-}" == "--require-runtime" ]]; then
  REQUIRE_RUNTIME=1
  shift
fi
if [[ "$#" -gt 0 ]]; then
  echo "usage: $0 [--require-runtime]" >&2
  exit 2
fi

PYTHONPATH="${ROOT}/learn${PYTHONPATH:+:${PYTHONPATH}}" \
  python3 "${ROOT}/learn/scripts/validate_symphony_workflow.py" \
  --workflow "${WORKFLOW}"

if [[ ! -x "${CODEX_BIN}" ]] || ! "${CODEX_BIN}" app-server --help >/dev/null 2>&1; then
  echo "Codex app-server runtime: GAP" >&2
  exit 1
fi
echo "Codex app-server runtime: READY"

if [[ -x "${SYMPHONY_BIN}" ]]; then
  symphony_help="$("${SYMPHONY_BIN}" --help 2>&1 || true)"
  if [[ "${symphony_help}" == *"Usage: symphony"* ]]; then
    echo "Symphony executable: READY (${SYMPHONY_BIN})"
    preview_help="$("${SYMPHONY_BIN}" "${PREVIEW_ACK_FLAG}" --help 2>&1 || true)"
    if [[ "${preview_help}" == *"Usage: symphony"* ]]; then
      echo "Symphony preview acknowledgement: SUPPORTED (launcher requires explicit opt-in)"
    else
      echo "Symphony preview acknowledgement: UNKNOWN (launcher will refuse to start)" >&2
      if [[ "${REQUIRE_RUNTIME}" == "1" ]]; then
        exit 1
      fi
    fi
  elif [[ "${REQUIRE_RUNTIME}" == "1" ]]; then
    echo "Symphony executable: GAP (incompatible runtime)" >&2
    exit 1
  else
    echo "Symphony executable: GAP (incompatible runtime)"
  fi
elif [[ "${REQUIRE_RUNTIME}" == "1" ]]; then
  echo "Symphony executable: GAP (set PD_FLOW_SYMPHONY_BIN)" >&2
  exit 1
else
  echo "Symphony executable: GAP (contract-only verification; set PD_FLOW_SYMPHONY_BIN to run)"
fi

echo "PDflow/Symphony integration verification complete"
