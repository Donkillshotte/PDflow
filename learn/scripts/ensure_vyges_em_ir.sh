#!/usr/bin/env bash
# Locate or install the Apache-2.0 vyges-em-ir binary (v0.1.33).
# Prints the absolute path to stdout. tools/ is gitignored — this is the
# reproducible fetch (sha256-pinned GitHub release, cargo fallback).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="${VYGES_EM_IR_VERSION:-0.1.33}"
DEST="${ROOT}/tools/vyges-em-ir"
BIN="${DEST}/vyges-em-ir"

if [[ -n "${VYGES_EM_IR:-}" && -x "${VYGES_EM_IR}" ]]; then
  echo "${VYGES_EM_IR}"
  exit 0
fi
if command -v vyges-em-ir >/dev/null 2>&1; then
  command -v vyges-em-ir
  exit 0
fi
if [[ -x "${BIN}" ]]; then
  echo "${BIN}"
  exit 0
fi

arch="$(uname -m)"
case "${arch}" in
  x86_64|amd64) triple="x86_64-unknown-linux-gnu"
    sha="1075ca8cf63a04949c87f76a91d764e7aa60be097972161c48d357b82030ac40" ;;
  aarch64|arm64) triple="aarch64-unknown-linux-gnu"
    sha="ab883c85885baeceab71f55f717c1ace4d33df1f3adc6c9c4dda58f4b44201a4" ;;
  *)
    echo "FAIL arch ${arch} — no vyges-em-ir release tarball" >&2
    exit 1
    ;;
esac

url="https://github.com/vyges-tools/em-ir/releases/download/v${VERSION}/vyges-em-ir-${triple}.tar.gz"
mkdir -p "${DEST}" /tmp/vyges-em-ir-dl
tgz="/tmp/vyges-em-ir-dl/vyges-em-ir-${VERSION}-${triple}.tar.gz"
echo "fetch ${url}" >&2
if curl -fsSL -o "${tgz}" "${url}"; then
  echo "${sha}  ${tgz}" | sha256sum -c - >&2
  tar -xzf "${tgz}" -C /tmp/vyges-em-ir-dl
  found="$(find /tmp/vyges-em-ir-dl -type f -name vyges-em-ir | head -1)"
  [[ -n "${found}" ]] || { echo "FAIL tarball without binary" >&2; exit 1; }
  install -m 755 "${found}" "${BIN}"
  echo "${BIN}"
  exit 0
fi

echo "WARN download failed — trying cargo build" >&2
if ! command -v cargo >/dev/null 2>&1; then
  echo "FAIL cannot install vyges-em-ir (no tarball, no cargo)" >&2
  exit 1
fi
src="${DEST}/src"
rm -rf "${src}"
git clone --depth 1 --branch "v${VERSION}" https://github.com/vyges-tools/em-ir.git "${src}" >&2
(cd "${src}" && cargo build --release >&2)
install -m 755 "${src}/target/release/vyges-em-ir" "${BIN}"
echo "${BIN}"
