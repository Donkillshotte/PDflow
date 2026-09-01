#!/usr/bin/env bash
# Isolated ORFS make finish for the multi-design campaign.
# Never writes FLOW_VARIANT=flowlab|learn|base. AES finish is allowed;
# AES Krylov is a different path and stays refused by admit_solve.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
DESIGN="${DESIGN:-gcd}"
VARIANT="${FLOW_VARIANT:-}"
TARGET="${1:-finish}"
PLATFORM="${PLATFORM:-nangate45}"

LOCKED='^(flowlab|learn|base)$'
if [[ -z "${VARIANT}" ]]; then
  echo "REFUSED: set FLOW_VARIANT (e.g. camp_gcd_clk055). flowlab/learn/base are locked." >&2
  exit 2
fi
if [[ "${VARIANT}" =~ ${LOCKED} ]]; then
  echo "REFUSED: FLOW_VARIANT=${VARIANT} is locked." >&2
  exit 2
fi
if [[ "${VARIANT}" == *krylov* ]]; then
  echo "REFUSED: Krylov is not a finish variant." >&2
  exit 2
fi

case "${DESIGN}" in
  gcd)
    CONFIG_REL="designs/${PLATFORM}/gcd-tutorial/config.mk"
    SRC_CFG="${ROOT}/learn/designs/nangate45/gcd-tutorial"
    DST_CFG="${FLOW}/designs/${PLATFORM}/gcd-tutorial"
    TOP=gcd
    CLK_PORT=clk
    CLK_NAME=core_clock
    DEFAULT_NS=0.46
    ;;
  spi)
    CONFIG_REL="designs/${PLATFORM}/spi/config.mk"
    SRC_CFG="${ROOT}/learn/designs/nangate45/spi"
    DST_CFG="${FLOW}/designs/${PLATFORM}/spi"
    TOP=spi
    CLK_PORT=clk
    CLK_NAME=clk
    DEFAULT_NS=1.0
    ;;
  aes)
    CONFIG_REL="designs/${PLATFORM}/aes/config.mk"
    SRC_CFG=""
    DST_CFG=""
    TOP=aes_cipher_top
    CLK_PORT=clk
    CLK_NAME=clk
    DEFAULT_NS=0.82
    ;;
  ibex)
    # slang plugin is not on this VM. Verilog chameleon/ibex overlay.
    CONFIG_REL="designs/${PLATFORM}/ibex-verilog/config.mk"
    SRC_CFG="${ROOT}/learn/designs/nangate45/ibex-verilog"
    DST_CFG="${FLOW}/designs/${PLATFORM}/ibex-verilog"
    TOP=ibex_core
    CLK_PORT=clk_i
    CLK_NAME=core_clock
    DEFAULT_NS=2.2
    ;;
  dynamic_node)
    CONFIG_REL="designs/${PLATFORM}/dynamic_node/config.mk"
    SRC_CFG=""
    DST_CFG=""
    TOP=dynamic_node_top_wrap
    CLK_PORT=clk
    CLK_NAME=clk
    DEFAULT_NS=6.0
    ;;
  *)
    echo "REFUSED: unknown DESIGN=${DESIGN}" >&2
    exit 2
    ;;
esac

if [[ -n "${SRC_CFG}" ]]; then
  mkdir -p "$(dirname "${DST_CFG}")"
  ln -sfn "${SRC_CFG}" "${DST_CFG}"
  [[ -f "${SRC_CFG}/config.mk" ]] || { echo "FAIL missing ${SRC_CFG}/config.mk" >&2; exit 1; }
fi
[[ -f "${FLOW}/${CONFIG_REL}" ]] || { echo "FAIL missing ${FLOW}/${CONFIG_REL}" >&2; exit 1; }

SDC_NS="${SDC_NS:-${DEFAULT_NS}}"
SDC_DIR="${ROOT}/learn/sim/dse/sdc"
mkdir -p "${SDC_DIR}"
SDC_FILE="${SDC_DIR}/${DESIGN}_${SDC_NS}.sdc"
cat > "${SDC_FILE}" <<EOF
current_design ${TOP}
set clk_name ${CLK_NAME}
set clk_port_name ${CLK_PORT}
set clk_period ${SDC_NS}
set clk_io_pct 0.2
set clk_port [get_ports \$clk_port_name]
create_clock -name \$clk_name -period \$clk_period \$clk_port
set non_clock_inputs [all_inputs -no_clocks]
set_input_delay  [expr \$clk_period * \$clk_io_pct] -clock \$clk_name \$non_clock_inputs
set_output_delay [expr \$clk_period * \$clk_io_pct] -clock \$clk_name [all_outputs]
EOF

AS_BYTES="${PDN_AS_BYTES:-8589934592}"
case "${DESIGN}" in
  aes|ibex) DEFAULT_CPU_S=7200 ;;
  dynamic_node) DEFAULT_CPU_S=3600 ;;
  *) DEFAULT_CPU_S=1800 ;;
esac
CPU_S="${PDN_CPU_S:-${DEFAULT_CPU_S}}"

MAKE_EXTRA=(
  DESIGN_CONFIG="./${CONFIG_REL}"
  FLOW_VARIANT="${VARIANT}"
  SDC_FILE="${SDC_FILE}"
  OPENROAD_EXE="${OPENROAD_EXE:-$(command -v openroad)}"
  OPENSTA_EXE="${OPENSTA_EXE:-$(command -v sta)}"
  YOSYS_EXE="${YOSYS_EXE:-$(command -v yosys)}"
)
if [[ -n "${SYNTH_NETLIST_FILES:-}" ]]; then
  if [[ ! -f "${SYNTH_NETLIST_FILES}" ]]; then
    echo "REFUSED: SYNTH_NETLIST_FILES=${SYNTH_NETLIST_FILES} missing" >&2
    exit 2
  fi
  MAKE_EXTRA+=( SYNTH_NETLIST_FILES="${SYNTH_NETLIST_FILES}" )
fi
if [[ "${ABC_SPEED:-}" == "1" ]]; then
  # Empty ABC_AREA= is not a TCL boolean. Force 0 so ORFS uses the speed script.
  MAKE_EXTRA+=( ABC_SPEED=1 ABC_AREA=0 )
fi
if [[ -n "${PLACE_DENSITY_LB_ADDON:-}" ]]; then
  MAKE_EXTRA+=( PLACE_DENSITY_LB_ADDON="${PLACE_DENSITY_LB_ADDON}" )
fi
if [[ -n "${SWAP_ARITH_OPERATORS:-}" ]]; then
  MAKE_EXTRA+=( SWAP_ARITH_OPERATORS="${SWAP_ARITH_OPERATORS}" )
fi
if [[ -n "${DIE_AREA:-}" && -n "${CORE_AREA:-}" ]]; then
  MAKE_EXTRA+=( DIE_AREA="${DIE_AREA}" CORE_AREA="${CORE_AREA}" CORE_UTILIZATION= )
  echo "campaign ${TARGET}: design=${DESIGN} variant=${VARIANT} locked DIE_AREA sdc=${SDC_NS}ns"
elif [[ -n "${CORE_UTILIZATION:-}" ]]; then
  MAKE_EXTRA+=( CORE_UTILIZATION="${CORE_UTILIZATION}" )
  echo "campaign ${TARGET}: design=${DESIGN} variant=${VARIANT} util=${CORE_UTILIZATION} sdc=${SDC_NS}ns"
else
  echo "campaign ${TARGET}: design=${DESIGN} variant=${VARIANT} sdc=${SDC_NS}ns (config util)"
fi

cd "${FLOW}"
exec prlimit --as="${AS_BYTES}" --cpu="${CPU_S}" \
  make \
    "${MAKE_EXTRA[@]}" \
    "${TARGET}"
