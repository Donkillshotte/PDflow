#!/usr/bin/env bash
# Install a pinned KLayout package from the official download site.
# Override KLAYOUT_VERSION and provide KLAYOUT_SHA256 together when upgrading.
set -euo pipefail

KLAYOUT_VERSION="${KLAYOUT_VERSION:-0.30.11}"
UBUNTU_MAJOR="$(. /etc/os-release && echo "${VERSION_ID%%.*}")"
URL="https://www.klayout.org/downloads/Ubuntu-${UBUNTU_MAJOR}/klayout_${KLAYOUT_VERSION}-1_amd64.deb"
if [[ "${KLAYOUT_VERSION}" == "0.30.11" ]]; then
  case "${UBUNTU_MAJOR}" in
    22) EXPECTED_SHA256="dde7f49610ef63c7d8688532778c3e19da985960097b0eff775577365965e32f" ;;
    24) EXPECTED_SHA256="772eb2c597dc8ec054800841246fcbf6f3440581caee53663dc93afd135027b3" ;;
    *) echo "ERROR: unsupported Ubuntu major ${UBUNTU_MAJOR}" >&2; exit 1 ;;
  esac
else
  EXPECTED_SHA256="${KLAYOUT_SHA256:-}"
fi
if [[ -z "${EXPECTED_SHA256}" ]]; then
  echo "ERROR: provide KLAYOUT_SHA256 for KLayout ${KLAYOUT_VERSION}" >&2
  exit 1
fi

echo "==> Downloading KLayout ${KLAYOUT_VERSION} for Ubuntu ${UBUNTU_MAJOR}..."
curl -fsSL -o /tmp/klayout.deb "${URL}"
ACTUAL_SHA256="$(sha256sum /tmp/klayout.deb | awk '{print $1}')"
if [[ "${ACTUAL_SHA256}" != "${EXPECTED_SHA256}" ]]; then
  echo "ERROR: KLayout package integrity check failed" >&2
  rm -f /tmp/klayout.deb
  exit 1
fi
sudo apt-get install -y /tmp/klayout.deb
rm -f /tmp/klayout.deb

echo "==> Installed: $(klayout -v 2>&1 | head -1)"
