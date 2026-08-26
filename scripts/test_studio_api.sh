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

# Stream breve permesso (check)
code="$(curl -s --max-time 45 -o /tmp/studio-check.sse -w '%{http_code}' \
  "${BASE}/api/run/stream?action=check")"
[[ "${code}" == "200" ]] && ok "check stream → 200" || bad "check stream → ${code}"
rg -q '"type":"start"' /tmp/studio-check.sse && ok "SSE start event" || bad "SSE senza start"

# Azione vietata
code="$(curl -s -o /tmp/studio-bad.json -w '%{http_code}' \
  "${BASE}/api/run/stream?action=rm_rf")"
[[ "${code}" == "400" ]] && ok "forbidden action → 400" || bad "forbidden → ${code}"

# Pagine chiave
for path in /lezioni /strumenti /materiali /lezioni/00-intro; do
  c="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}${path}")"
  [[ "${c}" == "200" ]] && ok "GET ${path}" || bad "GET ${path} → ${c}"
done

if [[ "${FAIL}" -ne 0 ]]; then
  echo "STUDIO API SMOKE FAILED"
  exit 1
fi
echo "STUDIO API SMOKE PASSED"
exit 0
