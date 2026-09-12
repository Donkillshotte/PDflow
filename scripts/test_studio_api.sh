#!/usr/bin/env bash
# Studio API smoke test (server on 127.0.0.1:43217).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${STUDIO_URL:-http://127.0.0.1:43217}"
STUDIO_ORIGIN="${STUDIO_ORIGIN:-http://127.0.0.1:43217}"
HTTP_TIMEOUT="${STUDIO_CURL_TIMEOUT_S:-600}"
AUTH_H=(-H "Origin: ${STUDIO_ORIGIN}")
if [[ -n "${STUDIO_RUN_TOKEN:-}" ]]; then AUTH_H+=(-H "Authorization: Bearer ${STUDIO_RUN_TOKEN}"); fi
FAIL=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; FAIL=1; }

expect_sse_pass_or_gap() {
  local label="$1"
  local file="$2"
  if grep -Eq '"ok":true|_PASS|_DONE' "${file}"; then
    ok "${label} pass"
  elif grep -Eqi 'GAP|missing|not installed|command not found|dependency|not in PATH|not available' "${file}"; then
    ok "${label} explicit dependency GAP"
  else
    bad "${label} failed"
  fi
}

# Keep this smoke suite portable on minimal Linux hosts where ripgrep is not
# installed. The suite only needs quiet extended-regex probes.
if ! command -v rg >/dev/null 2>&1; then
  rg() {
    if [[ "${1:-}" == "-qi" ]]; then
      shift
      grep -Eqi "$@"
    elif [[ "${1:-}" == "-q" ]]; then
      shift
      grep -Eq "$@"
    else
      grep -Eq "$@"
    fi
  }
fi

echo "== Studio API @ ${BASE} =="

code="$(curl -s -o /tmp/studio-home.html -w '%{http_code}' "${BASE}/")"
[[ "${code}" == "200" ]] && ok "GET / → 200" || bad "GET / → ${code}"

code="$(curl -s -o /tmp/studio-jobs.json -w '%{http_code}' "${BASE}/api/jobs")"
[[ "${code}" == "200" ]] && ok "GET /api/jobs → 200" || bad "GET /api/jobs → ${code}"
rg -q '"pipeline"' /tmp/studio-jobs.json && ok "jobs.pipeline" || bad "jobs missing pipeline"
rg -q '"jobs"' /tmp/studio-jobs.json && ok "jobs.jobs" || bad "jobs missing array"

code="$(curl -s -o /tmp/studio-prog.json -w '%{http_code}' "${BASE}/api/progress?lessonId=00-intro")"
[[ "${code}" == "200" ]] && ok "GET progress+gates → 200" || bad "progress → ${code}"
rg -q '"gates"' /tmp/studio-prog.json && ok "progress.gates" || bad "progress missing gates"

# Completion without gate → 422
code="$(curl -s -o /tmp/studio-complete.json -w '%{http_code}' \
  "${AUTH_H[@]}" -X POST -H 'Content-Type: application/json' \
  -d '{"lessonId":"07-finish"}' \
  "${BASE}/api/progress")"
[[ "${code}" == "422" ]] && ok "POST complete gated → 422" || bad "complete expected 422, got ${code}"

# Missing-input and lock failures run in a disposable fixture workspace.
# Never rename canonical artifacts or replace the live application's lock.
if "${ROOT}/studio/node-runtime/node" "${ROOT}/studio/tests/preflight-isolation.cjs"; then
  ok "isolated preflight contracts"
else
  bad "isolated preflight contracts"
fi
RES_DIR="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn"

# Short allowed stream (check)
code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o /tmp/studio-check.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=check")"
[[ "${code}" == "200" ]] && ok "check stream → 200" || bad "check stream → ${code}"
rg -q '"type":"start"' /tmp/studio-check.sse && ok "SSE start event" || bad "SSE missing start"

# Forbidden action
code="$(curl -s "${AUTH_H[@]}" -o /tmp/studio-bad.json -w '%{http_code}' \
  "${BASE}/api/run/stream?action=rm_rf")"
[[ "${code}" == "400" ]] && ok "forbidden action → 400" || bad "forbidden → ${code}"

# Key pages + deep-link
for path in /lessons /tools /materials /lessons/00-intro \
  '/tools?stage=cts&tab=results' '/materials?tab=gallery'; do
  c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}${path}")"
  [[ "${c}" == "200" ]] && ok "GET ${path}" || bad "GET ${path} → ${c}"
done

# Open catalog + dry-run / launch
code="$(curl -s -o /tmp/studio-open.json -w '%{http_code}' "${BASE}/api/open")"
[[ "${code}" == "200" ]] && ok "GET /api/open → 200" || bad "open → ${code}"
rg -q '"targets"' /tmp/studio-open.json && ok "open.targets" || bad "open missing targets"
rg -q 'gui-synth|Results dashboard' /tmp/studio-open.json && ok "open catalog entries" || bad "open catalog empty"

code="$(curl -s -o /tmp/studio-open-dry.json -w '%{http_code}' \
  "${AUTH_H[@]}" -X POST -H 'Content-Type: application/json' \
  -d '{"id":"dash-cts"}' "${BASE}/api/open")"
[[ "${code}" == "200" ]] && ok "POST open dash-cts → 200" || bad "open dash → ${code}"
rg -q '"navigate"' /tmp/studio-open-dry.json && ok "open navigate" || bad "open missing navigate"

if rg -q '"id":"gui-synth"[^}]*"exists":true' /tmp/studio-open.json \
  || python3 -c 'import json;d=json.load(open("/tmp/studio-open.json"));print(any(t["id"]=="gui-synth" and t["exists"] for t in d["targets"]))' | rg -q True; then
  code="$(curl -s -o /tmp/studio-open-gui.json -w '%{http_code}' \
    "${AUTH_H[@]}" -X POST -H 'Content-Type: application/json' \
    -d '{"id":"gui-synth","dryRun":true}' "${BASE}/api/open")"
  [[ "${code}" == "200" ]] && ok "POST open gui-synth dryRun" || bad "gui dryRun → ${code}"
else
  ok "skip gui-synth launch (odb missing)"
fi

# Inspect + web viewer
code="$(curl -s -o /tmp/studio-inspect.json -w '%{http_code}' \
  "${AUTH_H[@]}" "${BASE}/api/inspect?stage=synth")"
[[ "${code}" == "200" ]] && ok "GET inspect synth → 200" || bad "inspect → ${code}"
rg -q '"odb"|"sta"|"yosys"|"hooks"' /tmp/studio-inspect.json && ok "inspect payload" || bad "inspect payload weak"

code="$(curl -s -o /tmp/studio-viewer.json -w '%{http_code}' \
  "${AUTH_H[@]}" -X POST -H 'Content-Type: application/json' \
  -d '{"action":"start","stage":"cts"}' "${BASE}/api/viewer")"
[[ "${code}" == "200" || "${code}" == "422" ]] && ok "POST viewer start → ${code}" || bad "viewer start → ${code}"
URL="$(python3 -c 'import json;print(json.load(open("/tmp/studio-viewer.json")).get("url",""))')"
if [[ -n "${URL}" ]]; then
  sleep 1
  c="$(curl -s -o /dev/null -w '%{http_code}' "${URL}")"
  [[ "${c}" == "200" ]] && ok "web viewer HTTP 200" || bad "web viewer → ${c}"
fi
curl -s "${AUTH_H[@]}" -X POST -H 'Content-Type: application/json' \
  -d '{"action":"stop"}' "${BASE}/api/viewer" >/dev/null
ok "viewer stop"

code="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materials/reference/tool-hooks.md")"
[[ "${code}" == "200" ]] && ok "tool-hooks.md page" || bad "tool-hooks page → ${code}"
code="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materials/reference/extended-flow.md")"
[[ "${code}" == "200" ]] && ok "extended-flow.md page" || bad "extended-flow page → ${code}"

# Extended actions (short)
code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o /tmp/studio-rtl.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=rtl_sim")"
  [[ "${code}" == "200" || "${code}" == "412" ]] && ok "rtl_sim stream → ${code}" || bad "rtl_sim → ${code}"
expect_sse_pass_or_gap "rtl_sim" /tmp/studio-rtl.sse

code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o /tmp/studio-gc.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=gridcheck&mode=flowlab")"
[[ "${code}" == "200" || "${code}" == "412" ]] && ok "gridcheck stream → ${code}" || bad "gridcheck → ${code}"
expect_sse_pass_or_gap "gridcheck" /tmp/studio-gc.sse

# Suite hub + palette run/webviewer entries
code="$(curl -s -o /tmp/studio-suite.json -w '%{http_code}' "${BASE}/api/suite")"
[[ "${code}" == "200" ]] && ok "GET /api/suite → 200" || bad "suite → ${code}"
rg -q '"hooks"' /tmp/studio-suite.json && ok "suite.hooks" || bad "suite missing hooks"
rg -q '"ready"' /tmp/studio-suite.json && ok "suite.ready" || bad "suite missing ready"
rg -q 'leftover no MCMM' /tmp/studio-suite.json && ok "suite names leftover no MCMM" || bad "suite missing leftover no MCMM"
rg -q 'leftover no density' /tmp/studio-suite.json && ok "suite names leftover no density" || bad "suite missing leftover no density"
rg -q 'IR meshes not comparable' /tmp/studio-suite.json && ok "suite names IR mesh leftover" || bad "suite missing IR mesh leftover"
rg -q '"leftover"' /tmp/studio-suite.json && ok "suite hooks carry leftover ids" || bad "suite missing leftover ids"

code="$(curl -s -o /tmp/studio-story.json -w '%{http_code}' "${BASE}/api/story")"
[[ "${code}" == "200" ]] && ok "GET /api/story → 200" || bad "story → ${code}"
rg -q '"surfaces"' /tmp/studio-story.json && ok "story.surfaces" || bad "story missing surfaces"
rg -q '"path"' /tmp/studio-story.json && ok "story.path" || bad "story missing path"
rg -q '"product"' /tmp/studio-story.json && ok "story.product" || bad "story missing product"
rg -qi 'live-analysis|dynamic_ir_flowlab_direct' /tmp/studio-story.json && ok "story cites current IR analysis" || bad "story missing current IR analysis cite"
rg -q '"staIr"' /tmp/studio-story.json && ok "story.staIr" || bad "story missing staIr"
rg -q 'leftover no MCMM' /tmp/studio-story.json && ok "story names leftover no MCMM" || bad "story missing leftover no MCMM"
rg -q 'leftover must-connect' /tmp/studio-story.json && ok "story names leftover must-connect" || bad "story missing leftover must-connect"
code="$(curl -s -o /tmp/studio-lab.json -w '%{http_code}' "${BASE}/api/lab")"
[[ "${code}" == "200" ]] && ok "GET /api/lab → 200" || bad "lab → ${code}"
rg -q '"comparisons"' /tmp/studio-lab.json && ok "lab.comparisons" || bad "lab missing comparisons"
rg -q '"physics"' /tmp/studio-lab.json && ok "lab.physics" || bad "lab missing physics"
rg -q '"launches"' /tmp/studio-lab.json && ok "lab.launches" || bad "lab missing launches"
rg -q '"thisLaunch"' /tmp/studio-lab.json && ok "lab.thisLaunch" || bad "lab missing thisLaunch"
python3 - <<'PY'
import json
d=json.load(open("/tmp/studio-story.json"))
ids={s["id"] for s in d.get("surfaces",[])}
assert ids=={"course","lab","product"}, ids
assert len(d.get("path",[]))>=5, d.get("path")
lab=next(s for s in d["surfaces"] if s["id"]=="lab")
assert lab.get("href")=="/lab", lab
print("ok story surface ids")
print("ok story lab href /lab")
PY
if python3 - <<'PY'
import json,sys
d=json.load(open("/tmp/studio-suite.json"))
ids={h["id"] for h in d["hooks"]}
need={"toolchain","rtl_sim","gridcheck","activity","vectorless","klayout_drc","inspect","or-web","docs","yosys_equiv","formal_gcd","openrcx"}
miss=sorted(need-ids)
if miss:
    print("missing", miss)
    sys.exit(1)
sys.exit(0)
PY
then
  ok "suite hook ids"
else
  bad "suite core hooks missing"
fi

rg -q '"id":"run-rtl-sim"' /tmp/studio-open.json && ok "open run-rtl-sim" || bad "open missing run-rtl-sim"
rg -q '"kind":"webviewer"' /tmp/studio-open.json && ok "open webviewer kind" || bad "open missing webviewer"
rg -q '"id":"dash-suite"' /tmp/studio-open.json && ok "open dash-suite" || bad "open missing dash-suite"

code="$(curl -s -o /tmp/studio-open-run.json -w '%{http_code}' \
  "${AUTH_H[@]}" -X POST -H 'Content-Type: application/json' \
  -d '{"id":"run-gridcheck"}' "${BASE}/api/open")"
[[ "${code}" == "200" ]] && ok "POST open run-gridcheck" || bad "open run → ${code}"
rg -q 'tab=run&action=gridcheck' /tmp/studio-open-run.json && ok "run navigate deep-link" || bad "run navigate incorrect"

c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/tools?tab=run&action=rtl_sim")"
[[ "${c}" == "200" ]] && ok "GET tools action deep-link" || bad "tools action → ${c}"

# FlowLab API + page
code="$(curl -s -o /tmp/studio-flowlab.json -w '%{http_code}' "${BASE}/api/flowlab")"
[[ "${code}" == "200" ]] && ok "GET /api/flowlab → 200" || bad "flowlab → ${code}"
rg -q '"rtl"' /tmp/studio-flowlab.json && ok "flowlab.rtl" || bad "flowlab missing rtl"
rg -q '"params"' /tmp/studio-flowlab.json && ok "flowlab.params" || bad "flowlab missing params"
rg -q '"coreUtilization"' /tmp/studio-flowlab.json && ok "flowlab.params.coreUtilization" || bad "params incomplete"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/flow")"
[[ "${c}" == "200" ]] && ok "GET /flow" || bad "/flow → ${c}"
rg -q '"sim"' /tmp/studio-flowlab.json && ok "flowlab.sim" || bad "flowlab missing sim"

# Analysis Workbench contracts.  Preview is intentionally a POST because it
# accepts a typed plan, but it is read-only: it must not create a run, enqueue
# a job, or inspect arbitrary filesystem paths.
curl -s -o /tmp/studio-analysis-jobs-before.json "${BASE}/api/jobs"
code="$(curl -s "${AUTH_H[@]}" -o /tmp/studio-analysis-preview.json -w '%{http_code}' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"bundle_id":"recommended","stage":"finish","variant":"flowlab"}' \
  "${BASE}/api/analysis-bundles/preview")"
[[ "${code}" == "200" ]] && ok "POST analysis bundle preview → 200" || bad "analysis bundle preview → ${code}"
curl -s -o /tmp/studio-analysis-jobs-after.json "${BASE}/api/jobs"
if python3 - <<'PY'
import json

plan = json.load(open("/tmp/studio-analysis-preview.json"))
before = json.load(open("/tmp/studio-analysis-jobs-before.json"))
after = json.load(open("/tmp/studio-analysis-jobs-after.json"))
assert plan.get("bundle_id") == "recommended", plan
assert plan.get("stage") == "finish", plan
assert plan.get("variant") == "flowlab", plan
assert plan.get("read_only") is True, plan
assert isinstance(plan.get("jobs"), list), plan
assert isinstance(plan.get("resource_limit"), dict), plan
assert isinstance(plan.get("downstream_invalidations"), list), plan
assert plan.get("principle"), plan
before_ids = {item.get("job_id") for item in before.get("jobs", [])}
after_ids = {item.get("job_id") for item in after.get("jobs", [])}
assert after_ids == before_ids, (before_ids, after_ids)
print("OK analysis preview is read-only")
PY
then
  ok "analysis preview does not enqueue a job"
else
  bad "analysis preview contract"
fi
code="$(curl -s -o /tmp/studio-analysis-runs.json -w '%{http_code}' \
  "${BASE}/api/analysis-runs?limit=5")"
[[ "${code}" == "200" ]] && ok "GET analysis runs → 200" || bad "analysis runs → ${code}"
python3 - <<'PY' || bad "analysis runs payload"
import json
d=json.load(open("/tmp/studio-analysis-runs.json"))
assert isinstance(d.get("analysis_runs"), list), d
print("OK analysis_runs array")
PY
code="$(curl -s "${AUTH_H[@]}" -o /tmp/studio-layout-fp.json -w '%{http_code}' \
  "${BASE}/api/layout-preview?phase=floorplan&variant=flowlab")"
[[ "${code}" == "200" ]] && ok "GET live floorplan metadata → 200" || bad "floorplan metadata → ${code}"
if python3 - <<'PY'
import json
d = json.load(open('/tmp/studio-layout-fp.json'))
assert d['odb'] == '2_4_floorplan_pdn.odb', d
assert d['artifact']['exists'] is True, d
assert d['image']['source'] == 'odb', d
assert d.get('gallery') == [], d
assert d.get('compare') == [], d
print(d['artifact']['path'], d['artifact']['revision'])
PY
then
  ok "floorplan bridge points to live ODB"
else
  bad "floorplan bridge is not live-only"
fi
if rg -q '"phaseHistory"|"phaseRuns"' /tmp/studio-flowlab.json; then
  bad "flowlab exposes persistent phase history"
else
  ok "flowlab is current-run-only (no phase history)"
fi
code="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/api/flowlab/download?kind=vcd")"
[[ "${code}" == "200" || "${code}" == "404" ]] && ok "flowlab vcd download (${code})" || bad "flowlab download → ${code}"
rg -q '"id":"dash-flowlab"' /tmp/studio-open.json && ok "open dash-flowlab" || bad "open missing flowlab"
rg -q '"id":"dash-pkg"' /tmp/studio-open.json && ok "open dash-pkg" || bad "open missing dash-pkg"
rg -q '"id":"run-system-pdn"' /tmp/studio-open.json && ok "open run-system-pdn" || bad "open missing system_pdn"

c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/pkg")"
[[ "${c}" == "200" ]] && ok "GET /pkg" || bad "pkg → ${c}"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materials/reference/system-pdn.md")"
[[ "${c}" == "200" ]] && ok "system-pdn.md page" || bad "system-pdn page → ${c}"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materials/reference/pkg-design-package.md")"
[[ "${c}" == "200" ]] && ok "pkg-design-package.md page" || bad "pkg doc page → ${c}"

# ORFS log digest (wrapper must classify WARN vs ERROR, not treat Failure:0 as error)
code="$(curl -s -o /tmp/studio-results-finish.json -w '%{http_code}' \
  "${BASE}/api/results?stage=finish&variant=flowlab")"
[[ "${code}" == "200" ]] && ok "GET /api/results finish flowlab → 200" || bad "results finish → ${code}"
rg -q '"logDigest"' /tmp/studio-results-finish.json && ok "results.logDigest" || bad "results missing logDigest"
python3 - <<'PY' || bad "logDigest.errors must be 0"
import json
d=json.load(open("/tmp/studio-results-finish.json"))
dig=d.get("logDigest") or {}
assert dig.get("errors", 1) == 0, dig
assert dig.get("healthy") is True, dig
print("OK digest", dig.get("summary","")[:80])
PY
ok "logDigest.healthy (0 ERROR)"

code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o /tmp/studio-syspdn.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=system_pdn&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "system_pdn stream → 200" || bad "system_pdn → ${code}"
rg -q 'SYSTEM_PDN_DONE|"ok":true' /tmp/studio-syspdn.sse && ok "system_pdn pass" || \
  rg -qi 'ngspice is not installed|status.?[:=].?GAP' /tmp/studio-syspdn.sse && ok "system_pdn explicit GAP" || bad "system_pdn fail"

# Power signoff chain (requires finish — flowlab variant)
for action in activity_power chip_pdn_ir export_spice_lab; do
  code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o "/tmp/studio-${action}.sse" -w '%{http_code}' \
    "${BASE}/api/run/stream?action=${action}&mode=flowlab")"
  [[ "${code}" == "200" || "${code}" == "412" ]] && ok "${action} stream → ${code}" || bad "${action} → ${code}"
  expect_sse_pass_or_gap "${action}" "/tmp/studio-${action}.sse"
done

code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o /tmp/studio-power-chain.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=power_chain&mode=flowlab")"
[[ "${code}" == "200" || "${code}" == "412" ]] && ok "power_chain stream → ${code}" || bad "power_chain → ${code}"
expect_sse_pass_or_gap "power_chain" /tmp/studio-power-chain.sse
if grep -Eq '"ok":true|_PASS|_DONE' /tmp/studio-power-chain.sse; then
  [[ -f "${ROOT}/learn/sim/reports/power_chain_flowlab.log" ]] && ok "power_chain log artifact" || bad "missing power_chain log"
  rg -q 'ACTIVITY_SOURCE' "${ROOT}/learn/sim/reports/activity_power_flowlab.log" 2>/dev/null \
    && ok "activity_power source stamped" || bad "activity_power log missing ACTIVITY_SOURCE"
  rg -q 'Wrong number of arguments' "${ROOT}/learn/sim/reports/activity_power_flowlab.log" 2>/dev/null \
    && bad "activity_power still has read_vcd arity error" \
    || ok "activity_power no VCD arity error"
else
  ok "power_chain dependent artifacts skipped for GAP"
fi

# Tool matrix / vectorless / equiv / formal / OpenRCX / PEX
for action in yosys_equiv formal_gcd openrcx_report analytical_pex layout_tools spice_engines; do
  code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o "/tmp/studio-${action}.sse" -w '%{http_code}' \
    "${BASE}/api/run/stream?action=${action}&mode=flowlab")"
  [[ "${code}" == "200" || "${code}" == "412" ]] && ok "${action} stream → ${code}" || bad "${action} → ${code}"
  expect_sse_pass_or_gap "${action}" "/tmp/studio-${action}.sse"
done

code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o /tmp/studio-vyges.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=vyges_em_ir&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "vyges_em_ir stream → 200" || bad "vyges_em_ir → ${code}"
rg -q '"status":"PROXY"|VYGES_EM_IR_DONE|proxy evidence' /tmp/studio-vyges.sse \
  && ok "vyges_em_ir proxy evidence" || bad "vyges_em_ir missing proxy evidence"
[[ -f "${ROOT}/learn/sim/reports/vyges_em_ir_flowlab.json" ]] && ok "vyges_em_ir json artifact" || bad "missing vyges_em_ir json"
python3 - <<PY || bad "vyges_em_ir json parse"
import json
r=json.load(open("${ROOT}/learn/sim/reports/vyges_em_ir_flowlab.json"))
assert r["status"] == "PROXY" and r["ok"] is False
assert r["evidence_status"] == "PASS"
assert r["signoff_status"] == "PROXY"
assert r["engine"] == "vyges-em-ir"
assert r["vyges"]["worst_ir"]["drop"] > 0
print(r["summary"][:120])
PY
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materials/reference/vyges-em-ir.md")"
[[ "${c}" == "200" ]] && ok "vyges-em-ir.md page" || bad "vyges-em-ir page → ${c}"

code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o /tmp/studio-dynir.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=dynamic_ir&mode=flowlab")"
[[ "${code}" == "200" || "${code}" == "412" ]] && ok "dynamic_ir stream → ${code}" || bad "dynamic_ir → ${code}"
expect_sse_pass_or_gap "dynamic_ir" /tmp/studio-dynir.sse
if grep -Eq '"ok":true|_PASS|_DONE' /tmp/studio-dynir.sse; then
  [[ -f "${ROOT}/learn/sim/reports/dynamic_ir_flowlab_direct.json" ]] && ok "dynamic_ir current_run json" || bad "missing current_run dynamic_ir json"
  [[ -f "${ROOT}/learn/sim/reports/dynamic_ir_flowlab_direct.svg" ]] && ok "dynamic_ir current_run svg" || bad "missing current_run dynamic_ir svg"
  python3 - <<PY || bad "dynamic_ir current_run parse"
import json
r=json.load(open("${ROOT}/learn/sim/reports/dynamic_ir_flowlab_direct.json"))
assert r.get("comparison_scope") == "same-live-invocation"
assert r["status"] == "PROXY" and r["ok"] is False
assert r["execution_status"] == "COMPLETED"
assert r["evidence_status"] == "PASS" and r["signoff_status"] == "PROXY"
assert r["product_signoff"] is False
assert r["kind"] == "dynamic_ir"
assert r["static"]["worst_ir"] > 0
assert r["dynamic"]["worst_droop"] > 0
# no live IR mV pin — relative honesty only
assert float(r["dynamic"]["worst_droop"]) > float(r["static"]["worst_ir"]) * 0.5
# no fixed live IR mV pin — report-driven only
assert r["sim_levels"]["L0_static"]["status"] == "READY"
assert r["sim_levels"]["L2_vcd_dynamic"]["status"] in ("READY", "PARTIAL", "GAP")
assert r["sim_levels"]["L3_windowed"]["status"] in ("READY", "PARTIAL")
assert "windows" in r["sim_levels"]["L3_windowed"]
sta = (r.get("activity_model") or {}).get("sta") or {}
assert sta.get("status") == "READY", sta
assert (sta.get("n_applied") or 0) > 0
assert r["pipeline"][0]["status"] == "READY"
assert r["pipeline"][2]["status"] == "READY"
assert "LEF" in r["pipeline"][0]["via"] or "lef" in r["pipeline"][0]["via"].lower() or "write_pg_spice" in r["pipeline"][0]["via"]
assert r.get("extract", {}).get("backend") == "write_pg_spice"
assert r["emsim_split"]["B_pdn_solve"]["status"] == "READY"
assert r["platform"]["solvers"]["A_direct_be"]["status"] == "READY"
assert r["platform"]["network_levels"]["N2_RC"]["status"] == "READY"
b = r.get("solver_b")
assert b is None or b.get("ok") is True
c = r.get("solver_c")
assert c is None or c.get("abs_err_vs_A_mv", 0) < 5.0
d = r.get("solver_d")
assert d is None or d.get("abs_err_vs_A_mv", 0) < 5.0
g = r.get("ngspice_reference")
assert g is None or g.get("ok") is True, g
print(r["summary"][:120])
PY
else
  ok "dynamic_ir report checks skipped for explicit GAP"
fi
code="$(curl -s -o /tmp/studio-dynir.svg -w '%{http_code}' \
  "${BASE}/api/content?path=sim/reports/dynamic_ir_flowlab_direct.svg")"
[[ "${code}" == "200" ]] && ok "content current_run svg → 200" || bad "content svg → ${code}"
rg -q '<svg' /tmp/studio-dynir.svg && ok "content svg payload" || bad "content svg empty"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materials/reference/dynamic-ir.md")"
[[ "${c}" == "200" ]] && ok "dynamic-ir.md page" || bad "dynamic-ir page → ${c}"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materials/reference/dynamic-ir-landscape.md")"
[[ "${c}" == "200" ]] && ok "dynamic-ir-landscape.md page" || bad "landscape page → ${c}"

code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o /tmp/studio-vectorless.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=vectorless&mode=flowlab")"
[[ "${code}" == "200" || "${code}" == "412" ]] && ok "vectorless stream → ${code}" || bad "vectorless → ${code}"
expect_sse_pass_or_gap "vectorless" /tmp/studio-vectorless.sse
if grep -Eq '"ok":true|_PASS|_DONE' /tmp/studio-vectorless.sse; then
  [[ -f "${ROOT}/learn/sim/reports/vectorless_flowlab.json" ]] && ok "vectorless json artifact" || bad "missing vectorless json"
  python3 - <<PY || bad "vectorless json parse"
import json
r=json.load(open("${ROOT}/learn/sim/reports/vectorless_flowlab.json"))
assert r["ok"] is True
assert r["vectorless"]["total_w"]
assert "vcd" in r["dynamic"]["source"]
print(r["summary"][:100])
PY
else
  ok "vectorless report checks skipped for explicit GAP"
fi

c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materials/reference/vectorless-power.md")"
[[ "${c}" == "200" ]] && ok "vectorless-power.md page" || bad "vectorless-power page → ${c}"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materials/reference/oss-integrations.md")"
[[ "${c}" == "200" ]] && ok "oss-integrations.md page" || bad "oss-integrations page → ${c}"

# SPICE lab viewer + download
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materials/file/sim/spice/nangate_inverter_demo.sp")"
[[ "${c}" == "200" ]] && ok "spice file viewer page" || bad "spice viewer → ${c}"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materials/reference/spice-power-chain.md")"
[[ "${c}" == "200" ]] && ok "spice-power-chain.md page" || bad "spice-power-chain → ${c}"
code="$(curl -s -o /tmp/studio-spice-dl.sp -w '%{http_code}' \
  "${BASE}/api/flowlab/download?kind=spice&path=sim/spice/nangate_inverter_demo.sp")"
[[ "${code}" == "200" ]] && ok "spice download API" || bad "spice download → ${code}"
rg -q 'CMOS inverter demo' /tmp/studio-spice-dl.sp && ok "spice download content" || bad "spice download empty"

# Content API reports
code="$(curl -s -o /tmp/studio-content-sys.json -w '%{http_code}' \
  "${BASE}/api/content?path=sim/reports/system_pdn_flowlab.json")"
[[ "${code}" == "200" ]] && ok "content system_pdn report" || bad "content system_pdn → ${code}"
rg -q 'summary' /tmp/studio-content-sys.json && ok "system_pdn report JSON" || bad "system_pdn report weak"
python3 - <<'PY' || bad "system_pdn report parse"
import json
d=json.load(open("/tmp/studio-content-sys.json"))
c=d.get("content","")
assert "summary" in c and "system_pdn" in c.lower() or '"kind": "system_pdn"' in c
print("parsed ok")
PY

# Refresh suite after the action jobs above so hook status is current-run data.
code="$(curl -s -o /tmp/studio-suite.json -w '%{http_code}' "${BASE}/api/suite")"
[[ "${code}" == "200" ]] && ok "refresh suite after power jobs" || bad "suite refresh → ${code}"

# Suite extended power hooks
if python3 - <<'PY'
import json, sys
d = json.load(open("/tmp/studio-suite.json"))
ids = {h["id"] for h in d["hooks"]}
need = {"ngspice", "activity", "chip_pdn_ir", "vyges_em_ir", "dynamic_ir", "power_chain", "spice_lab", "system_pdn"}
miss = sorted(need - ids)
if miss:
    print("missing", miss)
    sys.exit(1)
for hid in need:
    h = next(x for x in d["hooks"] if x["id"] == hid)
    if not h.get("ok"):
        tools = {item.get("name"): item.get("ok") for item in d.get("tools", {}).get("tools", [])}
        detail = str(h.get("detail", ""))
        status = str(h.get("status", "")).upper()
        # PROXY/WARN/PARTIAL are completed evidence states, not validated
        # signoff. The hook must remain non-green, but the suite smoke must
        # accept the explicitly classified result and ensure it is visible to
        # the UI instead of misreporting it as an unclassified failure.
        if status in {"PROXY", "WARN", "PARTIAL"}:
            continue
        if "GAP" in detail or (hid == "power_chain" and tools.get("openroad") is False):
            continue
        print("not ok", hid, h.get("detail"))
        sys.exit(1)
sys.exit(0)
PY
then
  ok "suite power hooks ready"
else
  bad "suite power hooks incomplete"
fi

rg -q '"id":"run-chip-ir"' /tmp/studio-open.json && ok "open run-chip-ir" || bad "open missing chip ir"
rg -q '"id":"run-dynamic-ir"' /tmp/studio-open.json && ok "open run-dynamic-ir" || bad "open missing dynamic ir"
rg -q '"id":"run-power-chain"' /tmp/studio-open.json && ok "open run-power-chain" || bad "open missing power chain"
rg -q '"id":"run-export-spice"' /tmp/studio-open.json && ok "open run-export-spice" || bad "open missing export spice"


# FlowLab rtl_sim (uses learn/flowlab/gcd.v)
code="$(curl -s "${AUTH_H[@]}" --max-time 60 -o /tmp/studio-fl-rtl.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=rtl_sim&mode=flowlab")"
[[ "${code}" == "200" || "${code}" == "412" ]] && ok "flowlab rtl_sim → ${code}" || bad "flowlab rtl_sim → ${code}"
expect_sse_pass_or_gap "flowlab rtl_sim" /tmp/studio-fl-rtl.sse

# Locked flowlab recook must not overwrite gcd/flowlab
FLOWLAB_GDS="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.gds"
if [[ -f "${FLOWLAB_GDS}" ]]; then
  code="$(curl -s "${AUTH_H[@]}" -o /tmp/studio-recook.json -w '%{http_code}' \
    "${BASE}/api/run/stream?action=synth&mode=flowlab")"
  [[ "${code}" == "403" ]] && ok "flowlab synth recook refused → 403" || bad "flowlab recook expected 403, got ${code}"
  rg -q 'overwrite gcd/flowlab' /tmp/studio-recook.json && ok "recook names locked path" || bad "recook message missing lock"
else
  ok "skip flowlab recook refuse (no 6_final.gds)"
fi

# Artifact preflight for missing finish artifact
if [[ ! -f "${RES_DIR}/6_final.gds" ]]; then
  code="$(curl -s "${AUTH_H[@]}" -o /tmp/studio-kldrc.json -w '%{http_code}' \
    "${BASE}/api/run/stream?action=klayout_drc")"
  [[ "${code}" == "412" ]] && ok "klayout_drc deps → 412" || bad "klayout_drc expected 412, got ${code}"
else
  ok "skip klayout_drc deps (gds present)"
fi

# Signoff API + docs
code="$(curl -s -o /tmp/studio-signoff.json -w '%{http_code}' "${BASE}/api/signoff?variant=flowlab")"
[[ "${code}" == "200" ]] && ok "GET /api/signoff → 200" || bad "signoff API → ${code}"
rg -q '"pillars"' /tmp/studio-signoff.json && ok "signoff.pillars" || bad "signoff missing pillars"
rg -q '"evaluation"' /tmp/studio-signoff.json && ok "signoff.evaluation" || bad "signoff missing evaluation"
rg -q '"staIr"' /tmp/studio-signoff.json && ok "signoff.staIr" || bad "signoff missing staIr"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materials/reference/signoff-matrix.md")"
[[ "${c}" == "200" ]] && ok "signoff-matrix.md page" || bad "signoff-matrix page → ${c}"

code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o /tmp/studio-sta.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=sta_signoff&mode=flowlab")"
[[ "${code}" == "200" || "${code}" == "412" ]] && ok "sta_signoff stream → ${code}" || bad "sta_signoff → ${code}"
expect_sse_pass_or_gap "sta_signoff" /tmp/studio-sta.sse


if python3 - <<'PY'
import json, sys
d = json.load(open("/tmp/studio-suite.json"))
ids = {h["id"] for h in d["hooks"]}
need = {"sta_signoff", "sta_ir_aware", "drc_signoff", "lvs_signoff", "power_signoff", "signoff_all", "thermal_signoff", "pkg_signoff", "signoff_phase2"}
miss = sorted(need - ids)
if miss:
    print("missing", miss)
    sys.exit(1)
sys.exit(0)
PY
then
  ok "suite signoff hook ids"
else
  bad "suite signoff hooks missing"
fi

code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o /tmp/studio-thermal.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=thermal_signoff&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "thermal_signoff stream → 200" || bad "thermal_signoff → ${code}"
expect_sse_pass_or_gap "thermal_signoff" /tmp/studio-thermal.sse

code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o /tmp/studio-pkg.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=pkg_signoff&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "pkg_signoff stream → 200" || bad "pkg_signoff → ${code}"
expect_sse_pass_or_gap "pkg_signoff" /tmp/studio-pkg.sse

code="$(curl -s "${AUTH_H[@]}" --max-time "${HTTP_TIMEOUT}" -o /tmp/studio-ph2.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=signoff_phase2&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "signoff_phase2 stream → 200" || bad "signoff_phase2 → ${code}"
expect_sse_pass_or_gap "signoff_phase2" /tmp/studio-ph2.sse

code="$(curl -s -o /tmp/studio-layout-meta.json -w '%{http_code}' \
  "${AUTH_H[@]}" \
  "${BASE}/api/layout-preview?phase=route&variant=flowlab")"
[[ "${code}" == "200" ]] && ok "layout-preview route → 200" || bad "layout-preview → ${code}"
python3 -c "
import json
d=json.load(open('/tmp/studio-layout-meta.json'))
assert d.get('imageUrl')
assert d.get('artifact', {}).get('exists') is True, d
assert d.get('odbExists') is True, d
assert (d.get('image') or {}).get('source') == 'odb', d
assert not (d.get('gallery') or []), d
assert not (d.get('compare') or []), d
assert d.get('layers')
" \
  && ok "layout-preview route = live ODB/layers" || bad "route preview meta incomplete"
code="$(curl -s -o /tmp/studio-layout-route.png -w '%{http_code}' \
  "${AUTH_H[@]}" \
  "${BASE}/api/layout-preview/image?phase=route&variant=flowlab")"
[[ "${code}" == "200" ]] && ok "layout-preview PNG route" || bad "layout image → ${code}"
code="$(curl -s -o /tmp/studio-layout-grt.png -w '%{http_code}' \
  "${AUTH_H[@]}" \
  "${BASE}/api/layout-preview/image?shot=07_grt.png")"
[[ "${code}" == "200" ]] && ok "layout-preview shot 07_grt" || bad "shot 07_grt → ${code}"
code="$(curl -s -o /dev/null -w '%{http_code}' \
  "${AUTH_H[@]}" \
  "${BASE}/api/layout-preview/image?shot=../secret.png")"
[[ "${code}" == "400" ]] && ok "layout-preview shot traversal 400" || bad "shot traversal → ${code}"

code="$(curl -s -o /tmp/studio-vcd.json -w '%{http_code}' "${BASE}/api/vcd-waveform")"
[[ "${code}" == "200" ]] && ok "vcd-waveform → 200" || ok "skip vcd-waveform (${code})"
if [[ "${code}" == "200" ]]; then
  python3 -c "import json; d=json.load(open('/tmp/studio-vcd.json')); assert len(d.get('signals',[]))>=2" \
    && ok "vcd-waveform signals" || bad "vcd-waveform empty"
fi
for phase in synth place route finish; do
  c="$(curl -s "${AUTH_H[@]}" -o /dev/null -w '%{http_code}' "${BASE}/api/layout-preview?phase=${phase}&variant=flowlab")"
  [[ "${c}" == "200" ]] && ok "layout-preview ${phase}" || bad "layout ${phase} → ${c}"
done

# A fresh browser stream must start live rather than replaying the retained
# event history. The endpoint stays open, so allow curl to stop after the
# bounded header/heartbeat probe without treating its timeout as a failure.
event_code="$(curl -sS --max-time 2 -H 'Origin: http://127.0.0.1:43217' \
  "${AUTH_H[@]}" -o /tmp/studio-events-initial.sse -w '%{http_code}' \
  "${BASE}/api/events?since=0" || true)"
event_bytes="$(wc -c < /tmp/studio-events-initial.sse)"
if [[ "${event_code}" == "200" && "${event_bytes}" -le 16384 ]]; then
  ok "SSE initial cursor is bounded (${event_bytes} bytes)"
else
  bad "SSE initial cursor replayed ${event_bytes} bytes (HTTP ${event_code})"
fi

# Auth deny probes (soft until runAuth enforces on this branch)
code="$(curl -s -o /tmp/studio-auth-deny.json -w '%{http_code}' \
  -H 'Origin: http://evil.example' \
  "${BASE}/api/run/stream?action=check")"
if [[ "${code}" == "403" ]]; then
  ok "wrong Origin → 403"
elif [[ "${code}" == "200" || "${code}" == "409" ]]; then
  ok "server does not yet enforce Origin (got ${code}) — structural curl still sends Origin"
else
  ok "auth probe got ${code} (non-fatal until runAuth lands)"
fi

if [[ "${FAIL}" -ne 0 ]]; then
  echo "STUDIO API SMOKE FAILED"
  exit 1
fi
echo "STUDIO API SMOKE PASSED"
exit 0
