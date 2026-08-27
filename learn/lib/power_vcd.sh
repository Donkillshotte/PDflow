#!/usr/bin/env bash
# Shared helpers: VCD path + activity TCL block for OpenROAD report_power.
# Source from run_activity_power.sh / run_chip_pdn_ir.sh / run_power_chain.sh
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

# Prints TCL: read_power_activities when VCD exists, else synthetic global activity.
power_activity_tcl() {
  local root="$1"
  local vcd
  if vcd="$(power_vcd_path "${root}")"; then
    cat <<EOF
read_power_activities -vcd ${vcd}
puts "ACTIVITY_SOURCE vcd ${vcd}"
EOF
  else
    cat <<'EOF'
set_power_activity -global -activity 0.2 -duty 0.5
puts "ACTIVITY_SOURCE synthetic global 0.2"
EOF
  fi
}
