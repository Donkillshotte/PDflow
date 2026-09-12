#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="$(printenv PD_FLOW_AGENT_PORT || true)"
POLL_SECONDS="$(printenv PD_FLOW_AGENT_POLL_SECONDS || true)"
HOST="$(printenv PD_FLOW_AGENT_HOST || true)"

if [[ -z "$PORT" ]]; then PORT=43219; fi
if [[ -z "$POLL_SECONDS" ]]; then POLL_SECONDS=1.0; fi
if [[ -z "$HOST" ]]; then HOST=127.0.0.1; fi
AGENT_TOKEN="$(printenv PD_FLOW_AGENT_TOKEN || true)"
if [[ -z "$AGENT_TOKEN" ]]; then
  AGENT_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
fi

cd "$ROOT"
if [[ -f "${ROOT}/scripts/native_eda_env.sh" ]]; then
  # Prefer the checked native host toolchain when it has been installed.
  source "${ROOT}/scripts/native_eda_env.sh"
fi
export PYTHONPATH="$ROOT/learn"
export PD_FLOW_AGENT_TOKEN="$AGENT_TOKEN"
exec python3 -m pdflow_agent \
  --repo-root "$ROOT" \
  --host "$HOST" \
  --port "$PORT" \
  --poll-seconds "$POLL_SECONDS"
