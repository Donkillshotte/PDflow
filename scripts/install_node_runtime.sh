#!/usr/bin/env bash
# Install the pinned native Node.js runtime used by PDflow Studio.
#
# The runtime is user-owned and downloaded as a checksum-verified archive.  It
# is deliberately kept outside the repository so a clone stays source-only
# and so a desktop build can bundle the exact engine without using the host's
# package manager version.
set -Eeuo pipefail

DEFAULT_NODE_VERSION="20.19.5"
DEFAULT_NODE_SHA256="315046739a513a70e03a4a55a8afda8cf979f30852e576075c340084e3f8ac0f"

usage() {
  cat <<'EOF'
Usage: install_node_runtime.sh [options]

Install the checksum-verified native Node.js runtime required by PDflow.

Options:
  --check             verify the installed runtime without downloading
  --force             replace an incomplete or different target (kept aside)
  --version VERSION  install another version only with PD_FLOW_NODE_SHA256
  --prefix PATH       exact user-owned install directory
  --cache PATH        archive cache directory
  --print-path        print the installed node executable and exit
  --help              show this help

Environment:
  PD_FLOW_NODE_VERSION, PD_FLOW_NODE_SHA256, PD_FLOW_NODE_PREFIX,
  PD_FLOW_NODE_CACHE, PD_FLOW_NODE_URL
EOF
}

NODE_VERSION="${PD_FLOW_NODE_VERSION:-${DEFAULT_NODE_VERSION}}"
NODE_SHA256="${PD_FLOW_NODE_SHA256:-${DEFAULT_NODE_SHA256}}"
DATA_ROOT="${XDG_DATA_HOME:-${HOME:-/home/kalishot}/.local/share}"
CACHE_ROOT="${PD_FLOW_NODE_CACHE:-${XDG_CACHE_HOME:-${HOME:-/home/kalishot}/.cache}/pdflow}"
NODE_PREFIX="${PD_FLOW_NODE_PREFIX:-${DATA_ROOT}/pdflow/node-v${NODE_VERSION}-linux-x64}"
NODE_URL="${PD_FLOW_NODE_URL:-https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz}"
CHECK_ONLY=0
FORCE_INSTALL=0
PRINT_PATH=0

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --check)
      CHECK_ONLY=1
      shift
      ;;
    --force)
      FORCE_INSTALL=1
      shift
      ;;
    --version)
      [[ "$#" -ge 2 ]] || { usage >&2; exit 2; }
      NODE_VERSION="$2"
      shift 2
      ;;
    --prefix)
      [[ "$#" -ge 2 ]] || { usage >&2; exit 2; }
      NODE_PREFIX="$2"
      shift 2
      ;;
    --cache)
      [[ "$#" -ge 2 ]] || { usage >&2; exit 2; }
      CACHE_ROOT="$2"
      shift 2
      ;;
    --print-path)
      PRINT_PATH=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

NODE_BIN="${NODE_PREFIX}/bin/node"
if [[ "${NODE_VERSION}" != "${DEFAULT_NODE_VERSION}" && -z "${PD_FLOW_NODE_SHA256:-}" ]]; then
  echo "FAIL: a non-default Node version requires PD_FLOW_NODE_SHA256" >&2
  exit 2
fi
if [[ ! "${NODE_SHA256}" =~ ^[0-9a-fA-F]{64}$ ]]; then
  echo "FAIL: PD_FLOW_NODE_SHA256 must be a 64-character SHA-256 digest" >&2
  exit 2
fi

if [[ "${PRINT_PATH}" == "1" ]]; then
  if [[ -x "${NODE_BIN}" ]]; then
    printf '%s\n' "${NODE_BIN}"
    exit 0
  fi
  echo "Node runtime is not installed: ${NODE_BIN}" >&2
  exit 1
fi

verify_node() {
  [[ -x "${NODE_BIN}" ]] || return 1
  [[ "$(${NODE_BIN} --version 2>/dev/null)" == "v${NODE_VERSION}" ]] || return 1
}

if verify_node; then
  printf 'Node runtime READY: %s\n' "${NODE_BIN}"
  exit 0
fi
if [[ "${CHECK_ONLY}" == "1" ]]; then
  printf 'Node runtime GAP: %s\n' "${NODE_BIN}" >&2
  exit 1
fi

case "$(uname -m)" in
  x86_64|amd64) ;;
  *)
    echo "FAIL: the pinned PDflow desktop runtime currently supports Linux x86_64 only" >&2
    exit 1
    ;;
esac
command -v curl >/dev/null 2>&1 || { echo "FAIL: curl is required" >&2; exit 1; }
command -v tar >/dev/null 2>&1 || { echo "FAIL: tar is required" >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "FAIL: sha256sum is required" >&2; exit 1; }

mkdir -p "${CACHE_ROOT}" "$(dirname "${NODE_PREFIX}")"
ARCHIVE="${CACHE_ROOT}/node-v${NODE_VERSION}-linux-x64.tar.xz"
PARTIAL="${ARCHIVE}.part.$$"
STAGE_DIR="$(mktemp -d "$(dirname "${NODE_PREFIX}")/.pdflow-node.XXXXXX")"
cleanup() {
  rm -f "${PARTIAL}"
  rm -rf "${STAGE_DIR}"
}
trap cleanup EXIT

download_and_verify() {
  local source_file="$1"
  printf '%s  %s\n' "${NODE_SHA256}" "${source_file}" | sha256sum -c - >/dev/null
}

if [[ -f "${ARCHIVE}" ]]; then
  if download_and_verify "${ARCHIVE}"; then
    echo "Using verified Node archive: ${ARCHIVE}"
  else
    echo "Cached Node archive failed checksum; downloading a fresh copy" >&2
    rm -f "${ARCHIVE}"
  fi
fi
if [[ ! -f "${ARCHIVE}" ]]; then
  curl --fail --location --retry 3 --retry-delay 2 --proto '=https' --tlsv1.2 \
    --output "${PARTIAL}" "${NODE_URL}"
  download_and_verify "${PARTIAL}"
  mv "${PARTIAL}" "${ARCHIVE}"
fi

tar -xJf "${ARCHIVE}" -C "${STAGE_DIR}" --no-same-owner
EXTRACTED="${STAGE_DIR}/node-v${NODE_VERSION}-linux-x64"
[[ -x "${EXTRACTED}/bin/node" ]] || {
  echo "FAIL: Node archive did not contain the expected native executable" >&2
  exit 1
}
[[ "$(${EXTRACTED}/bin/node --version)" == "v${NODE_VERSION}" ]] || {
  echo "FAIL: extracted Node version does not match ${NODE_VERSION}" >&2
  exit 1
}

if [[ -e "${NODE_PREFIX}" ]]; then
  if [[ "${FORCE_INSTALL}" != "1" ]]; then
    echo "FAIL: target exists but is not a valid Node runtime: ${NODE_PREFIX}" >&2
    echo "Re-run with --force to keep it as a recoverable .stale directory." >&2
    exit 1
  fi
  STALE_PREFIX="${NODE_PREFIX}.stale-$(date +%Y%m%d%H%M%S)-$$"
  mv "${NODE_PREFIX}" "${STALE_PREFIX}"
  printf 'Moved previous Node target to %s\n' "${STALE_PREFIX}"
fi
mv "${EXTRACTED}" "${NODE_PREFIX}"
chmod 0755 "${NODE_BIN}"
printf 'Node runtime installed: %s\n' "${NODE_BIN}"
