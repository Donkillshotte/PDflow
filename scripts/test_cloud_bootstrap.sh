#!/usr/bin/env bash
# Static checks for the Cloud Agent core bootstrap. No ORFS, no AES, no IR.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAIL=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; FAIL=1; }

echo "== environment.json =="
python3 - <<PY || { bad "environment.json invalid"; exit 1; }
import json
from pathlib import Path
p = Path("${ROOT}/.cursor/environment.json")
d = json.loads(p.read_text())
install = d.get("install") or ""
assert "PD_FLOW_PROFILE=core" in install, install
assert "EDA_JOBS=2" in install, install
assert "cloud_agent_install.sh" in install
assert d.get("terminals")
print("environment.json core install ok")
PY
ok "environment.json core + EDA_JOBS=2"

echo "== install script syntax / profile =="
bash -n "${ROOT}/scripts/cloud_agent_install.sh" && ok "install syntax" || bad "install syntax"
bash -n "${ROOT}/scripts/cloud_agent_smoke.sh" && ok "smoke syntax" || bad "smoke syntax"
bash -n "${ROOT}/scripts/lib/jobs.sh" && ok "jobs.sh syntax" || bad "jobs.sh"
bash -n "${ROOT}/scripts/02_install_opensta.sh" && ok "02 syntax" || bad "02"
bash -n "${ROOT}/scripts/04_setup_orfs.sh" && ok "04 syntax" || bad "04"
rg -q 'PD_FLOW_PROFILE:-core' "${ROOT}/scripts/cloud_agent_install.sh" && ok "default core" || bad "no core default"
rg -q 'EDA_JOBS' "${ROOT}/scripts/04_setup_orfs.sh" && ok "yosys uses EDA_JOBS" || bad "yosys still nproc"
rg -q 'EDA_JOBS' "${ROOT}/scripts/02_install_opensta.sh" && ok "opensta uses EDA_JOBS" || bad "opensta still nproc"
rg -q 'nproc' "${ROOT}/scripts/04_setup_orfs.sh" && bad "04 still nproc" || ok "04 no nproc"
rg -q 'nproc' "${ROOT}/learn/scripts/build_dpn_engine.sh" && bad "dpn still nproc" || ok "dpn uses EDA_JOBS"

echo "== install must not run heavy work =="
if rg -n 'run_aes_f4|run_aes_slice|run_dse\.py|run_dynamic_ir|run_gcd_flow|test_course|test_all_phases|pdn_dynamic' \
  "${ROOT}/scripts/cloud_agent_install.sh"; then
  bad "install still invokes heavy analysis"
else
  ok "install has no AES/DSE/IR/GDS invocations"
fi
rg -q 'Nessun flow OpenROAD' "${ROOT}/scripts/cloud_agent_install.sh" && ok "install documents no-flow" || bad "missing no-flow note"

echo "== environment.json has no RAM knobs =="
python3 - <<PY || { bad "environment.json RAM fields"; exit 1; }
import json
from pathlib import Path
p = Path("${ROOT}/.cursor/environment.json")
d = json.loads(p.read_text())
for k in ("memory", "ram", "cpus", "cpu", "resources", "vmSize"):
    assert k not in d, k
print("environment.json has no memory/cpu fields (schema would reject them)")
PY
ok "environment.json cannot raise VM RAM"

echo "== timeout / RSS guards =="
python3 "${ROOT}/learn/scripts/test_heavy_analysis.py" && ok "test_heavy_analysis" || bad "test_heavy_analysis"
python3 - <<PY || { bad "timeout helper"; exit 1; }
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path("${ROOT}") / "learn" / "scripts"))
from heavy_analysis import resolve_solve_timeout_s
os.environ["PDN_SOLVE_TIMEOUT_S"] = "1800"
assert resolve_solve_timeout_s(90) == 1800.0
print("PDN_SOLVE_TIMEOUT_S=1800 overrides 90")
PY
ok "PDN_SOLVE_TIMEOUT_S override"

echo "== heavy guards =="
rg -q 'require_heavy' "${ROOT}/learn/scripts/run_aes_f4.py" && ok "aes F4 guarded" || bad "aes F4 unguarded"
rg -q 'require_heavy' "${ROOT}/learn/scripts/run_aes_slice.py" && ok "aes slice guarded" || bad "aes slice unguarded"
rg -q 'check_large_mesh' "${ROOT}/learn/scripts/pdn_dynamic.py" && ok "pdn_dynamic mesh guard" || bad "pdn_dynamic unguarded"
rg -q 'check_rss_budget' "${ROOT}/learn/scripts/dse_f4_worker.py" && ok "f4 worker RSS budget" || bad "f4 worker no RSS budget"
rg -q 'check_large_mesh' "${ROOT}/learn/scripts/dse_f4_worker.py" && ok "f4 worker mesh guard" || bad "f4 worker unguarded"
bash -n "${ROOT}/scripts/run_aes_f4_cloud.sh" && ok "aes F4 cloud wrapper syntax" || bad "aes F4 cloud wrapper syntax"
rg -q 'prlimit' "${ROOT}/scripts/run_aes_f4_cloud.sh" && ok "aes F4 cloud caps RSS" || bad "aes F4 cloud no prlimit"
rg -q 'run_aes_f4_cloud' "${ROOT}/scripts/cloud_agent_install.sh" && bad "install invokes aes F4 cloud" || ok "install does not run aes F4 cloud"

if [[ "${FAIL}" -ne 0 ]]; then
  echo "CLOUD_BOOTSTRAP_TEST_FAIL"
  exit 1
fi
echo "CLOUD_BOOTSTRAP_TEST_OK"
exit 0
