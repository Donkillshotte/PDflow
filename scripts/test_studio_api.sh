#!/usr/bin/env bash
# Smoke API Studio (server su 127.0.0.1:43217).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${STUDIO_URL:-http://127.0.0.1:43217}"
FAIL=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; FAIL=1; }

echo "== Studio API @ ${BASE} =="

code="$(curl -s -o /tmp/studio-home.html -w '%{http_code}' "${BASE}/")"
[[ "${code}" == "200" ]] && ok "GET / → 200" || bad "GET / → ${code}"

code="$(curl -s -o /tmp/studio-jobs.json -w '%{http_code}' "${BASE}/api/jobs")"
[[ "${code}" == "200" ]] && ok "GET /api/jobs → 200" || bad "GET /api/jobs → ${code}"
rg -q '"pipeline"' /tmp/studio-jobs.json && ok "jobs.pipeline" || bad "jobs senza pipeline"
rg -q '"jobs"' /tmp/studio-jobs.json && ok "jobs.jobs" || bad "jobs senza array"

code="$(curl -s -o /tmp/studio-prog.json -w '%{http_code}' "${BASE}/api/progress?lessonId=00-intro")"
[[ "${code}" == "200" ]] && ok "GET progress+gates → 200" || bad "progress → ${code}"
rg -q '"gates"' /tmp/studio-prog.json && ok "progress.gates" || bad "progress senza gates"

# Completamento senza gate → 422
code="$(curl -s -o /tmp/studio-complete.json -w '%{http_code}' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"lessonId":"07-finish"}' \
  "${BASE}/api/progress")"
[[ "${code}" == "422" ]] && ok "POST complete gated → 422" || bad "complete atteso 422, got ${code}"

# Lock: simula lock file e verifica 409
LOCK_FILE="${ROOT}/learn/.studio-run.lock"
mkdir -p "$(dirname "${LOCK_FILE}")"
printf '%s\n' '{"jobId":"smoke-lock","action":"synth","startedAt":"2026-01-01T00:00:00.000Z","pid":1}' > "${LOCK_FILE}"
code="$(curl -s -o /tmp/studio-dep.json -w '%{http_code}' \
  "${BASE}/api/run/stream?action=check")"
[[ "${code}" == "409" ]] && ok "locked stream → 409" || bad "lock atteso 409, got ${code}"
rm -f "${LOCK_FILE}"

# Dipendenza fase: senza artefatto primario di synth → floorplan 412
RES_DIR="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/learn"
PRIMARY="${RES_DIR}/1_synth.odb"
if [[ -f "${PRIMARY}" ]]; then
  mv "${PRIMARY}" "${PRIMARY}.smoke-bak"
  code="$(curl -s -o /tmp/studio-deps.json -w '%{http_code}' \
    "${BASE}/api/run/stream?action=floorplan")"
  mv "${PRIMARY}.smoke-bak" "${PRIMARY}"
  [[ "${code}" == "412" ]] && ok "floorplan deps → 412" || bad "deps atteso 412, got ${code}"
  rg -q '"code":"deps"' /tmp/studio-deps.json && ok "deps payload" || bad "412 senza code deps"
else
  ok "skip deps test (no 1_synth.odb yet)"
fi

# Stream breve permesso (check)
code="$(curl -s --max-time 45 -o /tmp/studio-check.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=check")"
[[ "${code}" == "200" ]] && ok "check stream → 200" || bad "check stream → ${code}"
rg -q '"type":"start"' /tmp/studio-check.sse && ok "SSE start event" || bad "SSE senza start"

# Azione vietata
code="$(curl -s -o /tmp/studio-bad.json -w '%{http_code}' \
  "${BASE}/api/run/stream?action=rm_rf")"
[[ "${code}" == "400" ]] && ok "forbidden action → 400" || bad "forbidden → ${code}"

# Pagine chiave + deep-link
for path in /lezioni /strumenti /materiali /lezioni/00-intro \
  '/strumenti?stage=cts&tab=results' '/materiali?tab=gallery'; do
  c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}${path}")"
  [[ "${c}" == "200" ]] && ok "GET ${path}" || bad "GET ${path} → ${c}"
done

# Catalogo open + dry-run / launch
code="$(curl -s -o /tmp/studio-open.json -w '%{http_code}' "${BASE}/api/open")"
[[ "${code}" == "200" ]] && ok "GET /api/open → 200" || bad "open → ${code}"
rg -q '"targets"' /tmp/studio-open.json && ok "open.targets" || bad "open senza targets"
rg -q 'gui-synth|Dashboard risultati' /tmp/studio-open.json && ok "open catalog entries" || bad "open catalog vuoto"

code="$(curl -s -o /tmp/studio-open-dry.json -w '%{http_code}' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"id":"dash-cts"}' "${BASE}/api/open")"
[[ "${code}" == "200" ]] && ok "POST open dash-cts → 200" || bad "open dash → ${code}"
rg -q '"navigate"' /tmp/studio-open-dry.json && ok "open navigate" || bad "open senza navigate"

if rg -q '"id":"gui-synth"[^}]*"exists":true' /tmp/studio-open.json \
  || python3 -c 'import json;d=json.load(open("/tmp/studio-open.json"));print(any(t["id"]=="gui-synth" and t["exists"] for t in d["targets"]))' | rg -q True; then
  code="$(curl -s -o /tmp/studio-open-gui.json -w '%{http_code}' \
    -X POST -H 'Content-Type: application/json' \
    -d '{"id":"gui-synth","dryRun":true}' "${BASE}/api/open")"
  [[ "${code}" == "200" ]] && ok "POST open gui-synth dryRun" || bad "gui dryRun → ${code}"
else
  ok "skip gui-synth launch (odb assente)"
fi

# Inspect + web viewer
code="$(curl -s -o /tmp/studio-inspect.json -w '%{http_code}' \
  "${BASE}/api/inspect?stage=synth")"
[[ "${code}" == "200" ]] && ok "GET inspect synth → 200" || bad "inspect → ${code}"
rg -q '"odb"|"sta"|"yosys"|"hooks"' /tmp/studio-inspect.json && ok "inspect payload" || bad "inspect payload debole"

code="$(curl -s -o /tmp/studio-viewer.json -w '%{http_code}' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"action":"start","stage":"cts"}' "${BASE}/api/viewer")"
[[ "${code}" == "200" ]] && ok "POST viewer start → 200" || bad "viewer start → ${code}"
URL="$(python3 -c 'import json;print(json.load(open("/tmp/studio-viewer.json")).get("url",""))')"
if [[ -n "${URL}" ]]; then
  sleep 1
  c="$(curl -s -o /dev/null -w '%{http_code}' "${URL}")"
  [[ "${c}" == "200" ]] && ok "web viewer HTTP 200" || bad "web viewer → ${c}"
fi
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"action":"stop"}' "${BASE}/api/viewer" >/dev/null
ok "viewer stop"

code="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materiali/reference/tool-hooks.md")"
[[ "${code}" == "200" ]] && ok "tool-hooks.md page" || bad "tool-hooks page → ${code}"
code="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materiali/reference/extended-flow.md")"
[[ "${code}" == "200" ]] && ok "extended-flow.md page" || bad "extended-flow page → ${code}"

# Extended actions (short)
code="$(curl -s --max-time 60 -o /tmp/studio-rtl.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=rtl_sim")"
[[ "${code}" == "200" ]] && ok "rtl_sim stream → 200" || bad "rtl_sim → ${code}"
rg -q 'RTL_SIM_PASS|"ok":true' /tmp/studio-rtl.sse && ok "rtl_sim pass event" || bad "rtl_sim senza PASS"

code="$(curl -s --max-time 60 -o /tmp/studio-gc.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=gridcheck")"
[[ "${code}" == "200" ]] && ok "gridcheck stream → 200" || bad "gridcheck → ${code}"
rg -q 'GRIDCHECK_DONE|PSM-0040' /tmp/studio-gc.sse && ok "gridcheck ok" || bad "gridcheck fallita"

# Suite hub + palette run/webviewer entries
code="$(curl -s -o /tmp/studio-suite.json -w '%{http_code}' "${BASE}/api/suite")"
[[ "${code}" == "200" ]] && ok "GET /api/suite → 200" || bad "suite → ${code}"
rg -q '"hooks"' /tmp/studio-suite.json && ok "suite.hooks" || bad "suite senza hooks"
rg -q '"ready"' /tmp/studio-suite.json && ok "suite.ready" || bad "suite senza ready"
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
  bad "suite core hooks mancanti"
fi

rg -q '"id":"run-rtl-sim"' /tmp/studio-open.json && ok "open run-rtl-sim" || bad "open senza run-rtl-sim"
rg -q '"kind":"webviewer"' /tmp/studio-open.json && ok "open webviewer kind" || bad "open senza webviewer"
rg -q '"id":"dash-suite"' /tmp/studio-open.json && ok "open dash-suite" || bad "open senza dash-suite"

code="$(curl -s -o /tmp/studio-open-run.json -w '%{http_code}' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"id":"run-gridcheck"}' "${BASE}/api/open")"
[[ "${code}" == "200" ]] && ok "POST open run-gridcheck" || bad "open run → ${code}"
rg -q 'tab=run&action=gridcheck' /tmp/studio-open-run.json && ok "run navigate deep-link" || bad "run navigate errato"

c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/strumenti?tab=run&action=rtl_sim")"
[[ "${c}" == "200" ]] && ok "GET strumenti action deep-link" || bad "strumenti action → ${c}"

# FlowLab API + page
code="$(curl -s -o /tmp/studio-flowlab.json -w '%{http_code}' "${BASE}/api/flowlab")"
[[ "${code}" == "200" ]] && ok "GET /api/flowlab → 200" || bad "flowlab → ${code}"
rg -q '"rtl"' /tmp/studio-flowlab.json && ok "flowlab.rtl" || bad "flowlab senza rtl"
rg -q '"params"' /tmp/studio-flowlab.json && ok "flowlab.params" || bad "flowlab senza params"
rg -q '"coreUtilization"' /tmp/studio-flowlab.json && ok "flowlab.params.coreUtilization" || bad "params incompleti"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/flusso")"
[[ "${c}" == "200" ]] && ok "GET /flusso" || bad "flusso → ${c}"
rg -q '"sim"' /tmp/studio-flowlab.json && ok "flowlab.sim" || bad "flowlab senza sim"
rg -q '"phaseHistory"' /tmp/studio-flowlab.json && ok "flowlab.phaseHistory" || bad "flowlab senza phaseHistory"
code="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/api/flowlab/download?kind=vcd")"
[[ "${code}" == "200" || "${code}" == "404" ]] && ok "flowlab vcd download (${code})" || bad "flowlab download → ${code}"
rg -q '"id":"dash-flowlab"' /tmp/studio-open.json && ok "open dash-flowlab" || bad "open senza flowlab"
rg -q '"id":"dash-pkg"' /tmp/studio-open.json && ok "open dash-pkg" || bad "open senza dash-pkg"
rg -q '"id":"run-system-pdn"' /tmp/studio-open.json && ok "open run-system-pdn" || bad "open senza system_pdn"

c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/pkg")"
[[ "${c}" == "200" ]] && ok "GET /pkg" || bad "pkg → ${c}"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materiali/reference/system-pdn.md")"
[[ "${c}" == "200" ]] && ok "system-pdn.md page" || bad "system-pdn page → ${c}"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materiali/reference/pkg-design-package.md")"
[[ "${c}" == "200" ]] && ok "pkg-design-package.md page" || bad "pkg doc page → ${c}"

# ORFS log digest (wrapper must classify WARN vs ERROR, not treat Failure:0 as error)
code="$(curl -s -o /tmp/studio-results-finish.json -w '%{http_code}' \
  "${BASE}/api/results?stage=finish&variant=flowlab")"
[[ "${code}" == "200" ]] && ok "GET /api/results finish flowlab → 200" || bad "results finish → ${code}"
rg -q '"logDigest"' /tmp/studio-results-finish.json && ok "results.logDigest" || bad "results senza logDigest"
python3 - <<'PY' || bad "logDigest.errors deve essere 0"
import json
d=json.load(open("/tmp/studio-results-finish.json"))
dig=d.get("logDigest") or {}
assert dig.get("errors", 1) == 0, dig
assert dig.get("healthy") is True, dig
print("OK digest", dig.get("summary","")[:80])
PY
ok "logDigest.healthy (0 ERROR)"

code="$(curl -s --max-time 60 -o /tmp/studio-syspdn.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=system_pdn&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "system_pdn stream → 200" || bad "system_pdn → ${code}"
rg -q 'SYSTEM_PDN_DONE|"ok":true' /tmp/studio-syspdn.sse && ok "system_pdn pass" || bad "system_pdn fail"

# Power signoff chain (requires finish — flowlab variant)
for action in activity_power chip_pdn_ir export_spice_lab; do
  code="$(curl -s --max-time 180 -o "/tmp/studio-${action}.sse" -w '%{http_code}' \
    "${BASE}/api/run/stream?action=${action}&mode=flowlab")"
  [[ "${code}" == "200" ]] && ok "${action} stream → 200" || bad "${action} → ${code}"
  rg -q '"ok":true' "/tmp/studio-${action}.sse" && ok "${action} pass" || bad "${action} fail"
done

code="$(curl -s --max-time 600 -o /tmp/studio-power-chain.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=power_chain&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "power_chain stream → 200" || bad "power_chain → ${code}"
rg -q 'POWER_CHAIN_DONE|"ok":true' /tmp/studio-power-chain.sse && ok "power_chain pass" || bad "power_chain fail"
[[ -f "${ROOT}/learn/sim/reports/power_chain_flowlab.log" ]] && ok "power_chain log artifact" || bad "manca power_chain log"
rg -q 'ACTIVITY_SOURCE' "${ROOT}/learn/sim/reports/activity_power_flowlab.log" 2>/dev/null \
  && ok "activity_power source stamped" || bad "activity_power log senza ACTIVITY_SOURCE"
rg -q 'Wrong number of arguments' "${ROOT}/learn/sim/reports/activity_power_flowlab.log" 2>/dev/null \
  && bad "activity_power still has read_vcd arity error" \
  || ok "activity_power no VCD arity error"

# Tool matrix / vectorless / equiv / formal / OpenRCX / PEX
for action in yosys_equiv formal_gcd openrcx_report analytical_pex layout_tools spice_engines; do
  code="$(curl -s --max-time 120 -o "/tmp/studio-${action}.sse" -w '%{http_code}' \
    "${BASE}/api/run/stream?action=${action}&mode=flowlab")"
  [[ "${code}" == "200" ]] && ok "${action} stream → 200" || bad "${action} → ${code}"
  rg -q '"ok":true' "/tmp/studio-${action}.sse" && ok "${action} pass" || bad "${action} fail"
done

code="$(curl -s --max-time 180 -o /tmp/studio-vyges.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=vyges_em_ir&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "vyges_em_ir stream → 200" || bad "vyges_em_ir → ${code}"
rg -q '"ok":true' /tmp/studio-vyges.sse && ok "vyges_em_ir pass" || bad "vyges_em_ir fail"
[[ -f "${ROOT}/learn/sim/reports/vyges_em_ir_flowlab.json" ]] && ok "vyges_em_ir json artifact" || bad "manca vyges_em_ir json"
python3 - <<PY || bad "vyges_em_ir json parse"
import json
r=json.load(open("${ROOT}/learn/sim/reports/vyges_em_ir_flowlab.json"))
assert r["ok"] is True
assert r["engine"] == "vyges-em-ir"
assert r["vyges"]["worst_ir"]["drop"] > 0
print(r["summary"][:120])
PY
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materiali/reference/vyges-em-ir.md")"
[[ "${c}" == "200" ]] && ok "vyges-em-ir.md page" || bad "vyges-em-ir page → ${c}"

code="$(curl -s --max-time 60 -o /tmp/studio-dynir.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=dynamic_ir&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "dynamic_ir stream → 200" || bad "dynamic_ir → ${code}"
rg -q '"ok":true' /tmp/studio-dynir.sse && ok "dynamic_ir pass" || bad "dynamic_ir fail"
[[ -f "${ROOT}/learn/sim/reports/dynamic_ir_flowlab.json" ]] && ok "dynamic_ir json artifact" || bad "manca dynamic_ir json"
[[ -f "${ROOT}/learn/sim/reports/dynamic_ir_flowlab.svg" ]] && ok "dynamic_ir svg artifact" || bad "manca dynamic_ir svg"
python3 - <<PY || bad "dynamic_ir json parse"
import json
r=json.load(open("${ROOT}/learn/sim/reports/dynamic_ir_flowlab.json"))
assert r["ok"] is True
assert r["kind"] == "dynamic_ir"
assert r["static"]["worst_ir"] > 0
assert r["dynamic"]["worst_droop"] > 0
assert r["sim_levels"]["L0_static"]["status"] == "READY"
assert r["sim_levels"]["L2_vcd_dynamic"]["status"] == "GAP"
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
assert r["platform"]["solvers"]["B_sa_amg"]["status"] == "READY"
assert r["platform"]["solvers"]["C_rational_krylov_mor"]["status"] in ("READY", "PARTIAL")
assert r["platform"]["solvers"].get("D_ras_schwarz", {}).get("status") in (None, "READY", "PARTIAL", "GAP")
assert r["platform"]["product_tiers"]["FAST"]["status"] == "READY"
assert r["platform"]["network_levels"]["N2_RC"]["status"] == "READY"
assert r["solver_b"]["ok"] is True
assert r["solver_b"]["abs_err_vs_A_mv"] < 5.0
assert r["solver_b"].get("backend") in (None, "native", "python")
c = r.get("solver_c")
assert c is None or c.get("abs_err_vs_A_mv", 0) < 5.0
d = r.get("solver_d")
assert d is None or d.get("abs_err_vs_A_mv", 0) < 5.0
assert "windows" in r["sim_levels"]["L3_windowed"]
g = r.get("ngspice_gold")
assert g is None or g.get("ok") is True, g
print(r["summary"][:120])
PY
code="$(curl -s -o /tmp/studio-dynir.svg -w '%{http_code}' \
  "${BASE}/api/content?path=sim/reports/dynamic_ir_flowlab.svg")"
[[ "${code}" == "200" ]] && ok "content dynamic_ir svg → 200" || bad "content svg → ${code}"
rg -q '<svg' /tmp/studio-dynir.svg && ok "content svg payload" || bad "content svg vuoto"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materiali/reference/dynamic-ir.md")"
[[ "${c}" == "200" ]] && ok "dynamic-ir.md page" || bad "dynamic-ir page → ${c}"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materiali/reference/dynamic-ir-landscape.md")"
[[ "${c}" == "200" ]] && ok "dynamic-ir-landscape.md page" || bad "landscape page → ${c}"

code="$(curl -s --max-time 180 -o /tmp/studio-vectorless.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=vectorless&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "vectorless stream → 200" || bad "vectorless → ${code}"
rg -q '"ok":true' /tmp/studio-vectorless.sse && ok "vectorless pass" || bad "vectorless fail"
[[ -f "${ROOT}/learn/sim/reports/vectorless_flowlab.json" ]] && ok "vectorless json artifact" || bad "manca vectorless json"
python3 - <<PY || bad "vectorless json parse"
import json
r=json.load(open("${ROOT}/learn/sim/reports/vectorless_flowlab.json"))
assert r["ok"] is True
assert r["vectorless"]["total_w"]
assert "vcd" in r["dynamic"]["source"]
print(r["summary"][:100])
PY

c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materiali/reference/vectorless-power.md")"
[[ "${c}" == "200" ]] && ok "vectorless-power.md page" || bad "vectorless-power page → ${c}"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materiali/reference/oss-integrations.md")"
[[ "${c}" == "200" ]] && ok "oss-integrations.md page" || bad "oss-integrations page → ${c}"

# SPICE lab viewer + download
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materiali/file/sim/spice/nangate_inverter_demo.sp")"
[[ "${c}" == "200" ]] && ok "spice file viewer page" || bad "spice viewer → ${c}"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materiali/reference/spice-power-chain.md")"
[[ "${c}" == "200" ]] && ok "spice-power-chain.md page" || bad "spice-power-chain → ${c}"
code="$(curl -s -o /tmp/studio-spice-dl.sp -w '%{http_code}' \
  "${BASE}/api/flowlab/download?kind=spice&path=sim/spice/nangate_inverter_demo.sp")"
[[ "${code}" == "200" ]] && ok "spice download API" || bad "spice download → ${code}"
rg -q 'CMOS inverter demo' /tmp/studio-spice-dl.sp && ok "spice download content" || bad "spice download vuoto"

# Content API reports
code="$(curl -s -o /tmp/studio-content-sys.json -w '%{http_code}' \
  "${BASE}/api/content?path=sim/reports/system_pdn_flowlab.json")"
[[ "${code}" == "200" ]] && ok "content system_pdn report" || bad "content system_pdn → ${code}"
rg -q 'summary' /tmp/studio-content-sys.json && ok "system_pdn report JSON" || bad "system_pdn report debole"
python3 - <<'PY' || bad "system_pdn report parse"
import json
d=json.load(open("/tmp/studio-content-sys.json"))
c=d.get("content","")
assert "summary" in c and "system_pdn" in c.lower() or '"kind": "system_pdn"' in c
print("parsed ok")
PY

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
        print("not ok", hid, h.get("detail"))
        sys.exit(1)
sys.exit(0)
PY
then
  ok "suite power hooks ready"
else
  bad "suite power hooks incomplete"
fi

rg -q '"id":"run-chip-ir"' /tmp/studio-open.json && ok "open run-chip-ir" || bad "open senza chip ir"
rg -q '"id":"run-dynamic-ir"' /tmp/studio-open.json && ok "open run-dynamic-ir" || bad "open senza dynamic ir"
rg -q '"id":"run-power-chain"' /tmp/studio-open.json && ok "open run-power-chain" || bad "open senza power chain"
rg -q '"id":"run-export-spice"' /tmp/studio-open.json && ok "open run-export-spice" || bad "open senza export spice"

# activity_power requires 6_final.odb (412 without)
FINAL="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.odb"
if [[ -f "${FINAL}" ]]; then
  mv "${FINAL}" "${FINAL}.smoke-bak"
  code="$(curl -s -o /tmp/studio-act-dep.json -w '%{http_code}' \
    "${BASE}/api/run/stream?action=activity_power&mode=flowlab")"
  mv "${FINAL}.smoke-bak" "${FINAL}"
  [[ "${code}" == "412" ]] && ok "activity_power deps → 412" || bad "activity_power atteso 412, got ${code}"
  rg -q '"code":"deps"' /tmp/studio-act-dep.json && ok "activity_power deps payload" || bad "412 senza code deps"
else
  ok "skip activity_power deps (no 6_final.odb)"
fi

# system_pdn also gated on 6_final.odb
if [[ -f "${FINAL}" ]]; then
  mv "${FINAL}" "${FINAL}.smoke-bak"
  code="$(curl -s -o /tmp/studio-syspdn-dep.json -w '%{http_code}' \
    "${BASE}/api/run/stream?action=system_pdn&mode=flowlab")"
  mv "${FINAL}.smoke-bak" "${FINAL}"
  [[ "${code}" == "412" ]] && ok "system_pdn deps → 412" || bad "system_pdn atteso 412, got ${code}"
else
  ok "skip system_pdn deps (no 6_final.odb)"
fi

# FlowLab rtl_sim (uses learn/flowlab/gcd.v)
code="$(curl -s --max-time 60 -o /tmp/studio-fl-rtl.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=rtl_sim&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "flowlab rtl_sim → 200" || bad "flowlab rtl_sim → ${code}"
rg -q 'RTL_SIM_PASS|"ok":true' /tmp/studio-fl-rtl.sse && ok "flowlab rtl_sim pass" || bad "flowlab rtl_sim fail"

# Artifact preflight for missing finish artifact
if [[ ! -f "${RES_DIR}/6_final.gds" ]]; then
  code="$(curl -s -o /tmp/studio-kldrc.json -w '%{http_code}' \
    "${BASE}/api/run/stream?action=klayout_drc")"
  [[ "${code}" == "412" ]] && ok "klayout_drc deps → 412" || bad "klayout_drc atteso 412, got ${code}"
else
  ok "skip klayout_drc deps (gds presente)"
fi

# Signoff API + docs
code="$(curl -s -o /tmp/studio-signoff.json -w '%{http_code}' "${BASE}/api/signoff?variant=flowlab")"
[[ "${code}" == "200" ]] && ok "GET /api/signoff → 200" || bad "signoff API → ${code}"
rg -q '"pillars"' /tmp/studio-signoff.json && ok "signoff.pillars" || bad "signoff senza pillars"
rg -q '"evaluation"' /tmp/studio-signoff.json && ok "signoff.evaluation" || bad "signoff senza evaluation"
c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/materiali/reference/signoff-matrix.md")"
[[ "${c}" == "200" ]] && ok "signoff-matrix.md page" || bad "signoff-matrix page → ${c}"

code="$(curl -s --max-time 120 -o /tmp/studio-sta.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=sta_signoff&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "sta_signoff stream → 200" || bad "sta_signoff → ${code}"
rg -q 'STA_SIGNOFF_DONE|"ok":true' /tmp/studio-sta.sse && ok "sta_signoff pass" || bad "sta_signoff fail"

# sta_signoff preflight without 6_final.v
FINAL_V="${ROOT}/tools/OpenROAD-flow-scripts/flow/results/nangate45/gcd/flowlab/6_final.v"
if [[ -f "${FINAL_V}" ]]; then
  mv "${FINAL_V}" "${FINAL_V}.smoke-bak"
  code="$(curl -s -o /tmp/studio-sta-dep.json -w '%{http_code}' \
    "${BASE}/api/run/stream?action=sta_signoff&mode=flowlab")"
  mv "${FINAL_V}.smoke-bak" "${FINAL_V}"
  [[ "${code}" == "412" ]] && ok "sta_signoff deps → 412" || bad "sta_signoff atteso 412, got ${code}"
else
  ok "skip sta_signoff deps (no 6_final.v)"
fi

if python3 - <<'PY'
import json, sys
d = json.load(open("/tmp/studio-suite.json"))
ids = {h["id"] for h in d["hooks"]}
need = {"sta_signoff", "drc_signoff", "lvs_signoff", "power_signoff", "signoff_all", "thermal_signoff", "pkg_signoff", "signoff_phase2"}
miss = sorted(need - ids)
if miss:
    print("missing", miss)
    sys.exit(1)
sys.exit(0)
PY
then
  ok "suite signoff hook ids"
else
  bad "suite signoff hooks mancanti"
fi

code="$(curl -s --max-time 60 -o /tmp/studio-thermal.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=thermal_signoff&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "thermal_signoff stream → 200" || bad "thermal_signoff → ${code}"
rg -q 'THERMAL_SIGNOFF_DONE|"ok":true' /tmp/studio-thermal.sse && ok "thermal_signoff pass" || bad "thermal_signoff fail"

code="$(curl -s --max-time 90 -o /tmp/studio-pkg.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=pkg_signoff&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "pkg_signoff stream → 200" || bad "pkg_signoff → ${code}"
rg -q 'PKG_SIGNOFF_DONE|"ok":true' /tmp/studio-pkg.sse && ok "pkg_signoff pass" || bad "pkg_signoff fail"

code="$(curl -s --max-time 120 -o /tmp/studio-ph2.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=signoff_phase2&mode=flowlab")"
[[ "${code}" == "200" ]] && ok "signoff_phase2 stream → 200" || bad "signoff_phase2 → ${code}"
rg -q 'SIGNOFF_PHASE2_DONE|"ok":true' /tmp/studio-ph2.sse && ok "signoff_phase2 pass" || bad "signoff_phase2 fail"

code="$(curl -s -o /tmp/studio-layout-meta.json -w '%{http_code}' \
  "${BASE}/api/layout-preview?phase=route&variant=flowlab")"
[[ "${code}" == "200" ]] && ok "layout-preview route → 200" || bad "layout-preview → ${code}"
python3 -c "
import json
d=json.load(open('/tmp/studio-layout-meta.json'))
assert d.get('imageUrl')
assert '08_route' in (d.get('image') or {}).get('rel','')
g=d.get('gallery') or []
assert len(g)>=4, g
assert any('07_grt' in (x.get('file') or '') for x in g)
c=d.get('compare') or []
assert any(x.get('id')=='grt-drt' for x in c), c
assert any(x.get('id')=='place-route' for x in c)
assert d.get('layers')
" \
  && ok "layout-preview route = 08_route_labeled + gallery/compare/layers" || bad "route preview meta incompleta"
code="$(curl -s -o /tmp/studio-layout-route.png -w '%{http_code}' \
  "${BASE}/api/layout-preview/image?phase=route&variant=flowlab")"
[[ "${code}" == "200" ]] && ok "layout-preview PNG route" || bad "layout image → ${code}"
code="$(curl -s -o /tmp/studio-layout-grt.png -w '%{http_code}' \
  "${BASE}/api/layout-preview/image?shot=07_grt.png")"
[[ "${code}" == "200" ]] && ok "layout-preview shot 07_grt" || bad "shot 07_grt → ${code}"
code="$(curl -s -o /dev/null -w '%{http_code}' \
  "${BASE}/api/layout-preview/image?shot=../secret.png")"
[[ "${code}" == "400" ]] && ok "layout-preview shot traversal 400" || bad "shot traversal → ${code}"

code="$(curl -s -o /tmp/studio-vcd.json -w '%{http_code}' "${BASE}/api/vcd-waveform")"
[[ "${code}" == "200" ]] && ok "vcd-waveform → 200" || ok "skip vcd-waveform (${code})"
if [[ "${code}" == "200" ]]; then
  python3 -c "import json; d=json.load(open('/tmp/studio-vcd.json')); assert len(d.get('signals',[]))>=2" \
    && ok "vcd-waveform signals" || bad "vcd-waveform vuoto"
fi
for phase in synth place route finish; do
  c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/api/layout-preview?phase=${phase}&variant=flowlab")"
  [[ "${c}" == "200" ]] && ok "layout-preview ${phase}" || bad "layout ${phase} → ${c}"
done

if [[ "${FAIL}" -ne 0 ]]; then
  echo "STUDIO API SMOKE FAILED"
  exit 1
fi
echo "STUDIO API SMOKE PASSED"
exit 0
