#!/usr/bin/env bash
# Single-command PDflow installer. Keep the implementation in scripts/ so it
# can also be called by packaging and automated verification.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec bash "${ROOT}/scripts/install_pdflow.sh" "$@"
