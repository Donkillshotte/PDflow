#!/usr/bin/env bash
# Shared helpers: VCD path + activity TCL for OpenSTA report_power.
# OpenSTA 26Q2: `read_power_activities` is deprecated and calls `read_vcd`
# with the wrong arity. Use `read_vcd -scope … file` (see `help read_vcd`).
#
# RTL VCD (Icarus tb_gcd/dut) only annotates nets whose names match the
# gate-level ODB — typically ports. Unmatched pins keep OpenSTA defaults
# (do NOT follow with set_power_activity -global: that overwrites VCD).
set -euo pipefail

power_vcd_path() {
  local root="$1"
  local vcd="${root}/learn/sim/gcd/gcd.vcd"
  if [[ -f "${vcd}" && -s "${vcd}" ]]; then
    echo "${vcd}"
    return 0
  fi
  return 1
}

# Prints TCL: vectorless global, dynamic VCD, or auto.
# POWER_MODE=vectorless|dynamic|auto  (default auto)
power_activity_tcl() {
  local root="$1"
  local mode="${POWER_MODE:-auto}"
  local vcd=""
  if [[ "${mode}" == "vectorless" ]]; then
    cat <<'EOF'
set_power_activity -global -activity 0.5 -duty 0.5
puts "ACTIVITY_SOURCE vectorless global 0.5"
EOF
    return 0
  fi
  if [[ "${mode}" == "dynamic" || "${mode}" == "auto" ]]; then
    if vcd="$(power_vcd_path "${root}")"; then
      cat <<EOF
read_vcd -scope tb_gcd/dut ${vcd}
puts "ACTIVITY_SOURCE vcd ${vcd}"
EOF
      return 0
    fi
  fi
  if [[ "${mode}" == "dynamic" ]]; then
    echo "puts \"ACTIVITY_SOURCE missing_vcd — run rtl_sim\""
    echo "set_power_activity -global -activity 0.2 -duty 0.5"
    return 0
  fi
  cat <<'EOF'
set_power_activity -global -activity 0.2 -duty 0.5
puts "ACTIVITY_SOURCE synthetic global 0.2"
EOF
}
