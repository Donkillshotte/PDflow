#!/usr/bin/env bash
# Prepare a user-owned native Linux build sysroot for PDflow Desktop.
#
# This is deliberately not a package installer: it uses the distribution's
# existing apt indexes, downloads Debian packages into a cache, and extracts
# them below a user-owned prefix with dpkg-deb. It never invokes sudo, changes
# the system package database, starts a container, or modifies the repository.
set -Eeuo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: bootstrap_native_build_sysroot.sh [options]

Options:
  --prefix PATH   extraction prefix (default: ~/.local/pdflow-build-sysroot)
  --cache PATH    .deb cache (default: ~/.cache/pdflow-apt/YYYYMMDD)
  --help          show this message

The script targets the certified amd64 Debian/Kali native desktop build. It
does not run apt-get update; refresh package indexes separately if required.
EOF
}

SYSROOT="${PD_FLOW_BUILD_SYSROOT:-${HOME:-/home/kalishot}/.local/pdflow-build-sysroot}"
CACHE_ROOT="${PD_FLOW_BUILD_SYSROOT_CACHE:-${XDG_CACHE_HOME:-${HOME:-/home/kalishot}/.cache}/pdflow-apt/$(date +%Y%m%d)}"

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --prefix)
      [[ "$#" -ge 2 ]] || { usage; exit 2; }
      SYSROOT="$2"
      shift 2
      ;;
    --cache)
      [[ "$#" -ge 2 ]] || { usage; exit 2; }
      CACHE_ROOT="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

command -v apt-get >/dev/null || { echo "FAIL: apt-get is required" >&2; exit 1; }
command -v dpkg-deb >/dev/null || { echo "FAIL: dpkg-deb is required" >&2; exit 1; }
command -v dpkg >/dev/null || { echo "FAIL: dpkg is required" >&2; exit 1; }
[[ "$(dpkg --print-architecture)" == "amd64" ]] || {
  echo "FAIL: certified rootless desktop sysroot currently supports amd64 only" >&2
  exit 1
}

DEV_PACKAGES=(
  pkgconf pkgconf-bin libpkgconf7
  libgtk-3-dev libwebkit2gtk-4.1-dev libsoup-3.0-dev
  libjavascriptcoregtk-4.1-dev libayatana-appindicator3-dev
  libayatana-indicator3-dev libdbusmenu-glib-dev librsvg2-dev libxml2-dev
  libgio-2.0-dev libglib2.0-dev libgio-2.0-dev-bin libglib2.0-dev-bin
  girepository-tools libglib2.0-bin libglib2.0-data
  libsysprof-capture-4-dev libpcre2-dev libpango1.0-dev
  libgdk-pixbuf-2.0-dev libcairo2-dev libatk1.0-dev libmount-dev
  libselinux-dev libsqlite3-dev libpsl-dev libbrotli-dev libnghttp2-dev
  libayatana-ido3-dev libffi-dev zlib1g-dev libwayland-dev libx11-dev
  libxcomposite-dev libxcursor-dev libxdamage-dev libxext-dev libxfixes-dev
  libxi-dev libxinerama-dev libxkbcommon-dev libxrandr-dev libepoxy-dev
  libegl1-mesa-dev libfontconfig-dev libfribidi-dev libatk-bridge2.0-dev
  wayland-protocols
  libharfbuzz-dev libpng-dev libfreetype-dev libxrender-dev
  libxcb-render0-dev libxcb-shm0-dev libpixman-1-dev libglycin-2-dev
  libblkid-dev libsepol-dev libidn2-dev libdav1d-dev libbz2-dev
  libgraphite2-dev libthai-dev libxft-dev libseccomp-dev liblcms2-dev
  libdatrie-dev libcloudproviders-dev libatspi2.0-dev libdbus-1-dev
  libsystemd-dev libxtst-dev libxres-dev
)

# The development packages provide linker symlinks; these runtime packages
# provide the versioned ELF targets required by lld and by linuxdeploy's GTK
# plugin. Runtime files are extracted into the user-owned sysroot, never
# installed over the host runtime.
RUNTIME_PACKAGES=(
  libatk-bridge2.0-0t64 libatk1.0-0t64 libatspi2.0-0t64
  libayatana-appindicator3-1 libayatana-ido3-0.4-0 libayatana-indicator3-7
  libblkid1 libbrotli1 libbz2-1.0 libcairo-gobject2
  libcairo-script-interpreter2 libcairo2 libcloudproviders0 libdatrie1
  libdav1d7 libdbus-1-3 libdbusmenu-glib4 libepoxy0 libffi8 libfontconfig1
  libfreetype6 libfribidi0 libgdk-pixbuf-2.0-0 libgdk-pixbuf2.0-common
  libglib2.0-0t64 libglycin-2-0 libgraphite2-3 libgtk-3-0t64
  libgtk-3-common libharfbuzz-gobject0 libharfbuzz-icu0
  libharfbuzz-subset0 libharfbuzz0b libidn2-0 libjavascriptcoregtk-4.1-0
  liblcms2-2 libmount1 libnghttp2-14 libpango-1.0-0 libpangocairo-1.0-0
  libpangoft2-1.0-0 libpangoxft-1.0-0 libpcre2-16-0 libpcre2-8-0
  libpcre2-posix3 libpixman-1-0 libpng16-16t64 libpsl5t64 librsvg2-2
  librsvg2-common
  libseccomp2 libselinux1 libsepol2 libsoup-3.0-0 libsqlite3-0 libsystemd0
  libthai0 libwayland-client0 libwayland-cursor0 libwayland-egl1
  libwayland-server0 libwebkit2gtk-4.1-0 libx11-6 libxcb-render0
  libxcb-shm0 libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3
  libxft2 libxi6 libxinerama1 libxkbcommon0 libxml2-16 libxrandr2
  libxrender1 libxres1 libxtst6 zlib1g
)

mkdir -p "${SYSROOT}" "${CACHE_ROOT}"

ALL_PACKAGES=("${DEV_PACKAGES[@]}" "${RUNTIME_PACKAGES[@]}")
TO_DOWNLOAD=()
for package_name in "${ALL_PACKAGES[@]}"; do
  package_present=0
  for deb_file in "${CACHE_ROOT}/${package_name}"_*.deb; do
    if [[ -f "${deb_file}" ]]; then
      package_present=1
      break
    fi
  done
  [[ "${package_present}" -eq 1 ]] || TO_DOWNLOAD+=("${package_name}")
done

if [[ "${#TO_DOWNLOAD[@]}" -gt 0 ]]; then
  DOWNLOAD_LOG="${CACHE_ROOT}/download.log"
  if ! apt-get download "${TO_DOWNLOAD[@]}" >"${DOWNLOAD_LOG}" 2>&1; then
    echo "FAIL: apt download failed; see ${DOWNLOAD_LOG}" >&2
    tail -80 "${DOWNLOAD_LOG}" >&2
    exit 1
  fi
fi

for deb_file in "${CACHE_ROOT}"/*.deb; do
  [[ -f "${deb_file}" ]] || continue
  dpkg-deb -x "${deb_file}" "${SYSROOT}"
done

PKG_CONFIG_BIN="${SYSROOT}/usr/bin/pkg-config"
[[ -x "${PKG_CONFIG_BIN}" ]] || {
  echo "FAIL: extracted pkg-config is missing: ${PKG_CONFIG_BIN}" >&2
  exit 1
}

export PD_FLOW_BUILD_SYSROOT="${SYSROOT}"
export PKG_CONFIG="${PKG_CONFIG_BIN}"
export PKG_CONFIG_SYSROOT_DIR="${SYSROOT}"
export PKG_CONFIG_PATH="${SYSROOT}/usr/lib/x86_64-linux-gnu/pkgconfig:${SYSROOT}/usr/share/pkgconfig${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}"
export LD_LIBRARY_PATH="${SYSROOT}/usr/lib/x86_64-linux-gnu:${SYSROOT}/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

REQUIRED_PC=(
  glib-2.0 gtk+-3.0 webkit2gtk-4.1 libsoup-3.0 javascriptcoregtk-4.1
  ayatana-appindicator3-0.1 librsvg-2.0 libxml-2.0
)
"${PKG_CONFIG_BIN}" --exists "${REQUIRED_PC[@]}" || {
  echo "FAIL: extracted sysroot cannot resolve the required pkg-config set" >&2
  exit 1
}

printf 'NATIVE BUILD SYSROOT READY\n'
printf 'prefix=%s\n' "${SYSROOT}"
printf 'cache=%s\n' "${CACHE_ROOT}"
printf 'packages=%s\n' "${#ALL_PACKAGES[@]}"
printf 'webkit2gtk=%s\n' "$("${PKG_CONFIG_BIN}" --modversion webkit2gtk-4.1)"
printf 'gdk_pixbuf_modules=%s\n' "${SYSROOT}/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0"
