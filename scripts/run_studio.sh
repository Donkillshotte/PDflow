#!/usr/bin/env bash
# Start OpenROAD Physical Design Studio (web UI).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${ROOT}/scripts/native_eda_env.sh" ]]; then
  # The desktop launcher and its child agent share one native toolchain.
  source "${ROOT}/scripts/native_eda_env.sh"
fi
NODE="${PD_FLOW_NODE:-$(command -v node || true)}"
if [[ -z "${NODE}" || ! -x "${NODE}" ]]; then
  NODE="${ROOT}/studio/node-runtime/node"
fi
if [[ ! -x "${NODE}" ]]; then
  echo "PDflow Studio requires a native Node.js executable; set PD_FLOW_NODE" >&2
  exit 1
fi
cd "${ROOT}/studio"
PORT="${PORT:-43217}"
HOST="${HOST:-127.0.0.1}"
AGENT_PORT="$(printenv PD_FLOW_AGENT_PORT || true)"
AGENT_PID=""
TMP_DIR="$(printenv TMPDIR || true)"
if [[ -z "${AGENT_PORT}" ]]; then AGENT_PORT=43219; fi
if [[ -z "${TMP_DIR}" ]]; then TMP_DIR=/tmp; fi
AGENT_TOKEN="$(printenv PD_FLOW_AGENT_TOKEN || true)"
if [[ -z "${AGENT_TOKEN}" ]]; then
  AGENT_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
fi

cleanup_agent() {
  if [[ -n "${AGENT_PID}" ]] && kill -0 "${AGENT_PID}" 2>/dev/null; then
    kill -TERM "${AGENT_PID}" 2>/dev/null || true
    for _ in $(seq 1 50); do
      if ! kill -0 "${AGENT_PID}" 2>/dev/null; then
        break
      fi
      sleep 0.1
    done
    if kill -0 "${AGENT_PID}" 2>/dev/null; then
      kill -KILL "${AGENT_PID}" 2>/dev/null || true
    fi
    wait "${AGENT_PID}" 2>/dev/null || true
  fi
}
trap cleanup_agent EXIT INT TERM

if ! curl -fsS --max-time 1 "http://127.0.0.1:${AGENT_PORT}/health" >/dev/null 2>&1; then
  echo "==> starting PDflow local agent on ${AGENT_PORT}"
  (
    cd "${ROOT}"
    export PD_FLOW_AGENT_TOKEN="${AGENT_TOKEN}"
    PYTHONPATH="${ROOT}/learn" python3 -m pdflow_agent \
      --repo-root "${ROOT}" \
      --host 127.0.0.1 \
      --port "${AGENT_PORT}" \
      --poll-seconds "$(printenv PD_FLOW_AGENT_POLL_SECONDS || echo 1.0)"
  ) >"${TMP_DIR}/pdflow-agent-${AGENT_PORT}.log" 2>&1 &
  AGENT_PID="$!"
  for _ in $(seq 1 50); do
    if curl -fsS --max-time 1 "http://127.0.0.1:${AGENT_PORT}/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.1
  done
  if ! curl -fsS --max-time 1 "http://127.0.0.1:${AGENT_PORT}/health" >/dev/null 2>&1; then
    echo "PDflow local agent did not become ready" >&2
    exit 1
  fi
fi

if [[ ! -d node_modules ]]; then
  if [[ -f package-lock.json ]]; then
    echo "==> npm ci in studio/"
    PD_FLOW_RESOURCE_CWD="${ROOT}/studio" \
      "${ROOT}/scripts/run_resource_job.sh" studio-npm-ci npm ci
  else
    echo "==> npm install in studio/ (no lockfile present)"
    PD_FLOW_RESOURCE_CWD="${ROOT}/studio" \
      "${ROOT}/scripts/run_resource_job.sh" studio-npm-install npm install
  fi
fi

"${NODE}" scripts/prepare_monaco_assets.mjs

if [[ "${1:-}" == "--build" ]]; then
  PD_FLOW_RESOURCE_CWD="${ROOT}/studio" \
    "${ROOT}/scripts/run_resource_job.sh" studio-next-build \
    "${NODE}" node_modules/next/dist/bin/next build --webpack
  "${NODE}" node_modules/next/dist/bin/next start -H "${HOST}" -p "${PORT}"
else
  "${NODE}" node_modules/next/dist/bin/next dev --webpack -H "${HOST}" -p "${PORT}"
fi
