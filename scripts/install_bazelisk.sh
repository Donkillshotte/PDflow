#!/usr/bin/env bash
# Install a pinned native Bazelisk binary for OpenROAD builds.
set -Eeuo pipefail

DEFAULT_BAZELISK_VERSION="1.29.0"
DEFAULT_BAZELISK_SHA256="5a408715e932c0250d28bd84555f12edbf70117de42f9181691c736eacc4a992"

usage() {
  cat <<'EOF'
Usage: install_bazelisk.sh [options]

Install checksum-verified Bazelisk into a user-owned PDflow EDA prefix.

Options:
  --check             verify the installed binary without downloading
  --force             replace an existing binary (kept as .stale)
  --path PATH         exact destination executable
  --cache PATH        binary cache directory
  --help              show this help

Environment:
  PD_FLOW_BAZELISK_VERSION, PD_FLOW_BAZELISK_SHA256,
  PD_FLOW_BAZELISK_PATH, PD_FLOW_BAZELISK_CACHE, PD_FLOW_BAZELISK_URL
EOF
}

VERSION="${PD_FLOW_BAZELISK_VERSION:-${DEFAULT_BAZELISK_VERSION}}"
SHA256="${PD_FLOW_BAZELISK_SHA256:-${DEFAULT_BAZELISK_SHA256}}"
PREFIX="${PD_FLOW_EDA_PREFIX:-${HOME:-/home/kalishot}/.local/pdflow-eda}"
DEST="${PD_FLOW_BAZELISK_PATH:-${PREFIX}/bin/bazelisk}"
CACHE_ROOT="${PD_FLOW_BAZELISK_CACHE:-${XDG_CACHE_HOME:-${HOME:-/home/kalishot}/.cache}/pdflow}"
URL="${PD_FLOW_BAZELISK_URL:-https://github.com/bazelbuild/bazelisk/releases/download/v${VERSION}/bazelisk-linux-amd64}"
CHECK_ONLY=0
FORCE_INSTALL=0

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
    --path)
      [[ "$#" -ge 2 ]] || { usage >&2; exit 2; }
      DEST="$2"
      shift 2
      ;;
    --cache)
      [[ "$#" -ge 2 ]] || { usage >&2; exit 2; }
      CACHE_ROOT="$2"
      shift 2
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

if [[ "${VERSION}" != "${DEFAULT_BAZELISK_VERSION}" && -z "${PD_FLOW_BAZELISK_SHA256:-}" ]]; then
  echo "FAIL: a non-default Bazelisk version requires PD_FLOW_BAZELISK_SHA256" >&2
  exit 2
fi
[[ "${SHA256}" =~ ^[0-9a-fA-F]{64}$ ]] || {
  echo "FAIL: Bazelisk SHA-256 must be a 64-character digest" >&2
  exit 2
}

verify_bazelisk() {
  [[ -x "${DEST}" ]] || return 1
  printf '%s  %s\n' "${SHA256}" "${DEST}" | sha256sum -c - >/dev/null 2>&1 || return 1
  "${DEST}" --version >/dev/null 2>&1 || return 1
}

if verify_bazelisk; then
  printf 'Bazelisk READY: %s\n' "${DEST}"
  exit 0
fi
if [[ "${CHECK_ONLY}" == "1" ]]; then
  printf 'Bazelisk GAP: %s\n' "${DEST}" >&2
  exit 1
fi

case "$(uname -m)" in
  x86_64|amd64) ;;
  *)
    echo "FAIL: the pinned OpenROAD build helper currently supports Linux x86_64 only" >&2
    exit 1
    ;;
esac
command -v curl >/dev/null 2>&1 || { echo "FAIL: curl is required" >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "FAIL: sha256sum is required" >&2; exit 1; }

mkdir -p "${CACHE_ROOT}" "$(dirname "${DEST}")"
ARCHIVE="${CACHE_ROOT}/bazelisk-${VERSION}-linux-amd64"
PARTIAL="${ARCHIVE}.part.$$"
cleanup() { rm -f "${PARTIAL}"; }
trap cleanup EXIT
verify_archive() {
  printf '%s  %s\n' "${SHA256}" "$1" | sha256sum -c - >/dev/null
}

if [[ -f "${ARCHIVE}" ]]; then
  if verify_archive "${ARCHIVE}"; then
    echo "Using verified Bazelisk archive: ${ARCHIVE}"
  else
    echo "Cached Bazelisk archive failed checksum; downloading a fresh copy" >&2
    rm -f "${ARCHIVE}"
  fi
fi
if [[ ! -f "${ARCHIVE}" ]]; then
  curl --fail --location --retry 3 --retry-delay 2 --proto '=https' --tlsv1.2 \
    --output "${PARTIAL}" "${URL}"
  verify_archive "${PARTIAL}"
  mv "${PARTIAL}" "${ARCHIVE}"
fi

if [[ -e "${DEST}" ]]; then
  if [[ "${FORCE_INSTALL}" != "1" ]]; then
    echo "FAIL: destination exists but is not a working Bazelisk: ${DEST}" >&2
    echo "Re-run with --force to keep it as a recoverable .stale file." >&2
    exit 1
  fi
  STALE_DEST="${DEST}.stale-$(date +%Y%m%d%H%M%S)-$$"
  mv "${DEST}" "${STALE_DEST}"
  printf 'Moved previous Bazelisk to %s\n' "${STALE_DEST}"
fi
install -m 0755 "${ARCHIVE}" "${DEST}"
verify_bazelisk || { echo "FAIL: installed Bazelisk cannot execute" >&2; exit 1; }
printf 'Bazelisk installed: %s\n' "${DEST}"
