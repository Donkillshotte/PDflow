#!/usr/bin/env bash
# PKG bump signoff: extract bump pattern from system PDN config + chip mesh SPICE
# Educational — Nangate45 GCD has no bump LEF; documents package model + mesh sources.
# Env: FLOW_VARIANT=learn|flowlab
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! "${ROOT}/scripts/resource_guard.sh"; then
  exec "${ROOT}/scripts/run_resource_job.sh" pkg-bump bash "${BASH_SOURCE[0]}" "$@"
fi
VARIANT="${FLOW_VARIANT:-flowlab}"
[[ "${VARIANT}" =~ ^[A-Za-z0-9_.-]{1,80}$ ]] || {
  echo "REFUSED: invalid package variant: ${VARIANT}" >&2
  exit 2
}
OUT="${ROOT}/learn/sim/reports/pkg_bump_${VARIANT}.json"
FLOW="${ROOT}/tools/OpenROAD-flow-scripts/flow"
RES="${FLOW}/results/nangate45/gcd/${VARIANT}"
CONFIG="${SYSTEM_PDN_CONFIG:-${ROOT}/learn/system_pdn/default.json}"
if [[ "${VARIANT}" == lab_asap7_* && -z "${SYSTEM_PDN_CONFIG:-}" ]]; then
  CONFIG="${ROOT}/learn/lab/asap7/pkg/asap7_system_pdn.json"
  RES="${FLOW}/results/asap7/gcd/${VARIANT}"
fi

# Chip PDN and Dynamic IR keep their current-run meshes in the generated
# workspace. Prefer those paths so package evidence cannot silently consume
# an older result-directory mesh with the same variant name. The result-tree
# and learn/sim paths remain compatibility fallbacks for older invocations.
WORK_HOME="${PD_FLOW_WORK_HOME:-}"
if [[ -n "${WORK_HOME}" ]]; then
  RUN_ID="${PD_FLOW_CANDIDATE_RUN_ID:-}"
  [[ "${RUN_ID}" =~ ^[A-Za-z0-9_.-]{8,100}$ ]] || {
    echo "FAIL invalid FlowLab candidate run id" >&2
    exit 1
  }
  EXPECTED_WORK_HOME="${ROOT}/.pdflow/runs/${RUN_ID}/candidate/orfs"
  [[ "${WORK_HOME}" == "${EXPECTED_WORK_HOME}" && "${VARIANT}" == "flowlab" ]] || {
    echo "FAIL candidate workspace is outside the requested run" >&2
    exit 1
  }
  GENERATED_DEFAULT="${WORK_HOME}/generated/chip_pdn_ir/finish"
else
  GENERATED_DEFAULT="${ROOT}/.pdflow/generated/${VARIANT}/finish/chip_pdn_ir"
fi
GENERATED_ROOT="${PD_FLOW_GENERATED_ROOT:-${GENERATED_DEFAULT}}"
GENERATED_ROOT="$(realpath -m -- "${GENERATED_ROOT}")"
case "${GENERATED_ROOT}" in
  "${ROOT}/.pdflow/"*|"${ROOT}/.pdflow"|"${WORK_HOME:-__no_candidate__}/generated/"*) ;;
  *)
    echo "REFUSED: generated package workspace must remain repository/candidate scoped: ${GENERATED_ROOT}" >&2
    exit 2
    ;;
esac

MESH=""
for candidate in \
  "${GENERATED_ROOT}/mesh/pg_vdd_bumps.sp" \
  "${GENERATED_ROOT}/mesh/pg_vdd.sp" \
  "${ROOT}/.pdflow/generated/${VARIANT}/finish/dynamic_ir/mesh/pg_vdd_bumps.sp" \
  "${RES}/pdn/pg_vdd_bumps.sp" \
  "${RES}/pdn/pg_vdd.sp" \
  "${ROOT}/learn/sim/spice/pg_vdd_bumps_${VARIANT}.sp"; do
  if [[ -f "${candidate}" ]]; then
    MESH="${candidate}"
    break
  fi
done

mkdir -p "$(dirname "${OUT}")"

ROOT_PATH="${ROOT}" VARIANT_NAME="${VARIANT}" CONFIG_PATH="${CONFIG}" MESH_PATH="${MESH}" OUT_PATH="${OUT}" \
python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT_PATH"])
variant = os.environ["VARIANT_NAME"]
config_path = Path(os.environ["CONFIG_PATH"])
config = json.loads(config_path.read_text())
pkg = config.get("package", {})
mesh = Path(os.environ["MESH_PATH"]) if os.environ.get("MESH_PATH") else None

v_sources = 0
r_count = 0
if mesh is not None and mesh.exists():
    text = mesh.read_text()
    v_sources = sum(1 for line in text.splitlines() if line.strip().startswith("V"))
    r_count = sum(1 for line in text.splitlines() if line.strip().startswith("R"))

n_bumps_cfg = int(pkg.get("n_bumps", 0))
mesh_exists = bool(mesh is not None and mesh.is_file())
ok = n_bumps_cfg > 0 and mesh_exists and v_sources > 0 and r_count > 0

out = {
  "kind": "pkg_bump",
  "variant": variant,
  "schema_version": 2,
  "package": {
    "n_bumps": n_bumps_cfg,
    "r_bump": pkg.get("r_bump"),
    "l_bump": pkg.get("l_bump"),
    "r_pkg": pkg.get("r_pkg"),
    "l_pkg": pkg.get("l_pkg"),
  },
  "mesh": {
    "path": str(mesh) if mesh_exists else None,
    "v_sources": v_sources,
    "r_elements": r_count,
  },
  "inputs": {
    "package_config": str(config_path),
    "mesh_source": "current-run generated workspace" if mesh and ".pdflow" in str(mesh) else "compatibility result path",
  },
  "evaluation": {
    "checks": [
      {
        "id": "n_bumps",
        "label": "Package bump count (config)",
        "actual": n_bumps_cfg,
        "target": 1,
        "ok": n_bumps_cfg >= 1,
      },
      {
        "id": "mesh_spice",
        "label": "Chip mesh SPICE (write_pg_spice)",
        "actual": mesh_exists,
        "target": True,
        "ok": mesh_exists and v_sources > 0 and r_count > 0,
        "note": "Run chip_pdn_ir after finish if the current-run mesh is missing",
      },
    ],
    "ok": ok,
  },
  "ok": ok,
  "educational_note": "GCD has synthetic BUMPS pattern (PSM-0073), not tapeout bump LEF",
  "summary": f"Bumps {n_bumps_cfg} · mesh V={v_sources} R={r_count}",
}
out_path = Path(os.environ["OUT_PATH"])
temporary = out_path.with_name(f".{out_path.name}.{os.getpid()}.tmp")
temporary.write_text(json.dumps(out, indent=2) + "\n")
os.replace(temporary, out_path)
print("PKG_BUMP_JSON", out_path)
print(out["summary"])
PY

echo "PKG_BUMP_DONE ${VARIANT}"
python3 "${ROOT}/learn/scripts/signoff_require_ok.py" "${OUT}"
