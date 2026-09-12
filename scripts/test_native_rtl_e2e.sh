#!/usr/bin/env bash
# Enterprise native RTL-to-GDS acceptance gate.
#
# This script is intentionally host-native: every tool is launched as a local
# process through the checked wrappers in tools/native/bin or a repository
# local native lab binary. It never calls Docker and never writes the protected
# FlowLab finish.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
VARIANT="${PD_FLOW_E2E_VARIANT:-enterprise-e2e}"
TIMEOUT_SECONDS="${PD_FLOW_TIMEOUT_S:-600}"
INCLUDE_LAB="${PD_FLOW_E2E_INCLUDE_LAB:-1}"
DESIGN_CONFIG="${FLOW}/designs/nangate45/gcd-tutorial/config.mk"
FLOWLAB_RES="${FLOW}/results/nangate45/gcd/flowlab"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
REPORT_DIR="${ROOT}/learn/sim/reports"
LOG="${REPORT_DIR}/native_rtl_e2e_${VARIANT}.log"
E2E_SDC_FILE="${PD_FLOW_E2E_SDC_FILE:-./designs/nangate45/gcd-tutorial/constraint.sdc}"
E2E_REBUILD="${PD_FLOW_E2E_REBUILD:-1}"
E2E_ALLOW_TIMING_FAIL="${PD_FLOW_E2E_ALLOW_TIMING_FAIL:-1}"

if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" "native-rtl-e2e-${VARIANT}" \
    bash "${BASH_SOURCE[0]}" "$@"
fi

if [[ ! "${VARIANT}" =~ ^[A-Za-z0-9_.-]{1,80}$ ]]; then
  echo "FAIL invalid E2E variant: ${VARIANT}" >&2
  exit 2
fi
if [[ "${E2E_REBUILD}" != "0" && "${E2E_REBUILD}" != "1" ]]; then
  echo "FAIL PD_FLOW_E2E_REBUILD must be 0 or 1" >&2
  exit 2
fi
if [[ "${E2E_ALLOW_TIMING_FAIL}" != "0" && "${E2E_ALLOW_TIMING_FAIL}" != "1" ]]; then
  echo "FAIL PD_FLOW_E2E_ALLOW_TIMING_FAIL must be 0 or 1" >&2
  exit 2
fi
if [[ ! "${TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "FAIL PD_FLOW_TIMEOUT_S must be a positive integer" >&2
  exit 2
fi
if [[ "${VARIANT}" == "flowlab" || "${VARIANT}" == "learn" ]]; then
  echo "FAIL E2E variant must be isolated from protected/course variants" >&2
  exit 2
fi

source "${ROOT}/scripts/native_eda_env.sh"
source "${ROOT}/learn/lib/lab_tools.sh"
lab_tools_path "${ROOT}"
cd "${ROOT}"
mkdir -p "${REPORT_DIR}"
: > "${LOG}"

exec > >(tee -a "${LOG}") 2>&1

required_tools=(openroad sta klayout yosys iverilog vvp ngspice)
for tool_name in "${required_tools[@]}"; do
  command -v "${tool_name}" >/dev/null 2>&1 || {
    echo "FAIL required native executable is unavailable: ${tool_name}"
    exit 1
  }
done
[[ -f "${DESIGN_CONFIG}" ]] || { echo "FAIL missing ${DESIGN_CONFIG}"; exit 1; }
[[ -f "${FLOWLAB_RES}/6_final.odb" ]] || {
  echo "FAIL protected FlowLab finish is missing: ${FLOWLAB_RES}/6_final.odb"
  exit 1
}

finish_hash_file="$(mktemp /tmp/pdflow-finish-hash.XXXXXX)"
trap 'rm -f "${finish_hash_file}"' EXIT
finish_files=(6_final.odb 6_final.def 6_final.gds 6_final.spef 6_final.v)
for name in "${finish_files[@]}"; do
  path="${FLOWLAB_RES}/${name}"
  [[ -f "${path}" ]] && sha256sum "${path}" >> "${finish_hash_file}"
done
[[ -s "${finish_hash_file}" ]] || { echo "FAIL no FlowLab finish hashes captured"; exit 1; }

run_stage() {
  local label="$1"
  shift
  echo
  echo "=== ${label} (timeout ${TIMEOUT_SECONDS}s) ==="
  timeout "${TIMEOUT_SECONDS}s" "$@"
}

echo "=== PDflow native RTL-to-GDS E2E ==="
echo "variant=${VARIANT} timeout=${TIMEOUT_SECONDS}s include_lab=${INCLUDE_LAB}"
echo "sdc=${E2E_SDC_FILE}"
echo "allow_timing_requirement_fail=${E2E_ALLOW_TIMING_FAIL}"
echo "openroad=$(command -v openroad)"
echo "sta=$(command -v sta)"
echo "klayout=$(command -v klayout)"
echo "yosys=$(command -v yosys)"
echo "iverilog=$(command -v iverilog)"
echo "ngspice=$(command -v ngspice)"
openroad -version | sed -n '1p'
sta -version | sed -n '1p'
klayout -v 2>&1 | sed -n '1p'
yosys -V | sed -n '1p'
iverilog -V 2>&1 | sed -n '1p'
ngspice -v 2>&1 | sed -n '1p'

make_args=(
  "DESIGN_CONFIG=${DESIGN_CONFIG#${FLOW}/}"
  "FLOW_VARIANT=${VARIANT}"
  "CORE_UTILIZATION=${PD_FLOW_E2E_CORE_UTILIZATION:-35}"
  "PLACE_DENSITY_LB_ADDON=${PD_FLOW_E2E_PLACE_DENSITY_LB_ADDON:-0.2}"
  "ABC_AREA=${PD_FLOW_E2E_ABC_AREA:-1}"
  "SDC_FILE=${E2E_SDC_FILE}"
  "TNS_END_PERCENT=${PD_FLOW_E2E_TNS_END_PERCENT:-100}"
  "OPENROAD_EXE=${OPENROAD_EXE}"
  "OPENSTA_EXE=${OPENSTA_EXE}"
  "YOSYS_EXE=${YOSYS_EXE}"
)
if [[ "${E2E_REBUILD}" == "1" ]]; then
  # The ORFS Makefile does not encode environment-variable changes such as a
  # new SDC as file dependencies. Clean only this validated, isolated E2E
  # variant so a previous run cannot be mistaken for the current invocation.
  run_stage "clean isolated E2E variant" bash -c 'cd "$1" && make "${@:2}" clean_all' bash "${FLOW}" "${make_args[@]}"
fi
run_stage "native ORFS finish from real GCD RTL" bash -c 'cd "$1" && make "${@:2}" finish' bash "${FLOW}" "${make_args[@]}"

required_outputs=(6_final.odb 6_final.def 6_final.gds 6_final.spef 6_final.v)
for name in "${required_outputs[@]}"; do
  path="${RES}/${name}"
  [[ -s "${path}" ]] || { echo "FAIL missing or empty RTL-to-GDS output: ${path}"; exit 1; }
done

export FLOW_VARIANT="${VARIANT}"
export E2E_ALLOW_TIMING_FAIL="${E2E_ALLOW_TIMING_FAIL}"
# Use the SDC copied into the exact finish checkpoint for every downstream
# timing/power action.  This prevents a report from silently using a different
# constraint than the RTL-to-GDS invocation just validated.
[[ -f "${RES}/6_final.sdc" ]] || {
  echo "FAIL missing current-run SDC: ${RES}/6_final.sdc"
  exit 1
}
export PD_FLOW_SDC_FILE="${RES}/6_final.sdc"
run_stage "RTL simulation" "${ROOT}/learn/scripts/run_rtl_sim.sh"
run_stage "gate simulation" "${ROOT}/learn/scripts/run_gate_sim.sh"
run_stage "PDN gridcheck" "${ROOT}/learn/scripts/run_gridcheck.sh" pdn
run_stage "final gridcheck" "${ROOT}/learn/scripts/run_gridcheck.sh" finish
run_stage "KLayout DRC" "${ROOT}/learn/scripts/run_drc_signoff.sh"
run_stage "KLayout LVS" "${ROOT}/learn/scripts/run_klayout_lvs.sh"
if ! run_stage "OpenSTA signoff" "${ROOT}/learn/scripts/run_sta_signoff.sh"; then
  # A real timing violation is valid evidence, not an executor failure. The
  # report must explicitly prove that OpenSTA completed and that its metrics
  # parsed before this execution gate is allowed to continue. The report
  # remains FAIL and can never become Product signoff.
  if [[ "${E2E_ALLOW_TIMING_FAIL}" == "1" ]] && python3 - "${REPORT_DIR}/sta_signoff_${VARIANT}.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    report = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)
raise SystemExit(
    0
    if report.get("execution_status") == "COMPLETED"
    and report.get("evidence_status") == "PASS"
    and report.get("requirement_status") == "FAIL"
    and report.get("ok") is False
    else 1
)
PY
  then
    echo "CONTINUE valid timing evidence with unmet requirement (Product signoff remains FAIL)"
  else
    exit 1
  fi
fi
run_stage "live System PDN / ngspice" "${ROOT}/learn/scripts/run_system_pdn.sh"
run_stage "chip PDN and transient IR" "${ROOT}/learn/scripts/run_chip_pdn_ir.sh"
# The matrix owns the single execution of equivalence, formal, extraction,
# characterization, vectorless, VYGES, and dynamic IR. Keeping it here avoids
# regenerating the same expensive reports later in the acceptance gate.
run_stage "native tool matrix" "${ROOT}/learn/scripts/run_tool_matrix.sh"
run_stage "IR-aware STA" "${ROOT}/learn/scripts/run_sta_ir_aware.sh"
run_stage "Package phase-two" "${ROOT}/learn/scripts/run_signoff_phase2.sh"

if [[ "${INCLUDE_LAB}" == "1" ]]; then
  echo
  echo "=== isolated Lab/DSE acceptance (FlowLab scope) ==="
  FLOW_VARIANT=flowlab DSE_BUDGET_S="${PD_FLOW_E2E_DSE_BUDGET_S:-45}" \
    DSE_F1_MAX="${PD_FLOW_E2E_DSE_F1_MAX:-6}" \
    run_stage "local DSE" "${ROOT}/learn/scripts/run_dse.sh"
fi

E2E_RES="${RES}" E2E_REPORT_DIR="${REPORT_DIR}" E2E_VARIANT="${VARIANT}" \
E2E_FLOWLAB_RES="${FLOWLAB_RES}" E2E_FINISH_HASH_FILE="${finish_hash_file}" \
  python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

res = Path(os.environ["E2E_RES"]).resolve()
root = Path.cwd().resolve()
reports = Path(os.environ["E2E_REPORT_DIR"])
variant = os.environ["E2E_VARIANT"]
flowlab = Path(os.environ["E2E_FLOWLAB_RES"])
hash_file = Path(os.environ["E2E_FINISH_HASH_FILE"])

try:
    res.relative_to(root)
except ValueError as exc:
    raise SystemExit(f"E2E result path escaped checkout: {res}") from exc

outputs = ["6_final.odb", "6_final.def", "6_final.gds", "6_final.spef", "6_final.v"]
for name in outputs:
    path = res / name
    if not path.is_file() or path.stat().st_size <= 0:
        raise SystemExit(f"missing or empty required output: {path}")

report_names = [
    f"gate_sim_{variant}.json",
    f"yosys_equiv_{variant}.json",
    f"formal_gcd_{variant}.json",
    f"drc_signoff_{variant}.json",
    f"lvs_signoff_{variant}.json",
    f"sta_signoff_{variant}.json",
    f"system_pdn_{variant}.json",
    f"pdn_chip_ir_{variant}.json",
    f"dynamic_ir_{variant}_direct.json",
    f"sta_ir_aware_{variant}.json",
    f"vyges_em_ir_{variant}.json",
    f"pkg_bump_{variant}.json",
    f"pkg_rdl_{variant}.json",
    f"pkg_signoff_{variant}.json",
    f"signoff_phase2_{variant}.json",
    f"tool_matrix_{variant}.json",
]
for name in report_names:
    path = reports / name
    if not path.is_file():
        raise SystemExit(f"missing required report: {path}")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid JSON report: {path}: {exc}") from exc
    if not isinstance(report, dict):
        raise SystemExit(f"report is not a JSON object: {path}")
    status = str(report.get("status") or "").upper()
    package_proxy_reports = {
        f"pkg_rdl_{variant}.json",
        f"pkg_signoff_{variant}.json",
        f"signoff_phase2_{variant}.json",
        f"pdn_chip_ir_{variant}.json",
        f"dynamic_ir_{variant}_direct.json",
        f"vyges_em_ir_{variant}.json",
    }
    if path.name in package_proxy_reports:
        if status != "PROXY" or report.get("ok") is not False:
            raise SystemExit(
                f"package evidence must be explicit PROXY/ok=false: {path}"
            )
        if report.get("product_signoff") is not False:
            raise SystemExit(f"proxy evidence cannot be Product signoff: {path}")
        if path.name in {
            f"pdn_chip_ir_{variant}.json",
            f"dynamic_ir_{variant}_direct.json",
        }:
            if report.get("evidence_status") != "PASS" or report.get("signoff_status") != "PROXY":
                raise SystemExit(f"chip/dynamic IR proxy evidence dimensions are invalid: {path}")
            if path.name.startswith("dynamic_ir_") and report.get("comparison_scope") != "same-live-invocation":
                raise SystemExit(f"Dynamic IR comparison scope is not live: {path}")
        elif path.name.endswith("vyges_em_ir_" + variant + ".json"):
            if report.get("evidence_status") != "PASS" or report.get("signoff_status") != "PROXY":
                raise SystemExit(f"Vyges proxy evidence dimensions are invalid: {path}")
    else:
        timing_requirement_fail = (
            path.name == f"sta_signoff_{variant}.json"
            and os.environ.get("E2E_ALLOW_TIMING_FAIL") == "1"
            and report.get("execution_status") == "COMPLETED"
            and report.get("evidence_status") == "PASS"
            and report.get("requirement_status") == "FAIL"
            and report.get("ok") is False
        )
        if timing_requirement_fail:
            print("timing_requirement=FAIL (valid current-run evidence; not Product signoff)")
            continue
        if report.get("ok") is not True:
            raise SystemExit(f"report did not validate as ok=true: {path}")
        if status in {"GAP", "FAIL", "PARTIAL", "PROXY", "NOT_RUN"}:
            raise SystemExit(f"required report has non-passing status {status}: {path}")

current_hashes = hash_file.read_text(encoding="utf-8").splitlines()
for line in current_hashes:
    digest, raw_path = line.split(maxsplit=1)
    path = Path(raw_path)
    current = hashlib.sha256(path.read_bytes()).hexdigest()
    if current != digest:
        raise SystemExit(f"protected FlowLab finish changed: {path}")

sta = json.loads((reports / f"sta_signoff_{variant}.json").read_text())
timing = sta.get("timing") or {}
if not isinstance(timing, dict):
    raise SystemExit("STA report has no structured timing section")
if not any(key in timing for key in ("wns", "worst_negative_slack", "tns")):
    raise SystemExit("STA report has no timing metrics")

dynamic = json.loads((reports / f"dynamic_ir_{variant}_direct.json").read_text())
if str(dynamic.get("comparison_scope")) != "same-live-invocation":
    raise SystemExit("Dynamic IR report is not same-live-invocation")
if not dynamic.get("input_artifacts") and not dynamic.get("spice"):
    raise SystemExit("Dynamic IR report has no input provenance")

print(f"NATIVE_RTL_E2E_VALIDATED variant={variant}")
print(f"validated_outputs={len(outputs)} reports={len(report_names)}")
print("protected_finish_hash=UNCHANGED")
PY

echo "NATIVE RTL-TO-GDS E2E PASSED · ${VARIANT}"
