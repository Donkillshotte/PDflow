#!/usr/bin/env bash
# Configure the native, host-installed PDflow EDA toolchain.
#
# This file is intentionally sourceable.  It never starts a container and it
# never changes the system package database.  The default prefix is the
# per-user native installation used by the local Linux workstation; callers
# can override it with PD_FLOW_EDA_PREFIX.

if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  _PD_FLOW_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  _PD_FLOW_ROOT="$(cd "${_PD_FLOW_ENV_DIR}/.." && pwd)"
else
  _PD_FLOW_ROOT="$(pwd)"
fi

_PD_FLOW_USER_HOME="${PD_FLOW_USER_HOME:-${HOME:-/home/kalishot}}"
PD_FLOW_EDA_PREFIX="${PD_FLOW_EDA_PREFIX:-${_PD_FLOW_USER_HOME}/.local/pdflow-eda}"

_PD_FLOW_CARGO_HOME="${CARGO_HOME:-${_PD_FLOW_USER_HOME}/.cargo}"
if [[ -d "${_PD_FLOW_CARGO_HOME}/bin" ]]; then
  export PATH="${_PD_FLOW_CARGO_HOME}/bin:${PATH}"
fi
unset _PD_FLOW_CARGO_HOME

# Optional user-owned native build sysroot.  This is useful on hosts that have
# the GTK/WebKit runtime installed but cannot install development packages in
# the system package database.  It is deliberately additive: native runtime
# tools and the host linker remain available, while pkg-config receives a
# deterministic source of headers, metadata and link flags for Tauri builds.
_PD_FLOW_BUILD_SYSROOT="${PD_FLOW_BUILD_SYSROOT:-${_PD_FLOW_USER_HOME}/.local/pdflow-build-sysroot}"
_PD_FLOW_SYSROOT_PKG_CONFIG="${_PD_FLOW_BUILD_SYSROOT}/usr/bin/pkg-config"
if [[ -x "${_PD_FLOW_SYSROOT_PKG_CONFIG}" ]]; then
  export PD_FLOW_BUILD_SYSROOT="${_PD_FLOW_BUILD_SYSROOT}"
  export PATH="${_PD_FLOW_ROOT}/scripts:${PD_FLOW_BUILD_SYSROOT}/usr/bin:${PATH}"
  export PKG_CONFIG="${_PD_FLOW_SYSROOT_PKG_CONFIG}"
  export PKG_CONFIG_SYSROOT_DIR="${PD_FLOW_BUILD_SYSROOT}"
  export PKG_CONFIG_PATH="${PD_FLOW_BUILD_SYSROOT}/usr/lib/x86_64-linux-gnu/pkgconfig:${PD_FLOW_BUILD_SYSROOT}/usr/share/pkgconfig${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}"
  export C_INCLUDE_PATH="${PD_FLOW_BUILD_SYSROOT}/usr/include/x86_64-linux-gnu:${PD_FLOW_BUILD_SYSROOT}/usr/include${C_INCLUDE_PATH:+:${C_INCLUDE_PATH}}"
  export CPLUS_INCLUDE_PATH="${PD_FLOW_BUILD_SYSROOT}/usr/include/x86_64-linux-gnu:${PD_FLOW_BUILD_SYSROOT}/usr/include${CPLUS_INCLUDE_PATH:+:${CPLUS_INCLUDE_PATH}}"
  export LIBRARY_PATH="${PD_FLOW_BUILD_SYSROOT}/usr/lib/x86_64-linux-gnu:${PD_FLOW_BUILD_SYSROOT}/usr/lib${LIBRARY_PATH:+:${LIBRARY_PATH}}"
  export LD_LIBRARY_PATH="${PD_FLOW_BUILD_SYSROOT}/usr/lib/x86_64-linux-gnu:${PD_FLOW_BUILD_SYSROOT}/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
fi
unset _PD_FLOW_BUILD_SYSROOT _PD_FLOW_SYSROOT_PKG_CONFIG

if [[ ! -d "${PD_FLOW_EDA_PREFIX}/usr" ]]; then
  unset _PD_FLOW_ENV_DIR _PD_FLOW_ROOT _PD_FLOW_USER_HOME
  return 0 2>/dev/null || exit 0
fi

export PD_FLOW_EDA_PREFIX
export PD_FLOW_NATIVE_EDA=1
export PATH="${_PD_FLOW_ROOT}/tools/native/bin:${_PD_FLOW_ROOT}/learn/tools/xyce/bin:${_PD_FLOW_ROOT}/learn/tools/fastercap:${_PD_FLOW_ROOT}/learn/tools/hotspot:${PD_FLOW_EDA_PREFIX}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${PD_FLOW_EDA_PREFIX}/usr/lib/klayout:${PD_FLOW_EDA_PREFIX}/usr/lib/x86_64-linux-gnu:${PD_FLOW_EDA_PREFIX}/usr/lib:${PD_FLOW_EDA_PREFIX}/usr/lib/tcltk/x86_64-linux-gnu/tclreadline2.3.8:${PD_FLOW_EDA_PREFIX}/opt/or-tools/lib:${LD_LIBRARY_PATH:-}"
export TCLLIBPATH="${PD_FLOW_EDA_PREFIX}/usr/lib/tcltk/x86_64-linux-gnu/tclreadline2.3.8"
export IVERILOG_VPI_MODULE_PATH="${PD_FLOW_EDA_PREFIX}/usr/lib/x86_64-linux-gnu/ivl"
export YOSYS_DATDIR="${PD_FLOW_EDA_PREFIX}/usr/share/yosys"
export YOSYS_ABC="${PD_FLOW_EDA_PREFIX}/usr/bin/yosys-abc"
export KLAYOUT_PATH="${PD_FLOW_EDA_PREFIX}/usr/share/klayout:${PD_FLOW_EDA_PREFIX}/usr/lib/klayout"
export SPICE_LIB_DIR="${PD_FLOW_EDA_PREFIX}/usr/share/ngspice"
export SPICE_SCRIPTS="${PD_FLOW_EDA_PREFIX}/usr/share/ngspice/scripts"
export NGSPICE_INPUT_DIR="${PD_FLOW_EDA_PREFIX}/usr/share/ngspice"
export NGSPICE_OSDI_DIR="${PD_FLOW_EDA_PREFIX}/usr/lib/x86_64-linux-gnu/ngspice"

# Keep native numerical tools aligned with the resource executor's four-CPU
# budget even when an operator launches one directly from a shell. Preserve a
# smaller explicit value, but clamp invalid or larger values unless an
# explicit resource increase has been authorized.
_PD_FLOW_THREAD_CAP="${PD_FLOW_NUM_THREADS:-4}"
if [[ ! "${_PD_FLOW_THREAD_CAP}" =~ ^[1-9][0-9]*$ ]]; then
  _PD_FLOW_THREAD_CAP=4
fi
if [[ "${_PD_FLOW_THREAD_CAP}" -gt 4 && "${PD_FLOW_RESOURCE_ALLOW_INCREASE:-0}" != "1" ]]; then
  _PD_FLOW_THREAD_CAP=4
fi
for _pd_flow_thread_var in \
  OMP_NUM_THREADS OPENBLAS_NUM_THREADS MKL_NUM_THREADS NUMEXPR_NUM_THREADS \
  BLIS_NUM_THREADS VECLIB_MAXIMUM_THREADS RAYON_NUM_THREADS CMAKE_BUILD_PARALLEL_LEVEL
do
  _pd_flow_thread_value="$(printenv "${_pd_flow_thread_var}" 2>/dev/null || true)"
  if [[ ! "${_pd_flow_thread_value}" =~ ^[1-9][0-9]*$ ]] \
    || [[ "${_pd_flow_thread_value}" -gt "${_PD_FLOW_THREAD_CAP}" ]]; then
    export "${_pd_flow_thread_var}=${_PD_FLOW_THREAD_CAP}"
  fi
done
export PD_FLOW_NUM_THREADS="${_PD_FLOW_THREAD_CAP}"
unset _PD_FLOW_THREAD_CAP _pd_flow_thread_var _pd_flow_thread_value

# The ODB Python module is built from the same native OpenROAD source tree and
# installed next to the OpenROAD executable.  Keep it explicit instead of
# putting it on the global PYTHONPATH: only ODB-aware operations should opt in
# to the binding, and the caller can still control the rest of its Python
# environment.
if [[ -f "${PD_FLOW_EDA_PREFIX}/native-openroad/python/odb.py" \
  && -f "${PD_FLOW_EDA_PREFIX}/native-openroad/python/_odb.so" ]]; then
  export OPENROAD_ODB_PYTHONPATH="${PD_FLOW_EDA_PREFIX}/native-openroad/python"
else
  unset OPENROAD_ODB_PYTHONPATH
fi

export OPENROAD_BIN="${_PD_FLOW_ROOT}/tools/native/bin/openroad"
export OPENROAD_EXE="${_PD_FLOW_ROOT}/tools/native/bin/openroad"
export OPENSTA_BIN="${_PD_FLOW_ROOT}/tools/native/bin/sta"
export OPENSTA_EXE="${_PD_FLOW_ROOT}/tools/native/bin/sta"
export KLAYOUT_BIN="${_PD_FLOW_ROOT}/tools/native/bin/klayout"
export KLAYOUT_CMD="${_PD_FLOW_ROOT}/tools/native/bin/klayout"
export YOSYS_BIN="${_PD_FLOW_ROOT}/tools/native/bin/yosys"
export YOSYS_EXE="${_PD_FLOW_ROOT}/tools/native/bin/yosys"
export IVERILOG_BIN="${_PD_FLOW_ROOT}/tools/native/bin/iverilog"
export IVERILOG="${_PD_FLOW_ROOT}/tools/native/bin/iverilog"
export NGSPICE_BIN="${_PD_FLOW_ROOT}/tools/native/bin/ngspice"
export NGSPICE_EXE="${_PD_FLOW_ROOT}/tools/native/bin/ngspice"

unset _PD_FLOW_ENV_DIR _PD_FLOW_ROOT _PD_FLOW_USER_HOME
