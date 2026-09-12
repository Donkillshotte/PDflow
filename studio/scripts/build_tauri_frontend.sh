#!/usr/bin/env bash
# Build the standalone Next server and the tiny Tauri bootstrap page.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE="${PD_FLOW_NODE:-$(command -v node || true)}"
if [[ -z "${NODE}" || ! -x "${NODE}" ]]; then
  NODE="${ROOT}/node-runtime/node"
fi
if [[ -z "${NODE}" || ! -x "${NODE}" ]]; then
  echo "FAIL: set PD_FLOW_NODE or put a native Node.js executable on PATH" >&2
  exit 1
fi

# A direct cargo tauri build must use the same guarded slot as npm builds.
# When cargo is already running inside the slot, continue in that cgroup so
# the complete desktop package remains one serialized workload.
if [[ "${PD_FLOW_RESOURCE_ACTIVE:-0}" != "1" ]]; then
  exec "${ROOT}/../scripts/run_resource_job.sh" \
    studio-tauri-frontend bash "${BASH_SOURCE[0]}" "$@"
fi

cd "${ROOT}"
"${NODE}" scripts/prepare_monaco_assets.mjs
# The webpack worker is a native Node child and can otherwise reserve most of
# the six-GiB PDflow cgroup before MemoryHigh has a chance to reclaim it. Keep
# the JS heap comfortably below the shared five-GiB high watermark; native
# buffers and the Tauri compiler still have room inside MemoryMax. An operator
# may choose a larger heap explicitly, but only with the same resource
# increase acknowledgement used by the shared runner.
NEXT_HEAP_MB="${PD_FLOW_NEXT_HEAP_MB:-3072}"
if [[ ! "${NEXT_HEAP_MB}" =~ ^[0-9]+$ ]] || (( NEXT_HEAP_MB < 2048 || NEXT_HEAP_MB > 5120 )); then
  echo "FAIL: PD_FLOW_NEXT_HEAP_MB must be between 2048 and 5120" >&2
  exit 2
fi
if (( NEXT_HEAP_MB > 3072 )) && [[ "${PD_FLOW_RESOURCE_ALLOW_INCREASE:-0}" != "1" ]]; then
  echo "FAIL: PD_FLOW_NEXT_HEAP_MB above 3072 requires PD_FLOW_RESOURCE_ALLOW_INCREASE=1" >&2
  exit 2
fi
case " ${NODE_OPTIONS:-} " in
  *" --max-old-space-size="*) ;;
  *) export NODE_OPTIONS="${NODE_OPTIONS:+${NODE_OPTIONS} }--max-old-space-size=${NEXT_HEAP_MB}" ;;
esac
echo "TAURI_NEXT_HEAP_MB=${NEXT_HEAP_MB}"
# Next's webpack cache is an incremental artifact and must never influence a
# release bundle.  Move only this generated cache aside so stale WebAssembly
# hash records cannot affect a repeated package build and recovery remains
# possible while the build is running. Keep the recovery archive on the
# persistent filesystem rather than consuming the small /tmp tmpfs.
STALE_ROOT="${PD_FLOW_STALE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/pdflow-stale}"
BUILD_STALE_DIR="${STALE_ROOT}/build-$(date +%Y%m%d)-${PPID}-$$"
mkdir -p "${BUILD_STALE_DIR}"
if [[ -d "${ROOT}/.next/cache" ]]; then
  mv "${ROOT}/.next/cache" "${BUILD_STALE_DIR}/next-cache"
fi
# linuxdeploy can reuse an old AppDir between packaging attempts.  Remove the
# exact generated release AppDir (by moving it aside) so deleted optional
# native modules cannot leak back into a subsequent AppImage.
if [[ -d "${ROOT}/src-tauri/target/release/bundle/appimage/PDflow.AppDir" ]]; then
  mv "${ROOT}/src-tauri/target/release/bundle/appimage/PDflow.AppDir" "${BUILD_STALE_DIR}/PDflow.AppDir"
fi
for stale_path in \
  "${ROOT}/src-tauri/target/release/next-standalone" \
  "${ROOT}/src-tauri/target/release/bundle/appimage_deb"; do
  if [[ -e "${stale_path}" ]]; then
    stale_name="$(basename "${stale_path}")"
    mv "${stale_path}" "${BUILD_STALE_DIR}/${stale_name}"
  fi
done
PD_FLOW_DESKTOP_BUILD=1 "${NODE}" node_modules/next/dist/bin/next build --webpack

STANDALONE="${ROOT}/.next/standalone"
[[ -f "${STANDALONE}/server.js" ]] || {
  echo "FAIL: Next standalone server was not generated" >&2
  exit 1
}
mkdir -p "${STANDALONE}/.next" "${STANDALONE}/public" "${ROOT}/out" "${ROOT}/node-runtime"
if [[ -d "${ROOT}/.next/static" ]]; then
  if [[ -d "${STANDALONE}/.next/static" ]]; then
    mv "${STANDALONE}/.next/static" "${BUILD_STALE_DIR}/standalone-static"
  fi
  cp -a "${ROOT}/.next/static" "${STANDALONE}/.next/static"
fi
if [[ -d "${ROOT}/public" ]]; then
  PUBLIC_STALE_DIR="${BUILD_STALE_DIR}/standalone-public"
  mkdir -p "${PUBLIC_STALE_DIR}"
  find "${STANDALONE}/public" -mindepth 1 -maxdepth 1 -exec mv -t "${PUBLIC_STALE_DIR}" -- {} +
  cp -a "${ROOT}/public/." "${STANDALONE}/public/"
fi
# Next's standalone trace can include the optional musl sharp package even
# when the target is glibc Linux. Leaving that binary in the AppImage makes
# linuxdeploy require libc.musl-x86_64.so.1 and breaks a native host bundle.
# The glibc sharp package remains available for image operations.
MUSL_STALE_DIR="${BUILD_STALE_DIR}/standalone-musl-modules"
while IFS= read -r -d '' stale_module; do
  relative_module="${stale_module#${STANDALONE}/node_modules/}"
  target_module="${MUSL_STALE_DIR}/${relative_module}"
  mkdir -p "$(dirname "${target_module}")"
  mv "${stale_module}" "${target_module}"
done < <(find "${STANDALONE}/node_modules" -type d \
  \( -path '*/@img/sharp-linuxmusl-x64' -o -path '*/@img/sharp-libvips-linuxmusl-x64' \) \
  -prune -print0 2>/dev/null)
cp "${ROOT}/desktop/index.html" "${ROOT}/out/index.html"
NODE_TARGET="${ROOT}/node-runtime/node"
if [[ "$(readlink -f "${NODE}")" == "$(readlink -f "${NODE_TARGET}" 2>/dev/null || true)" ]]; then
  chmod 0755 "${NODE_TARGET}"
else
  install -m 0755 "${NODE}" "${NODE_TARGET}"
fi
echo "TAURI_FRONTEND_READY standalone=${STANDALONE} node=${ROOT}/node-runtime/node"
