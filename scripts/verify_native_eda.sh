#!/usr/bin/env bash
# Verify the complete PDflow native host toolchain.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT}/scripts/native_eda_env.sh"

required=(openroad sta klayout yosys iverilog vvp ngspice)
for tool_name in "${required[@]}"; do
  tool_path="$(command -v "${tool_name}" 2>/dev/null || true)"
  if [[ -z "${tool_path}" ]]; then
    echo "MISSING ${tool_name}" >&2
    exit 1
  fi
  printf '%-10s %s\n' "${tool_name}" "${tool_path}"
done

openroad -version | sed -n '1p'
sta -version | sed -n '1p'
klayout -v
yosys -V
iverilog -V 2>&1 | sed -n '1p'
ngspice -v | sed -n '1p'

printf 'read_verilog /dev/null\nprep\nwrite_json /tmp/pdflow-native-yosys.json\n' | yosys -q >/dev/null
test -s /tmp/pdflow-native-yosys.json

printf 'module pdflow_native_top; initial $display("PDflow native Icarus OK"); endmodule\n' >/tmp/pdflow-native.v
iverilog -o /tmp/pdflow-native.vvp /tmp/pdflow-native.v
vvp /tmp/pdflow-native.vvp | grep -q 'PDflow native Icarus OK'

printf '* pdflow native ngspice\nV1 in 0 1\nR1 in 0 1k\n.op\n.end\n' >/tmp/pdflow-native.cir
ngspice -b -o /tmp/pdflow-native.log /tmp/pdflow-native.cir >/tmp/pdflow-native.stdout 2>&1
grep -q 'No. of Data Rows' /tmp/pdflow-native.log
if grep -Eqi 'error opening code model|couldn.t be loaded|tmpfile\(\)' /tmp/pdflow-native.log /tmp/pdflow-native.stdout; then
  echo "ngspice native smoke reported an initialization error" >&2
  exit 1
fi

openroad -exit <<'TCL'
puts "PDflow native OpenROAD OK"
TCL
sta -version >/dev/null
echo "NATIVE EDA TOOLCHAIN VERIFIED"
