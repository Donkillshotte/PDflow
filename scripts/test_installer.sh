#!/usr/bin/env bash
# Offline contract tests for the native PDflow installer and launcher.
# These tests never run apt, download archives, build EDA tools, or modify the
# repository. They use disposable temporary prefixes for helper checks.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/pdflow-installer-test.XXXXXX")"
cleanup() { rm -rf "${TEMP_ROOT}"; }
trap cleanup EXIT

pass() { printf 'OK  %s\n' "$*"; }
fail() { printf 'FAIL %s\n' "$*" >&2; exit 1; }

for script_file in \
  "${ROOT}/install.sh" \
  "${ROOT}/scripts/install_pdflow.sh" \
  "${ROOT}/scripts/install_node_runtime.sh" \
  "${ROOT}/scripts/install_bazelisk.sh" \
  "${ROOT}/scripts/pdflow"; do
  bash -n "${script_file}" || fail "bash syntax: ${script_file}"
done
pass "installer shell syntax"

"${ROOT}/install.sh" --help >/dev/null || fail "installer help"
"${ROOT}/scripts/install_node_runtime.sh" --help >/dev/null || fail "Node helper help"
"${ROOT}/scripts/install_bazelisk.sh" --help >/dev/null || fail "Bazelisk helper help"
"${ROOT}/scripts/pdflow" --help >/dev/null || fail "launcher help"
pass "help and argument contracts"

if "${ROOT}/scripts/install_node_runtime.sh" --check \
  --prefix "${TEMP_ROOT}/node" >/dev/null 2>&1; then
  fail "missing Node runtime incorrectly passed --check"
fi
mkdir -p "${TEMP_ROOT}/node/bin"
printf '#!/usr/bin/env bash\nprintf "v20.19.5\\n"\n' >"${TEMP_ROOT}/node/bin/node"
chmod 0755 "${TEMP_ROOT}/node/bin/node"
"${ROOT}/scripts/install_node_runtime.sh" --check \
  --prefix "${TEMP_ROOT}/node" >/dev/null || fail "valid Node runtime failed --check"
pass "Node runtime check"

if "${ROOT}/scripts/install_bazelisk.sh" --check \
  --path "${TEMP_ROOT}/bazelisk" >/dev/null 2>&1; then
  fail "missing Bazelisk incorrectly passed --check"
fi
printf '#!/usr/bin/env bash\nprintf "1.29.0\\n"\n' >"${TEMP_ROOT}/bazelisk"
chmod 0755 "${TEMP_ROOT}/bazelisk"
FAKE_BAZELISK_SHA256="$(sha256sum "${TEMP_ROOT}/bazelisk" | cut -d' ' -f1)"
PD_FLOW_BAZELISK_SHA256="${FAKE_BAZELISK_SHA256}" \
  "${ROOT}/scripts/install_bazelisk.sh" --check \
  --path "${TEMP_ROOT}/bazelisk" >/dev/null || fail "valid Bazelisk failed --check"
pass "Bazelisk check"

python3 -m json.tool "${ROOT}/config/pdflow/native_toolchain.json" >/dev/null \
  || fail "native toolchain manifest is invalid JSON"
grep -q '"install_prefix": null' "${ROOT}/config/pdflow/native_toolchain.json" \
  || fail "native toolchain manifest contains a host-specific prefix"
pass "portable native toolchain manifest"

for protected_file in .sshkey.swp sshkey sshkey.pub; do
  git -C "${ROOT}" check-ignore -q "${protected_file}" \
    || fail "local SSH artifact is not ignored: ${protected_file}"
done
pass "local SSH artifacts remain untracked and ignored"

if grep -RInE '(^|[[:space:]])(docker|podman)([[:space:]]|$)' \
  "${ROOT}/scripts/install_pdflow.sh" "${ROOT}/scripts/install_node_runtime.sh" \
  "${ROOT}/scripts/install_bazelisk.sh" >/dev/null; then
  fail "native installer references a container runtime"
fi
pass "native-only installer contract"

printf 'INSTALLER CONTRACTS PASSED\n'
