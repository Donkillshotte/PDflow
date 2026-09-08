# Optional local prefixes for lab binaries (HotSpot, Xyce). Source from scripts.
# Does not replace system PATH tools when they already exist.
lab_tools_path() {
  local root="$1"
  export PATH="${root}/learn/tools/hotspot:${root}/learn/tools/fastercap:${root}/learn/tools/xyce/bin:${PATH}"
  # The vlsida-eda Xyce archive carries an $ORIGIN/../lib RPATH.  Do not
  # prepend that directory to the whole process: its bundled serial
  # OpenBLAS can shadow the system BLAS and break Python/NumPy imports.
  # Set PDflow_XYCE_USE_LD_LIBRARY_PATH=1 only for a non-RPATH build.
  if [[ "${PDflow_XYCE_USE_LD_LIBRARY_PATH:-0}" == "1" && -d "${root}/learn/tools/xyce/lib" ]]; then
    export LD_LIBRARY_PATH="${root}/learn/tools/xyce/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  fi
}

hotspot_bin() {
  local root="$1"
  if command -v hotspot >/dev/null 2>&1; then
    command -v hotspot
    return 0
  fi
  if [[ -x "${root}/learn/tools/hotspot/hotspot" ]]; then
    echo "${root}/learn/tools/hotspot/hotspot"
    return 0
  fi
  return 1
}

xyce_bin() {
  local root="$1"
  for c in Xyce xyce; do
    if command -v "${c}" >/dev/null 2>&1; then
      command -v "${c}"
      return 0
    fi
  done
  if [[ -x "${root}/learn/tools/xyce/bin/Xyce" ]]; then
    echo "${root}/learn/tools/xyce/bin/Xyce"
    return 0
  fi
  return 1
}
