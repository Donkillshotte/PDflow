#!/usr/bin/env bash
# Install the complete native PDflow workstation on Linux.
#
# This is the single implementation behind ./install.sh. It is intentionally
# conservative around existing checkouts: generated directories and fetched
# tool sources are created only when absent, and a dirty source tree is never
# realigned or overwritten implicitly.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

DEFAULT_EDA_PREFIX="${HOME:-/home/kalishot}/.local/pdflow-eda"
DEFAULT_NODE_VERSION="20.19.5"
DEFAULT_NODE_DATA_ROOT="${XDG_DATA_HOME:-${HOME:-/home/kalishot}/.local/share}/pdflow"
DEFAULT_APP_DIR="${DEFAULT_NODE_DATA_ROOT}"
DEFAULT_BIN_DIR="${XDG_BIN_HOME:-${HOME:-/home/kalishot}/.local/bin}"
ORFS_URL="https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git"
ORFS_TAG="${PD_FLOW_ORFS_TAG:-26Q2}"
ORFS_COMMIT="${PD_FLOW_ORFS_COMMIT:-036d106273e66855cd5214d49518fd0f0df7de61}"
OPENROAD_URL="https://github.com/The-OpenROAD-Project/OpenROAD.git"
OPENROAD_COMMIT="${PD_FLOW_OPENROAD_COMMIT:-a9147cf3aebe65e058bb3fa89c1f9e524488dbb8}"
TAURI_VERSION="${PD_FLOW_TAURI_VERSION:-2.11.4}"

EDA_PREFIX="${PD_FLOW_EDA_PREFIX:-${DEFAULT_EDA_PREFIX}}"
NODE_VERSION="${PD_FLOW_NODE_VERSION:-${DEFAULT_NODE_VERSION}}"
NODE_PREFIX="${PD_FLOW_NODE_PREFIX:-${DEFAULT_NODE_DATA_ROOT}/node-v${NODE_VERSION}-linux-x64}"
NODE_PREFIX_EXPLICIT=0
[[ -n "${PD_FLOW_NODE_PREFIX:-}" ]] && NODE_PREFIX_EXPLICIT=1
APP_DIR="${PD_FLOW_APP_DIR:-${DEFAULT_APP_DIR}}"
BIN_DIR="${PD_FLOW_BIN_DIR:-${DEFAULT_BIN_DIR}}"
INSTALL_SYSTEM_PACKAGES=1
INSTALL_EDA=1
INSTALL_DESKTOP=1
CHECK_ONLY=0
AUTO_YES=0
FORCE_NODE=0
CHECK_FAILED=0
APT_UPDATED=0
OPENROAD_SOURCE_ROOT=""

usage() {
  cat <<'EOF'
PDflow native Linux installer

Usage: ./install.sh [options]

The default installs the native EDA toolchain, the pinned Node.js runtime,
Studio dependencies, and a Tauri AppImage launcher. No Docker runtime is
used. System package installation requires sudo when this process is not
running as root.

Options:
  --yes                 accept system package installation without prompting
  --check               read-only prerequisite and installation check
  --no-system-packages  do not use apt or sudo
  --no-eda              skip ORFS/OpenROAD and EDA checks
  --no-desktop          install tools and Studio dependencies, skip Tauri
  --force-node          replace an invalid user Node target (kept as .stale)
  --eda-prefix PATH     native EDA prefix (default: ~/.local/pdflow-eda)
  --node-prefix PATH    exact Node install directory
  --node-version VER    Node version (non-default requires a SHA digest)
  --app-dir PATH        installed desktop bundle directory
  --bin-dir PATH        user launcher directory
  --help                show this help

Useful environment overrides:
  PD_FLOW_OPENROAD_ROOT, PD_FLOW_OPENROAD_BUILD_TIMEOUT,
  PD_FLOW_ALLOW_DIRTY_OPENROAD=1, PD_FLOW_ALLOW_ORFS_REALIGN=1

Examples:
  ./install.sh --yes
  ./install.sh --yes --no-desktop
  ./install.sh --check
EOF
}

die() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

warn() {
  printf 'WARN: %s\n' "$*" >&2
}

info() {
  printf '==> %s\n' "$*"
}

is_installed_package() {
  dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q '^install ok installed$'
}

apt_has_candidate() {
  apt-cache show "$1" >/dev/null 2>&1
}

apt_run() {
  if [[ "${EUID}" -eq 0 ]]; then
    DEBIAN_FRONTEND=noninteractive apt-get "$@"
  else
    if ! sudo -n true >/dev/null 2>&1 && [[ ! -t 0 ]]; then
      die "sudo needs a password but the installer has no interactive terminal; run ./install.sh --yes from a terminal after authenticating with sudo -v"
    fi
    sudo env DEBIAN_FRONTEND=noninteractive apt-get "$@"
  fi
}

ensure_apt_access() {
  command -v apt-get >/dev/null 2>&1 || die "apt-get is required on Debian-like Linux"
  command -v dpkg-query >/dev/null 2>&1 || die "dpkg-query is required on Debian-like Linux"
  if [[ "${EUID}" -ne 0 ]]; then
    command -v sudo >/dev/null 2>&1 || die "sudo is required to install system packages; use --no-system-packages only with a prepared host"
  fi
}

ensure_apt_packages() {
  [[ "${INSTALL_SYSTEM_PACKAGES}" == "1" ]] || {
    info "system package installation disabled"
    return 0
  }
  ensure_apt_access
  local package_name
  local missing_packages=()
  for package_name in "$@"; do
    if ! is_installed_package "${package_name}"; then
      missing_packages+=("${package_name}")
    fi
  done
  if [[ "${#missing_packages[@]}" -eq 0 ]]; then
    info "system dependencies already installed"
    return 0
  fi

  local unavailable_packages=()
  for package_name in "${missing_packages[@]}"; do
    if ! apt_has_candidate "${package_name}"; then
      unavailable_packages+=("${package_name}")
    fi
  done
  if [[ "${#unavailable_packages[@]}" -gt 0 && "${APT_UPDATED}" == "0" ]]; then
    info "refreshing apt indexes because package candidates are missing"
    apt_run update
    APT_UPDATED=1
    unavailable_packages=()
    for package_name in "${missing_packages[@]}"; do
      if ! apt_has_candidate "${package_name}"; then
        unavailable_packages+=("${package_name}")
      fi
    done
  fi
  [[ "${#unavailable_packages[@]}" -eq 0 ]] || {
    die "no apt candidate for: ${unavailable_packages[*]} (refresh the distribution indexes or install equivalent native packages)"
  }
  info "installing native system dependencies: ${missing_packages[*]}"
  apt_run install -y --no-install-recommends "${missing_packages[@]}"
}

platform_check() {
  [[ "$(uname -s)" == "Linux" ]] || die "PDflow's certified installer supports Linux only"
  case "$(uname -m)" in
    x86_64|amd64) ;;
    *) die "the certified native toolchain currently supports Linux x86_64 only" ;;
  esac
  [[ -r /etc/os-release ]] || die "/etc/os-release is required to identify a Debian-like host"
  # shellcheck disable=SC1091
  source /etc/os-release
  local distro_ids="${ID:-} ${ID_LIKE:-}"
  [[ "${distro_ids}" == *debian* || "${distro_ids}" == *ubuntu* || "${distro_ids}" == *kali* ]] || {
    die "unsupported distribution (${ID:-unknown}); use a Debian/Kali/Ubuntu host or install the documented native prerequisites manually"
  }
  command -v git >/dev/null 2>&1 || die "git is required"
  command -v curl >/dev/null 2>&1 || die "curl is required"
  command -v sha256sum >/dev/null 2>&1 || die "sha256sum is required"
}

select_optional_package() {
  local candidate
  for candidate in "$@"; do
    if is_installed_package "${candidate}" || apt_has_candidate "${candidate}"; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

system_packages() {
  local packages=(
    build-essential cmake ninja-build pkg-config pkgconf git curl ca-certificates
    file patchelf xz-utils tar python3 python3-venv python3-dev python3-numpy
    python3-scipy tcl-dev tcllib bison flex time libreadline-dev libffi-dev
    zlib1g-dev libssl-dev libeigen3-dev libomp-dev libxdo-dev libgtk-3-dev
    librsvg2-dev iverilog ngspice klayout yosys
  )
  if [[ "${INSTALL_DESKTOP}" == "1" ]]; then
    local webkit_package indicator_package soup_package
    webkit_package="$(select_optional_package libwebkit2gtk-4.1-dev libwebkit2gtk-4.0-dev || true)"
    [[ -n "${webkit_package}" ]] || die "neither libwebkit2gtk-4.1-dev nor libwebkit2gtk-4.0-dev is available"
    packages+=("${webkit_package}")
    indicator_package="$(select_optional_package libayatana-appindicator3-dev libappindicator3-dev || true)"
    [[ -n "${indicator_package}" ]] || die "no supported Linux AppIndicator development package is available"
    packages+=("${indicator_package}")
    soup_package="$(select_optional_package libsoup-3.0-dev libsoup2.4-dev || true)"
    [[ -n "${soup_package}" ]] && packages+=("${soup_package}")
    packages+=(rustc cargo)
  fi
  printf '%s\n' "${packages[@]}"
}

run_guarded() {
  local label="$1"
  shift
  export PD_FLOW_RESOURCE_CWD="${PD_FLOW_RESOURCE_CWD:-${ROOT}}"
  export PD_FLOW_EDA_PREFIX="${PD_FLOW_EDA_PREFIX:-${EDA_PREFIX}}"
  local environment_name
  for environment_name in \
    PD_FLOW_NODE PDFLOW_OPENROAD_ROOT PDFLOW_OPENROAD_ODB_ROOT \
    PDFLOW_BAZELISK PDFLOW_OPENROAD_BUILD_TIMEOUT; do
    if [[ -n "${!environment_name:-}" ]]; then
      export "${environment_name}"
    fi
  done
  "${ROOT}/scripts/run_resource_job.sh" "${label}" "$@"
}

native_verify() {
  source "${ROOT}/scripts/native_eda_env.sh"
  run_guarded installer-native-verify bash "${ROOT}/scripts/verify_native_eda.sh"
}

ensure_orfs() {
  local orfs_root="${ROOT}/tools/OpenROAD-flow-scripts"
  if [[ -d "${orfs_root}/.git" ]]; then
    [[ -d "${orfs_root}/flow" ]] || die "existing ORFS checkout is incomplete: ${orfs_root}"
    info "preserving existing ORFS checkout: ${orfs_root}"
    return 0
  fi
  [[ ! -e "${orfs_root}" ]] || die "ORFS path exists but is not a Git checkout: ${orfs_root}"
  local parent_root="${ROOT}/tools"
  local staging_root="${parent_root}/.orfs-install.$$"
  mkdir -p "${parent_root}"
  trap 'rm -rf "${staging_root}"' RETURN
  info "cloning ORFS ${ORFS_TAG} at ${ORFS_COMMIT}" >&2
  git clone --filter=blob:none --no-checkout --branch "${ORFS_TAG}" \
    "${ORFS_URL}" "${staging_root}"
  git -C "${staging_root}" fetch --depth 1 origin "${ORFS_COMMIT}"
  git -C "${staging_root}" checkout --detach "${ORFS_COMMIT}"
  git -C "${staging_root}" submodule update --init --depth 1 --recursive tools/OpenROAD tools/yosys
  mv "${staging_root}" "${orfs_root}"
  trap - RETURN
}

ensure_openroad_source() {
  local source_root="${PDFLOW_OPENROAD_ROOT:-${EDA_PREFIX}/src/openroad-26q3}"
  if [[ -d "${source_root}/.git" ]]; then
    local source_dirty
    source_dirty="$(git -C "${source_root}" status --porcelain --untracked-files=normal)"
    if [[ -n "${source_dirty}" && "${PD_FLOW_ALLOW_DIRTY_OPENROAD:-0}" != "1" ]]; then
      die "OpenROAD source is dirty; refusing to build or realign it (${source_root}). Set PD_FLOW_ALLOW_DIRTY_OPENROAD=1 only after reviewing the changes."
    fi
    if [[ "$(git -C "${source_root}" rev-parse HEAD)" != "${OPENROAD_COMMIT}" ]]; then
      [[ "${PD_FLOW_ALLOW_ORFS_REALIGN:-0}" == "1" ]] || die "OpenROAD source is not pinned to ${OPENROAD_COMMIT}; set PD_FLOW_ALLOW_ORFS_REALIGN=1 explicitly to realign it"
      [[ -z "${source_dirty}" ]] || die "OpenROAD source is dirty; refusing explicit realignment"
      git -C "${source_root}" fetch --depth 1 origin "${OPENROAD_COMMIT}"
      git -C "${source_root}" checkout --detach "${OPENROAD_COMMIT}"
    fi
    git -C "${source_root}" submodule update --init --depth 1 --recursive
    OPENROAD_SOURCE_ROOT="${source_root}"
    return 0
  fi
  [[ ! -e "${source_root}" ]] || die "OpenROAD source path exists but is not a Git checkout: ${source_root}"
  local source_parent="$(dirname "${source_root}")"
  local staging_root="${source_parent}/.openroad-install.$$"
  mkdir -p "${source_parent}"
  trap 'rm -rf "${staging_root}"' RETURN
  info "cloning native OpenROAD source at ${OPENROAD_COMMIT}" >&2
  git clone --filter=blob:none --no-checkout "${OPENROAD_URL}" "${staging_root}"
  git -C "${staging_root}" fetch --depth 1 origin "${OPENROAD_COMMIT}"
  git -C "${staging_root}" checkout --detach "${OPENROAD_COMMIT}"
  git -C "${staging_root}" submodule update --init --depth 1 --recursive
  mv "${staging_root}" "${source_root}"
  trap - RETURN
  OPENROAD_SOURCE_ROOT="${source_root}"
}

ensure_bazelisk() {
  mkdir -p "${EDA_PREFIX}/bin"
  PD_FLOW_EDA_PREFIX="${EDA_PREFIX}" \
    "${ROOT}/scripts/install_bazelisk.sh" --path "${EDA_PREFIX}/bin/bazelisk"
}

build_native_openroad() {
  local source_root="$1"
  local bazelisk_path="${EDA_PREFIX}/bin/bazelisk"
  local build_timeout="${PD_FLOW_OPENROAD_BUILD_TIMEOUT:-600}"
  [[ "${build_timeout}" =~ ^[1-9][0-9]*$ ]] || die "PD_FLOW_OPENROAD_BUILD_TIMEOUT must be a positive integer"
  info "building native OpenROAD/OpenSTA from ${source_root}"
  PD_FLOW_EDA_PREFIX="${EDA_PREFIX}" \
    PDFLOW_OPENROAD_ROOT="${source_root}" \
    PDFLOW_OPENROAD_ODB_ROOT="${source_root}" \
    PDFLOW_BAZELISK="${bazelisk_path}" \
    PDFLOW_OPENROAD_BUILD_TIMEOUT="${build_timeout}" \
    PD_FLOW_RESOURCE_CWD="${ROOT}" \
    run_guarded installer-openroad-build bash "${ROOT}/scripts/build_native_openroad.sh"
}

ensure_native_eda() {
  if native_verify >/dev/null 2>&1; then
    info "native EDA toolchain already passes verification"
    ensure_orfs
    return 0
  fi
  [[ "${CHECK_ONLY}" == "0" ]] || return 1
  ensure_bazelisk
  ensure_openroad_source
  local source_root="${OPENROAD_SOURCE_ROOT}"
  [[ -n "${source_root}" ]] || die "OpenROAD source helper returned no source path"
  build_native_openroad "${source_root}"
  ensure_orfs
  native_verify
}

node_bin() {
  printf '%s\n' "${NODE_PREFIX}/bin/node"
}

ensure_node() {
  local node_path
  node_path="$(node_bin)"
  local helper_args=(--prefix "${NODE_PREFIX}")
  [[ "${FORCE_NODE}" == "1" ]] && helper_args+=(--force)
  [[ "${NODE_VERSION}" == "${DEFAULT_NODE_VERSION}" ]] || helper_args+=(--version "${NODE_VERSION}")
  PD_FLOW_NODE_VERSION="${NODE_VERSION}" \
    "${ROOT}/scripts/install_node_runtime.sh" "${helper_args[@]}" >&2
  [[ -x "${node_path}" ]] || die "Node helper did not install ${node_path}"
  export PD_FLOW_NODE="${node_path}"
  export PATH="${NODE_PREFIX}/bin:${PATH}"
  printf '%s\n' "${node_path}"
}

ensure_studio_dependencies() {
  local node_path="$1"
  [[ -f "${ROOT}/studio/package-lock.json" ]] || die "studio/package-lock.json is missing"
  info "installing deterministic Studio dependencies with npm ci"
  PD_FLOW_NODE="${node_path}" PATH="${NODE_PREFIX}/bin:${PATH}" \
    PD_FLOW_RESOURCE_CWD="${ROOT}/studio" \
    run_guarded installer-studio-npm-ci bash -c 'cd "$1" && npm ci' _ "${ROOT}/studio"
  PD_FLOW_NODE="${node_path}" PATH="${NODE_PREFIX}/bin:${PATH}" \
    PD_FLOW_RESOURCE_CWD="${ROOT}/studio" \
    run_guarded installer-studio-lint bash -c 'cd "$1" && npm run lint' _ "${ROOT}/studio"
}

ensure_tauri_cli() {
  source "${ROOT}/scripts/native_eda_env.sh"
  command -v cargo >/dev/null 2>&1 || die "Cargo is missing; install rustc/cargo or use --no-desktop"
  if cargo tauri --version >/dev/null 2>&1; then
    info "Tauri CLI already available: $(cargo tauri --version 2>/dev/null | head -n 1)"
    return 0
  fi
  info "installing native Tauri CLI ${TAURI_VERSION}"
  run_guarded installer-tauri-cli cargo install tauri-cli --version "${TAURI_VERSION}" --locked
  cargo tauri --version >/dev/null 2>&1 || die "Tauri CLI installation did not produce cargo tauri"
}

find_latest_appimage() {
  local bundle_root="${ROOT}/studio/src-tauri/target/release/bundle/appimage"
  local newest_file
  newest_file="$(find "${bundle_root}" -maxdepth 1 -type f -name '*.AppImage' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)"
  [[ -n "${newest_file}" && -f "${newest_file}" ]] || return 1
  printf '%s\n' "${newest_file}"
}

build_desktop() {
  local node_path="$1"
  ensure_tauri_cli
  info "building the native PDflow AppImage"
  PD_FLOW_NODE="${node_path}" PATH="${NODE_PREFIX}/bin:${PATH}" \
    PD_FLOW_RESOURCE_CWD="${ROOT}/studio" \
    run_guarded installer-tauri-build bash -c 'cd "$1" && cargo tauri build' _ "${ROOT}/studio"
}

install_desktop_launcher() {
  local appimage_source="$1"
  local appimage_target="${APP_DIR}/PDflow.AppImage"
  local appimage_tmp="${appimage_target}.tmp.$$"
  local desktop_root="${XDG_DATA_HOME:-${HOME:-/home/kalishot}/.local/share}"
  local desktop_dir="${desktop_root}/applications"
  local launcher_target="${BIN_DIR}/pdflow"
  mkdir -p "${APP_DIR}" "${BIN_DIR}" "${desktop_dir}"
  install -m 0755 "${appimage_source}" "${appimage_tmp}"
  mv -f "${appimage_tmp}" "${appimage_target}"
  if [[ -f "${ROOT}/studio/src-tauri/icons/icon.png" ]]; then
    install -m 0644 "${ROOT}/studio/src-tauri/icons/icon.png" "${APP_DIR}/pdflow.png"
  fi
  if [[ -e "${launcher_target}" && ! -L "${launcher_target}" ]]; then
    mv "${launcher_target}" "${launcher_target}.stale-$(date +%Y%m%d%H%M%S)-$$"
  fi
  ln -sfn "${ROOT}/scripts/pdflow" "${launcher_target}"
  local icon_value="${APP_DIR}/pdflow.png"
  [[ -f "${icon_value}" ]] || icon_value="application-x-executable"
  local desktop_tmp="${desktop_dir}/PDflow.desktop.tmp.$$"
  {
    printf '%s\n' '[Desktop Entry]'
    printf '%s\n' 'Type=Application'
    printf '%s\n' 'Name=PDflow'
    printf '%s\n' 'Comment=Native RTL-to-GDS and power-integrity workspace'
    printf 'Exec=%s\n' "${appimage_target}"
    printf 'TryExec=%s\n' "${appimage_target}"
    printf 'Icon=%s\n' "${icon_value}"
    printf '%s\n' 'Terminal=false'
    printf '%s\n' 'Categories=Development;Electronics;Engineering;'
  } >"${desktop_tmp}"
  chmod 0644 "${desktop_tmp}"
  mv -f "${desktop_tmp}" "${desktop_dir}/PDflow.desktop"
  local manifest_tmp="${APP_DIR}/install.json.tmp.$$"
  {
    printf '{\n'
    printf '  "schema_version": 1,\n'
    printf '  "repository": "%s",\n' "${ROOT}"
    printf '  "eda_prefix": "%s",\n' "${EDA_PREFIX}"
    printf '  "node": "%s",\n' "${NODE_PREFIX}/bin/node"
    printf '  "appimage": "%s",\n' "${appimage_target}"
    printf '  "installed_at": "%s"\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '}\n'
  } >"${manifest_tmp}"
  chmod 0644 "${manifest_tmp}"
  mv -f "${manifest_tmp}" "${APP_DIR}/install.json"
  info "desktop launcher installed: ${launcher_target}"
  info "application bundle installed: ${appimage_target}"
}

check_one() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf 'READY  %s\n' "${label}"
  else
    printf 'GAP    %s\n' "${label}"
    CHECK_FAILED=1
  fi
}

read_only_check() {
  info "read-only PDflow installation check"
  platform_check
  check_one "Node ${NODE_VERSION}" "${ROOT}/scripts/install_node_runtime.sh" --prefix "${NODE_PREFIX}" --check
  if [[ "${INSTALL_EDA}" == "1" ]]; then
    check_one "Bazelisk" "${ROOT}/scripts/install_bazelisk.sh" --path "${EDA_PREFIX}/bin/bazelisk" --check
    if native_verify >/dev/null 2>&1; then
      printf 'READY  native EDA verification\n'
    else
      printf 'GAP    native EDA verification (or resource isolation unavailable)\n'
      CHECK_FAILED=1
    fi
    if [[ -d "${ROOT}/tools/OpenROAD-flow-scripts/flow" ]]; then
      printf 'READY  ORFS checkout\n'
    else
      printf 'GAP    ORFS checkout\n'
      CHECK_FAILED=1
    fi
  fi
  if [[ "${INSTALL_DESKTOP}" == "1" ]]; then
    check_one "Cargo" cargo --version
    check_one "Tauri CLI" cargo tauri --version
    check_one "desktop AppImage" test -x "${APP_DIR}/PDflow.AppImage"
  fi
  if [[ "${CHECK_FAILED}" == "1" ]]; then
    return 1
  fi
  printf 'PDflow installation check PASSED\n'
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --yes)
      AUTO_YES=1
      shift
      ;;
    --check)
      CHECK_ONLY=1
      shift
      ;;
    --no-system-packages)
      INSTALL_SYSTEM_PACKAGES=0
      shift
      ;;
    --no-eda)
      INSTALL_EDA=0
      shift
      ;;
    --no-desktop)
      INSTALL_DESKTOP=0
      shift
      ;;
    --force-node)
      FORCE_NODE=1
      shift
      ;;
    --eda-prefix)
      [[ "$#" -ge 2 ]] || { usage >&2; exit 2; }
      EDA_PREFIX="$2"
      shift 2
      ;;
    --node-prefix)
      [[ "$#" -ge 2 ]] || { usage >&2; exit 2; }
      NODE_PREFIX="$2"
      NODE_PREFIX_EXPLICIT=1
      shift 2
      ;;
    --node-version)
      [[ "$#" -ge 2 ]] || { usage >&2; exit 2; }
      NODE_VERSION="$2"
      shift 2
      ;;
    --app-dir)
      [[ "$#" -ge 2 ]] || { usage >&2; exit 2; }
      APP_DIR="$2"
      shift 2
      ;;
    --bin-dir)
      [[ "$#" -ge 2 ]] || { usage >&2; exit 2; }
      BIN_DIR="$2"
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

if [[ "${NODE_PREFIX_EXPLICIT}" == "0" ]]; then
  NODE_PREFIX="${DEFAULT_NODE_DATA_ROOT}/node-v${NODE_VERSION}-linux-x64"
fi

platform_check
if [[ "${CHECK_ONLY}" == "1" ]]; then
  read_only_check
  exit $?
fi

if [[ "${INSTALL_SYSTEM_PACKAGES}" == "1" && "${AUTO_YES}" != "1" ]]; then
  if [[ ! -t 0 ]]; then
    die "system package installation requires --yes in a non-interactive terminal"
  fi
  printf 'PDflow will install native system packages with apt. Continue? [y/N] '
  read -r confirmation
  [[ "${confirmation}" == "y" || "${confirmation}" == "Y" ]] || die "installation cancelled"
fi

if [[ "${INSTALL_SYSTEM_PACKAGES}" == "1" ]]; then
  mapfile -t requested_packages < <(system_packages)
  ensure_apt_packages "${requested_packages[@]}"
fi

if [[ "${INSTALL_EDA}" == "1" ]]; then
  info "installing/verifying the native EDA toolchain"
  ensure_native_eda
else
  info "EDA installation disabled"
fi

node_path=""
if [[ "${INSTALL_DESKTOP}" == "1" || ! -x "${ROOT}/studio/node-runtime/node" ]]; then
  node_path="$(ensure_node)"
else
  node_path="${ROOT}/studio/node-runtime/node"
fi
ensure_studio_dependencies "${node_path}"

if [[ "${INSTALL_DESKTOP}" == "1" ]]; then
  build_desktop "${node_path}"
  appimage_source="$(find_latest_appimage)" || die "Tauri build completed without an AppImage"
  install_desktop_launcher "${appimage_source}"
else
  info "desktop packaging disabled; browser Studio dependencies are ready"
fi

if [[ "${INSTALL_EDA}" == "1" ]]; then
  info "final native verification"
  native_verify
fi

printf '\nPDflow installation completed successfully.\n'
printf 'Launch: %s\n' "${BIN_DIR}/pdflow"
printf 'Verify: %s --check\n' "${ROOT}/install.sh"
printf 'Repository: %s\n' "${ROOT}"
