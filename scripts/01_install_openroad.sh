#!/usr/bin/env bash
# Installa OpenROAD dai binari precompilati di Precision Innovations (VaultLink).
# Supporta Ubuntu 22.04 e 24.04.
set -euo pipefail

API="https://vaultlink.precisioninno.com/api"
UBUNTU_VER="$(. /etc/os-release && echo "$VERSION_ID")"

echo "==> Cerco l'ultima release di OpenROAD per Ubuntu ${UBUNTU_VER}..."
LATEST_JSON="$(curl -fsSL "${API}/releases/latest")"
VERSION="$(echo "${LATEST_JSON}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')"
FILE="$(echo "${LATEST_JSON}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
names = [f['name'] for f in d['files'] if 'ubuntu-${UBUNTU_VER}' in f['name']]
print(names[0] if names else '')
")"

if [[ -z "${FILE}" ]]; then
  echo "ERRORE: nessun pacchetto per Ubuntu ${UBUNTU_VER} nella release ${VERSION}" >&2
  exit 1
fi

echo "==> Scarico ${FILE} (release ${VERSION})..."
curl -fsSL -o /tmp/openroad.deb "${API}/releases/${VERSION}/${FILE}/download"

echo "==> Installo il pacchetto..."
sudo apt-get update -qq
sudo apt-get install -y /tmp/openroad.deb
rm -f /tmp/openroad.deb

echo "==> Installato: openroad $(openroad -version)"
