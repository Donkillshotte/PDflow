#!/usr/bin/env bash
# Start the optional Symphony control plane for PDflow coding tasks.
#
# Symphony is deliberately kept outside PDflow's heavy-job executor: it is a
# lightweight coordinator. Agent workspaces must still use PDflow's guarded
# executor for builds, native EDA, and long tests.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREVIEW_ACK_FLAG="--i-understand-that-this-will-be-running-without-the-usual-guardrails"

# The currently installed native runtime is an engineering preview. Do not
# silently opt an operator into its preview mode: require a deliberate wrapper
# flag (or an explicit, host-local environment setting) and translate it to
# the runtime's long acknowledgement flag below.
ACK_PREVIEW=0
case "${PD_FLOW_SYMPHONY_ACK_PREVIEW:-0}" in
  1|true|TRUE|yes|YES)
    ACK_PREVIEW=1
    ;;
  0|false|FALSE|no|NO|'')
    ;;
  *)
    echo "PD_FLOW_SYMPHONY_ACK_PREVIEW must be 0/1 (or true/false)" >&2
    exit 2
    ;;
esac

# Consume the PDflow-friendly acknowledgement flag and the raw runtime flag
# if an operator supplied it explicitly. Other arguments are forwarded as an
# argv array; no shell command string is ever constructed.
FORWARD_ARGS=()
for arg in "$@"; do
  case "${arg}" in
    --ack-preview|"${PREVIEW_ACK_FLAG}")
      ACK_PREVIEW=1
      ;;
    *)
      FORWARD_ARGS+=("${arg}")
      ;;
  esac
done

WORKFLOW="${PD_FLOW_SYMPHONY_WORKFLOW:-${ROOT}/WORKFLOW.md}"
STATE_PARENT="${XDG_STATE_HOME:-${HOME}/.local/state}"
STATE_ROOT="${PD_FLOW_SYMPHONY_STATE_ROOT:-${STATE_PARENT}/pdflow/symphony}"
WORKSPACE_ROOT="${PD_FLOW_SYMPHONY_WORKSPACE_ROOT:-${STATE_ROOT}/workspaces}"
LOG_ROOT="${PD_FLOW_SYMPHONY_LOG_ROOT:-${STATE_ROOT}/logs}"
CODEX_BIN="${PD_FLOW_CODEX_BIN:-$(command -v codex || true)}"
SYMPHONY_BIN="${PD_FLOW_SYMPHONY_BIN:-$(command -v symphony || true)}"
REPO_ROOT="${PD_FLOW_REPO_ROOT:-${ROOT}}"

if ! REPO_ROOT="$(cd "${REPO_ROOT}" 2>/dev/null && pwd -P)"; then
  echo "PD_FLOW_REPO_ROOT is not an accessible directory: ${PD_FLOW_REPO_ROOT:-${ROOT}}" >&2
  exit 2
fi

if [[ ! -f "${WORKFLOW}" ]]; then
  echo "PDflow Symphony workflow is missing: ${WORKFLOW}" >&2
  exit 2
fi
if [[ ! -x "${SYMPHONY_BIN}" ]]; then
  echo "PDflow Symphony executable is missing or not executable: ${SYMPHONY_BIN:-<unset>}" >&2
  echo "Set PD_FLOW_SYMPHONY_BIN to the native Symphony executable." >&2
  exit 2
fi
SYMPHONY_HELP="$("${SYMPHONY_BIN}" --help 2>&1 || true)"
if [[ "${SYMPHONY_HELP}" != *"Usage: symphony"* ]]; then
  echo "The configured executable is not a compatible Symphony runtime." >&2
  exit 2
fi
if [[ ! -x "${CODEX_BIN}" ]]; then
  echo "PDflow requires a native Codex executable for Symphony: ${CODEX_BIN:-<unset>}" >&2
  exit 2
fi
if ! "${CODEX_BIN}" app-server --help >/dev/null 2>&1; then
  echo "The configured Codex executable does not expose app-server mode." >&2
  exit 2
fi
if ! command -v git >/dev/null 2>&1; then
  echo "PDflow Symphony requires native git." >&2
  exit 2
fi
if ! git -C "${REPO_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "PD_FLOW_REPO_ROOT must point to a Git checkout: ${REPO_ROOT}" >&2
  exit 2
fi

# Keep the acknowledgement check after all read-only preflight checks so a
# missing workflow, binary, Codex runtime, or Git checkout is reported as the
# real configuration error. This still happens before mkdir/export/exec.
if [[ "${ACK_PREVIEW}" != "1" ]]; then
  echo "The configured Symphony runtime is an engineering preview and requires explicit acknowledgement." >&2
  echo "No Symphony process was started." >&2
  echo "Re-run with: $0 --ack-preview [optional Symphony arguments]" >&2
  echo "Alternatively set PD_FLOW_SYMPHONY_ACK_PREVIEW=1 in the host shell." >&2
  exit 2
fi

mkdir -p "${STATE_ROOT}" "${WORKSPACE_ROOT}" "${LOG_ROOT}"
chmod 700 "${STATE_ROOT}" "${WORKSPACE_ROOT}" "${LOG_ROOT}" 2>/dev/null || true
STATE_ROOT="$(cd "${STATE_ROOT}" && pwd -P)"
WORKSPACE_ROOT="$(cd "${WORKSPACE_ROOT}" && pwd -P)"
LOG_ROOT="$(cd "${LOG_ROOT}" && pwd -P)"

# The after_create hook uses these explicit, non-secret paths to make a local
# copy of the canonical checkout. A dirty main checkout is not copied; agents
# always start from its committed HEAD in a separate workspace.
export PD_FLOW_REPO_ROOT="${REPO_ROOT}"
export PD_FLOW_SYMPHONY_WORKSPACE_ROOT="${WORKSPACE_ROOT}"
export PD_FLOW_SYMPHONY_STATE_ROOT="${STATE_ROOT}"
export PD_FLOW_SYMPHONY_LOG_ROOT="${LOG_ROOT}"
export PD_FLOW_SYMPHONY_ACTIVE=1
# WORKFLOW.md deliberately names the stable `codex` command. When an operator
# selects a different native binary, expose only its containing directory so
# the app-server child resolves the same executable that was preflighted.
CODEX_DIR="$(dirname "${CODEX_BIN}")"
export PATH="${CODEX_DIR}:${PATH}"

SYMPHONY_ARGS=("${PREVIEW_ACK_FLAG}" "${WORKFLOW}" "--logs-root" "${LOG_ROOT}")
if [[ -n "${PD_FLOW_SYMPHONY_PORT:-}" ]]; then
  if [[ ! "${PD_FLOW_SYMPHONY_PORT}" =~ ^[0-9]+$ ]] || (( PD_FLOW_SYMPHONY_PORT < 1 || PD_FLOW_SYMPHONY_PORT > 65535 )); then
    echo "PD_FLOW_SYMPHONY_PORT must be an integer from 1 to 65535" >&2
    exit 2
  fi
  SYMPHONY_ARGS+=("--port" "${PD_FLOW_SYMPHONY_PORT}")
fi
if [[ "${#FORWARD_ARGS[@]}" -gt 0 ]]; then
  SYMPHONY_ARGS+=("${FORWARD_ARGS[@]}")
fi

echo "PDflow Symphony: workspace root ${WORKSPACE_ROOT}" >&2
echo "PDflow Symphony: workflow ${WORKFLOW}" >&2
exec "${SYMPHONY_BIN}" "${SYMPHONY_ARGS[@]}"
