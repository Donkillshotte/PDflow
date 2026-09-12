#!/usr/bin/env bash
# Verify the local PDflow/Symphony contract without starting any service.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREVIEW_ACK_FLAG="--i-understand-that-this-will-be-running-without-the-usual-guardrails"
WORKFLOW="${PD_FLOW_SYMPHONY_WORKFLOW:-${ROOT}/WORKFLOW.md}"
CODEX_BIN="${PD_FLOW_CODEX_BIN:-$(command -v codex || true)}"
SYMPHONY_BIN="${PD_FLOW_SYMPHONY_BIN:-$(command -v symphony || true)}"
REQUIRE_RUNTIME=0
REQUIRE_LUNA_MAX=0
REQUIRE_GITHUB_AUTH=0
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --require-runtime)
      REQUIRE_RUNTIME=1
      shift
      ;;
    --require-luna-max)
      REQUIRE_LUNA_MAX=1
      shift
      ;;
    --require-github-auth)
      REQUIRE_GITHUB_AUTH=1
      shift
      ;;
    *)
      echo "usage: $0 [--require-runtime] [--require-luna-max] [--require-github-auth]" >&2
      exit 2
      ;;
  esac
done

PYTHONPATH="${ROOT}/learn${PYTHONPATH:+:${PYTHONPATH}}" \
  python3 "${ROOT}/learn/scripts/validate_symphony_workflow.py" \
  --workflow "${WORKFLOW}"

if [[ ! -x "${CODEX_BIN}" ]] || ! "${CODEX_BIN}" app-server --help >/dev/null 2>&1; then
  echo "Codex app-server runtime: GAP" >&2
  exit 1
fi
echo "Codex app-server runtime: READY"

if [[ "${REQUIRE_LUNA_MAX}" == "1" ]]; then
  CODEX_CONFIG="${PD_FLOW_CODEX_CONFIG:-${CODEX_HOME:-${HOME}/.codex}/config.toml}"
  read_codex_setting() {
    python3 - "${CODEX_CONFIG}" "$1" <<'PY'
import sys
import tomllib

path, key = sys.argv[1:]
try:
    with open(path, "rb") as handle:
        config = tomllib.load(handle)
except (OSError, tomllib.TOMLDecodeError):
    raise SystemExit(1)
value = config.get(key)
if not isinstance(value, str) or not value.strip():
    raise SystemExit(1)
print(value.strip())
PY
  }
  if ! CODEX_MODEL="$(read_codex_setting model 2>/dev/null)"; then
    echo "Codex model configuration: GAP (missing model in ${CODEX_CONFIG})" >&2
    exit 1
  fi
  if ! CODEX_REASONING="$(read_codex_setting model_reasoning_effort 2>/dev/null)"; then
    echo "Codex reasoning configuration: GAP (missing model_reasoning_effort in ${CODEX_CONFIG})" >&2
    exit 1
  fi
  if [[ "${CODEX_MODEL}" != "gpt-5.6-luna" || "${CODEX_REASONING}" != "max" ]]; then
    echo "Codex model configuration: GAP (expected gpt-5.6-luna with max reasoning; found ${CODEX_MODEL}/${CODEX_REASONING})" >&2
    exit 1
  fi
  echo "Codex model configuration: READY (gpt-5.6-luna / max)"
fi

if [[ "${REQUIRE_GITHUB_AUTH}" == "1" ]]; then
  if [[ -z "${GITHUB_TOKEN:-}" ]]; then
    echo "GitHub tracker authentication: GAP (GITHUB_TOKEN is not set)" >&2
    exit 1
  fi
  command -v curl >/dev/null 2>&1 || {
    echo "GitHub tracker authentication: GAP (curl is unavailable)" >&2
    exit 1
  }
  GITHUB_API_URL="${PD_FLOW_SYMPHONY_API_URL:-https://api.github.com}"
  case "${GITHUB_API_URL}" in
    https://*) ;;
    *)
      echo "GitHub tracker authentication: GAP (API URL must use HTTPS)" >&2
      exit 1
      ;;
  esac
  github_request() {
    local endpoint="$1"
    local response
    if ! response="$(printf 'Authorization: Bearer %s\nAccept: application/vnd.github+json\nX-GitHub-Api-Version: 2022-11-28\n' "${GITHUB_TOKEN}" | \
      curl --silent --show-error --connect-timeout 5 --max-time 15 \
        --proto '=https' --tlsv1.2 --header @- \
        --output /dev/null --write-out '%{http_code}' \
        "${GITHUB_API_URL}${endpoint}" 2>/dev/null)"; then
      return 1
    fi
    [[ "${response}" == "200" ]]
  }
  if ! github_request "/user"; then
    echo "GitHub tracker authentication: GAP (token rejected or API unreachable)" >&2
    exit 1
  fi
  if ! github_request "/repos/Donkillshotte/PDflow"; then
    echo "GitHub tracker repository access: GAP (cannot read Donkillshotte/PDflow)" >&2
    exit 1
  fi
  echo "GitHub tracker authentication: READY (user and repository readable)"
fi

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
