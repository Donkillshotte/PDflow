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
need={"toolchain","rtl_sim","gridcheck","activity","klayout_drc","inspect","or-web","docs"}
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
rg -q '"id":"dash-flowlab"' /tmp/studio-open.json && ok "open dash-flowlab" || bad "open senza flowlab"

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

if [[ "${FAIL}" -ne 0 ]]; then
  echo "STUDIO API SMOKE FAILED"
  exit 1
fi
echo "STUDIO API SMOKE PASSED"
exit 0
