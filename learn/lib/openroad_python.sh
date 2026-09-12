#!/usr/bin/env bash
# Run OpenROAD's embedded Python with a complete matching standard library.
# Some packaged OpenROAD binaries carry only part of Python 3.12 next to the
# executable; prefer a compatible local runtime when one is available.

openroad_python_home() {
  local candidate tool exe prefix
  for candidate in "${OPENROAD_PYTHONHOME:-}" "${PYTHONHOME:-}"; do
    if [[ -n "${candidate}" && -f "${candidate}/lib/python3.12/re/__init__.py" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  for tool in openroad klayout python3 python; do
    exe="$(command -v "${tool}" 2>/dev/null || true)"
    [[ -n "${exe}" ]] || continue
    prefix="$(cd "$(dirname "${exe}")/.." 2>/dev/null && pwd || true)"
    if [[ -f "${prefix}/lib/python3.12/re/__init__.py" ]]; then
      printf '%s\n' "${prefix}"
      return 0
    fi
  done
  return 1
}

openroad_python() {
  local home=""
  local -a env_args=(-u PYTHONPATH)
  home="$(openroad_python_home || true)"
  if [[ -n "${home}" ]]; then
    env_args+=(PYTHONHOME="${home}")
  else
    env_args+=(-u PYTHONHOME)
  fi
  if [[ -n "${OPENROAD_PYTHONPATH:-}" ]]; then
    env_args+=(PYTHONPATH="${OPENROAD_PYTHONPATH}")
  fi
  env "${env_args[@]}" openroad "$@"
}

# Run a Python helper with OpenDB's native SWIG module.  Recent upstream
# OpenROAD Bazel builds may omit the embedded interpreter while still
# producing the supported ODB extension; this path keeps ODB inspection fully
# native and avoids silently falling back to a text parser or a container.
openroad_odb_python() {
  local module_path="${OPENROAD_ODB_PYTHONPATH:-}"
  local python_bin="${OPENROAD_PYTHON_BIN:-python3}"
  if [[ -z "${module_path}" \
    || ! -f "${module_path}/odb.py" \
    || ! -f "${module_path}/_odb.so" ]]; then
    echo "FAIL native OpenDB Python binding is not installed" >&2
    echo "Set OPENROAD_ODB_PYTHONPATH to a verified native binding directory" >&2
    return 1
  fi
  PYTHONPATH="${module_path}${PYTHONPATH:+:${PYTHONPATH}}" \
    env -u PYTHONHOME "${python_bin}" "$@"
}

openroad_embedded_python_available() {
  command -v openroad >/dev/null 2>&1 \
    && openroad -help 2>&1 | grep -q -- ' -python '
}
