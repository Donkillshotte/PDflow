#!/usr/bin/env bash
# Install OpenROAD from a pinned Precision Innovations binary (VaultLink).
# Supports Ubuntu 22.04 and 24.04. Override OPENROAD_VERSION and provide
# OPENROAD_SHA256 together when deliberately moving to another release.
set -euo pipefail

API="https://vaultlink.precisioninno.com/api"
UBUNTU_VER="$(. /etc/os-release && echo "$VERSION_ID")"
PINNED_VERSION="26Q2-1164-g08f67ee5ec"
OPENROAD_VERSION="${OPENROAD_VERSION:-${PINNED_VERSION}}"

case "${UBUNTU_VER}" in
  22.04|24.04) ;;
  *)
    echo "ERROR: unsupported Ubuntu ${UBUNTU_VER} (expected 22.04 or 24.04)" >&2
    exit 1
    ;;
esac

echo "==> Resolving OpenROAD ${OPENROAD_VERSION} for Ubuntu ${UBUNTU_VER}..."
EXPECTED_MD5_B64=""
EXPECTED_SIZE=""
if [[ "${OPENROAD_VERSION}" == "${PINNED_VERSION}" ]]; then
  VERSION="${PINNED_VERSION}"
  FILE="openroad_${PINNED_VERSION}_amd64-ubuntu-${UBUNTU_VER}.deb"
  case "${UBUNTU_VER}" in
    22.04)
      DEFAULT_SHA256="1fe0e084dfc67a807f31a67a8f941e8d6dc4c3242cae0bdb0a67e1dae6f1c4a6"
      EXPECTED_MD5_B64="LcpJMXdUg+sN6NvP0vu82A=="
      EXPECTED_SIZE="64047394"
      ;;
    24.04)
      DEFAULT_SHA256="f3f1eeaa18f327503f72cc45dcef5b1514ec2e89726ec53b4553bf4f951168a3"
      EXPECTED_MD5_B64="+1hKUJeH+uFmJ24UjnUk3g=="
      EXPECTED_SIZE="63800256"
      ;;
  esac
else
  VERSION="${OPENROAD_VERSION}"
  FILE="${OPENROAD_FILE:-openroad_${OPENROAD_VERSION}_amd64-ubuntu-${UBUNTU_VER}.deb}"
  echo "WARNING: using an unpinned OpenROAD release; vendor metadata is unavailable." >&2
fi
EXPECTED_SHA256="${OPENROAD_SHA256:-${DEFAULT_SHA256:-}}"
if [[ -z "${EXPECTED_SHA256}" ]]; then
  echo "ERROR: provide OPENROAD_SHA256 for an unpinned OpenROAD release" >&2
  exit 1
fi

echo "==> Downloading ${FILE} (release ${VERSION})..."
curl -fsSL -o /tmp/openroad.deb "${API}/releases/${VERSION}/${FILE}/download"

ACTUAL_SIZE="$(stat -c '%s' /tmp/openroad.deb)"
ACTUAL_SHA256="$(sha256sum /tmp/openroad.deb | awk '{print $1}')"
ACTUAL_MD5_B64="$(openssl dgst -md5 -binary /tmp/openroad.deb | base64 -w0)"
if [[ "${ACTUAL_SHA256}" != "${EXPECTED_SHA256}" ||
      ( -n "${EXPECTED_SIZE}" && "${ACTUAL_SIZE}" != "${EXPECTED_SIZE}" ) ||
      ( -n "${EXPECTED_MD5_B64}" && "${ACTUAL_MD5_B64}" != "${EXPECTED_MD5_B64}" ) ]]; then
  echo "ERROR: OpenROAD package integrity check failed" >&2
  rm -f /tmp/openroad.deb
  exit 1
fi

echo "==> Installing package..."
sudo apt-get update -qq
sudo apt-get install -y /tmp/openroad.deb
rm -f /tmp/openroad.deb

echo "==> Installed: openroad $(openroad -version)"
