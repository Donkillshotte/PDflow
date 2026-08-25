#!/usr/bin/env bash
# Installa KLayout dal deb ufficiale (necessario a ORFS per generare il GDS finale).
set -euo pipefail

KLAYOUT_VERSION="${KLAYOUT_VERSION:-0.30.11}"
UBUNTU_MAJOR="$(. /etc/os-release && echo "${VERSION_ID%%.*}")"
URL="https://www.klayout.org/downloads/Ubuntu-${UBUNTU_MAJOR}/klayout_${KLAYOUT_VERSION}-1_amd64.deb"

echo "==> Scarico KLayout ${KLAYOUT_VERSION} per Ubuntu ${UBUNTU_MAJOR}..."
curl -fsSL -o /tmp/klayout.deb "${URL}"
sudo apt-get install -y /tmp/klayout.deb
rm -f /tmp/klayout.deb

echo "==> Installato: $(klayout -v 2>&1 | head -1)"
