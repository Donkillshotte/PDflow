#!/usr/bin/env bash
# Install KLayout from the official deb (required by ORFS to generate the final GDS).
set -euo pipefail

KLAYOUT_VERSION="${KLAYOUT_VERSION:-0.30.11}"
UBUNTU_MAJOR="$(. /etc/os-release && echo "${VERSION_ID%%.*}")"
URL="https://www.klayout.org/downloads/Ubuntu-${UBUNTU_MAJOR}/klayout_${KLAYOUT_VERSION}-1_amd64.deb"

echo "==> Downloading KLayout ${KLAYOUT_VERSION} for Ubuntu ${UBUNTU_MAJOR}..."
curl -fsSL -o /tmp/klayout.deb "${URL}"
sudo apt-get install -y /tmp/klayout.deb
rm -f /tmp/klayout.deb

echo "==> Installed: $(klayout -v 2>&1 | head -1)"
