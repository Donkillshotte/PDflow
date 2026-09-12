#!/usr/bin/env bash
# Contract and API smoke tests for the Linux-first PDflow local agent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${PD_FLOW_AGENT_URL:-http://127.0.0.1:43219}"
HTTP_TIMEOUT="${PD_FLOW_AGENT_CURL_TIMEOUT_S:-600}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT
FAIL=0
AUTH_H=()
TOKEN_PATH="${ROOT}/.pdflow/agent/agent.token"
if [[ -r "${TOKEN_PATH}" ]]; then
  AGENT_TOKEN="$(tr -d '\r\n' < "${TOKEN_PATH}")"
  if [[ -n "${AGENT_TOKEN}" ]]; then
    AUTH_H=(-H "X-PDFlow-Token: ${AGENT_TOKEN}")
  fi
fi

ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; FAIL=1; }

request() {
  local output="$1"
  shift
  curl -sS --max-time "${HTTP_TIMEOUT}" -o "${output}" -w '%{http_code}' "${AUTH_H[@]}" "$@"
}

assert_json() {
  local label="$1"
  local file="$2"
  shift 2
  if python3 - "$file" "$@" <<'PY'
import json
import sys

path = sys.argv[1]
code = sys.argv[2]
data = json.load(open(path, encoding="utf-8"))
if code == "health":
    assert data["service"] == "pdflow-local-agent"
    assert data["watcher"]["mode"] in {"inotify", "polling"}
elif code == "registry":
    assert data["default_timeout_seconds"] == 600
    assert data["schema_version"] >= 1
    tools = data["tools"]
    assert tools
    required = {"tool_id", "capabilities", "input_kinds", "output_kinds", "availability", "timeout_seconds"}
    assert all(required <= set(tool) for tool in tools)
    assert all(tool["availability"] in {"READY", "MISSING", "MISCONFIGURED", "INCOMPATIBLE"} for tool in tools)
    actions = {item["action_id"]: item for item in data["actions"]}
    assert {"synth", "floorplan", "place", "cts", "route", "finish", "list"} <= set(actions)
    assert all(item["timeout_seconds"] == 600 for item in actions.values())
elif code == "context":
    assert data["surface"] == "flow"
    assert all(item["authority"] == "finish" and item["mutable"] is False for item in data["finish"])
    assert data["comparison_scope"] == "same-live-invocation"
elif code == "artifacts":
    refs = data["artifacts"]
    assert refs
    assert all(item["authority"] == "finish" and item["mutable"] is False for item in refs)
    odb = next(item for item in refs if item["kind"] == "odb")
    print(odb["artifact_id"])
    print(odb["content_hash"] or "")
elif code == "detail":
    assert data["resolved"] is True
    assert data["read_only"] is True
    assert data["artifact"]["authority"] == "finish"
elif code == "candidate":
    source = data["source"]
    candidate = data["candidate"]
    assert candidate["authority"] == "candidate"
    assert candidate["mutable"] is True
    assert candidate["content_hash"] == source["content_hash"]
    print(candidate["artifact_id"])
    print(candidate["relative_path"])
elif code == "run":
    assert data["run"]["run_id"] == sys.argv[3]
    assert data["run"]["surface"] == "flow"
elif code == "job_pass":
    assert data["state"] == "COMPLETED"
    assert data["report"]["status"] == "PASS"
    assert data["report"]["ok"] is True
elif code == "job_gap":
    assert data["state"] == "GAP"
    assert data["report"]["status"] == "GAP"
    assert data["report"]["ok"] is False
elif code == "package":
    assert data["status"] in {"GAP", "PASS", "PROXY", "PARTIAL", "NOT_RUN"}
    if data["status"] != "PASS":
        assert data["ok"] is False
elif code == "ledger":
    assert data["status"] in {"GAP", "PASS", "PROXY", "PARTIAL", "NOT_RUN", "FAIL"}
    if data["status"] != "PASS":
        assert data["ok"] is False
elif code == "compare":
    assert data["status"] == "GAP"
    assert data["ok"] is False
    assert data["comparison_scope"] == "not-comparable"
    assert data["relative"] == []
elif code == "refresh":
    assert data["ok"] is True
else:
    raise AssertionError(code)
PY
  then
    ok "${label}"
  else
    bad "${label}"
  fi
}

echo "== PDflow local agent @ ${BASE} =="

if [[ "${#AUTH_H[@]}" -gt 0 ]]; then
  code="$(curl -sS --max-time "${HTTP_TIMEOUT}" -o "${TMP_DIR}/unauthorized.json" -w '%{http_code}' "${BASE}/v1/registry")"
  [[ "${code}" == "401" ]] && ok "unauthenticated registry request rejected" || bad "unauthenticated registry HTTP ${code}"
fi

code="$(request "${TMP_DIR}/health.json" "${BASE}/v1/health")"
[[ "${code}" == "200" ]] && assert_json "health contract" "${TMP_DIR}/health.json" health || bad "health HTTP ${code}"

code="$(request "${TMP_DIR}/registry.json" "${BASE}/v1/registry")"
[[ "${code}" == "200" ]] && assert_json "registry contract and 600s defaults" "${TMP_DIR}/registry.json" registry || bad "registry HTTP ${code}"

code="$(request "${TMP_DIR}/context.json" "${BASE}/v1/context?surface=flow")"
[[ "${code}" == "200" ]] && assert_json "finish context is read-only" "${TMP_DIR}/context.json" context || bad "context HTTP ${code}"

code="$(request "${TMP_DIR}/artifacts.json" "${BASE}/v1/artifacts?authority=finish&variant=flowlab&limit=2000")"
if [[ "${code}" == "200" ]]; then
  mapfile -t ART_INFO < <(python3 - "${TMP_DIR}/artifacts.json" <<'PY'
import json
data = json.load(open(__import__("sys").argv[1], encoding="utf-8"))
refs = data["artifacts"]
assert refs
assert all(item["authority"] == "finish" and item["mutable"] is False for item in refs)
odb = next(item for item in refs if item["kind"] == "odb")
print(odb["artifact_id"])
print(odb["content_hash"] or "")
PY
  )
  if [[ "${#ART_INFO[@]}" -ge 2 && -n "${ART_INFO[0]}" ]]; then
    ok "finish artifact catalog is filtered and hashed"
  else
    bad "finish artifact catalog has no ODB reference"
  fi
else
  bad "artifacts HTTP ${code}"
fi

ARTIFACT_ID="${ART_INFO[0]:-}"
SOURCE_HASH="${ART_INFO[1]:-}"
if [[ -n "${ARTIFACT_ID}" ]]; then
  code="$(request "${TMP_DIR}/detail.json" "${BASE}/v1/artifacts/${ARTIFACT_ID}")"
  [[ "${code}" == "200" ]] && assert_json "artifact detail resolves read-only" "${TMP_DIR}/detail.json" detail || bad "artifact detail HTTP ${code}"
fi

RUN_ID="run-agent-smoke-$(date +%s)-$$"
code="$(request "${TMP_DIR}/run.json" -X POST -H 'Content-Type: application/json' \
  -d "{\"run_id\":\"${RUN_ID}\",\"surface\":\"flow\",\"profile\":\"api-smoke\"}" \
  "${BASE}/v1/runs")"
[[ "${code}" == "201" ]] && assert_json "run context persisted" "${TMP_DIR}/run.json" run "${RUN_ID}" || bad "run HTTP ${code}"

if [[ -n "${ARTIFACT_ID}" ]]; then
  code="$(request "${TMP_DIR}/candidate.json" -X POST -H 'Content-Type: application/json' \
    -d "{\"run_id\":\"${RUN_ID}\",\"artifact_id\":\"${ARTIFACT_ID}\"}" \
    "${BASE}/v1/candidates")"
  if [[ "${code}" == "201" ]]; then
    assert_json "candidate copy preserves source hash" "${TMP_DIR}/candidate.json" candidate
    candidate_id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["candidate"]["artifact_id"])' "${TMP_DIR}/candidate.json")"
    candidate_path="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["candidate"]["relative_path"])' "${TMP_DIR}/candidate.json")"
    [[ "${candidate_path}" == .pdflow/runs/${RUN_ID}/candidate/* ]] && ok "candidate path is run-scoped" || bad "candidate path escaped run scope"
    [[ "${candidate_id}" != "${ARTIFACT_ID}" ]] && ok "candidate has distinct artifact identity" || bad "candidate reused finish identity"
  else
    bad "candidate HTTP ${code}"
  fi
fi

code="$(request "${TMP_DIR}/bad-args.json" -X POST -H 'Content-Type: application/json' \
  -d "{\"action\":\"list\",\"operation\":\"action\",\"run_id\":\"${RUN_ID}\",\"args\":[\"unexpected\"]}" \
  "${BASE}/v1/jobs")"
[[ "${code}" == "400" ]] && ok "unregistered action arguments rejected" || bad "bad action args HTTP ${code}"

code="$(request "${TMP_DIR}/list-job.json" -X POST -H 'Content-Type: application/json' \
  -d "{\"action\":\"list\",\"operation\":\"action\",\"run_id\":\"${RUN_ID}\",\"variant\":\"flowlab\"}" \
  "${BASE}/v1/jobs")"
if [[ "${code}" == "202" ]]; then
  JOB_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["job_id"])' "${TMP_DIR}/list-job.json")"
  state="QUEUED"
  deadline=$(( $(date +%s) + 600 ))
  while [[ "${state}" == "QUEUED" || "${state}" == "RUNNING" ]]; do
    poll_code="$(request "${TMP_DIR}/job.json" "${BASE}/v1/jobs?id=${JOB_ID}")"
    [[ "${poll_code}" == "200" ]] || break
    state="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("state",""))' "${TMP_DIR}/job.json")"
    [[ "${state}" == "QUEUED" || "${state}" == "RUNNING" ]] || break
    [[ "$(date +%s)" -lt "${deadline}" ]] || break
    sleep 1
  done
  [[ "${state}" == "COMPLETED" ]] && assert_json "allowlisted action completes" "${TMP_DIR}/job.json" job_pass || bad "allowlisted action ended in ${state}"
else
  bad "list action HTTP ${code}"
fi

if [[ -n "${ARTIFACT_ID}" ]]; then
  code="$(request "${TMP_DIR}/gui-gap.json" -X POST -H 'Content-Type: application/json' \
    -d "{\"tool_id\":\"openroad\",\"operation\":\"gui\",\"artifact_id\":\"${ARTIFACT_ID}\",\"run_id\":\"${RUN_ID}\",\"mode\":\"view\"}" \
    "${BASE}/v1/jobs")"
  if [[ "${code}" == "202" ]]; then
    gui_state="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["state"])' "${TMP_DIR}/gui-gap.json")"
    if [[ "${gui_state}" == "GAP" ]]; then
      assert_json "native GUI dependency GAP" "${TMP_DIR}/gui-gap.json" job_gap
    elif [[ "${gui_state}" == "QUEUED" || "${gui_state}" == "RUNNING" ]]; then
      GUI_JOB_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["job_id"])' "${TMP_DIR}/gui-gap.json")"
      gui_code="$(request "${TMP_DIR}/gui-job.json" "${BASE}/v1/jobs?id=${GUI_JOB_ID}")"
      if [[ "${gui_code}" == "200" ]]; then
        gui_state="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("state", ""))' "${TMP_DIR}/gui-job.json")"
      else
        gui_state="ERROR"
        bad "native GUI status HTTP ${gui_code}"
      fi
      gui_deadline=$(( $(date +%s) + 15 ))
      while [[ "${gui_state}" == "QUEUED" && "$(date +%s)" -lt "${gui_deadline}" ]]; do
        sleep 1
        gui_code="$(request "${TMP_DIR}/gui-job.json" "${BASE}/v1/jobs?id=${GUI_JOB_ID}")"
        [[ "${gui_code}" == "200" ]] || break
        gui_state="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("state", ""))' "${TMP_DIR}/gui-job.json")"
      done
      if [[ "${gui_state}" == "RUNNING" ]]; then
        if python3 - "${TMP_DIR}/gui-job.json" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
assert "-db" in data["command"]
assert data.get("pid")
assert "couldn't read file" not in data.get("log_tail", "")
PY
        then
          ok "native OpenROAD GUI launched with live ODB"
        else
          bad "native OpenROAD GUI command or log"
        fi
        cancel_code="$(request "${TMP_DIR}/gui-cancel.json" -X POST -H 'Content-Type: application/json' \
          -d '{}' "${BASE}/v1/jobs/${GUI_JOB_ID}/cancel")"
        [[ "${cancel_code}" == "200" ]] || bad "native GUI cancel HTTP ${cancel_code}"
        gui_state="RUNNING"
        while [[ "${gui_state}" == "QUEUED" || "${gui_state}" == "RUNNING" ]]; do
          sleep 1
          gui_code="$(request "${TMP_DIR}/gui-job-final.json" "${BASE}/v1/jobs?id=${GUI_JOB_ID}")"
          [[ "${gui_code}" == "200" ]] || break
          gui_state="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("state", ""))' "${TMP_DIR}/gui-job-final.json")"
        done
        [[ "${gui_state}" == "CANCELLED" ]] && ok "native GUI cancel is orderly" || bad "native GUI ended in ${gui_state}"
      else
        bad "native OpenROAD GUI ended before RUNNING (${gui_state})"
      fi
    else
      bad "native GUI job ended in unexpected state ${gui_state}"
    fi
  else
    bad "GUI GAP HTTP ${code}"
  fi
fi

code="$(request "${TMP_DIR}/package.json" "${BASE}/v1/package?variant=flowlab")"
[[ "${code}" == "200" ]] && assert_json "package status is explicit" "${TMP_DIR}/package.json" package || bad "package HTTP ${code}"

code="$(request "${TMP_DIR}/ledger.json" "${BASE}/v1/path-ledger?variant=flowlab")"
[[ "${code}" == "200" ]] && assert_json "path ledger status is explicit" "${TMP_DIR}/ledger.json" ledger || bad "ledger HTTP ${code}"

code="$(request "${TMP_DIR}/compare.json" -X POST -H 'Content-Type: application/json' \
  -d '{}' "${BASE}/v1/compare")"
[[ "${code}" == "200" ]] && assert_json "comparison refuses missing provenance" "${TMP_DIR}/compare.json" compare || bad "compare HTTP ${code}"

code="$(request "${TMP_DIR}/refresh.json" -X POST -H 'Content-Type: application/json' -d '{}' "${BASE}/v1/refresh")"
[[ "${code}" == "200" ]] && assert_json "watcher refresh endpoint" "${TMP_DIR}/refresh.json" refresh || bad "refresh HTTP ${code}"

if [[ "${FAIL}" -ne 0 ]]; then
  echo "PDflow agent API SMOKE FAILED"
  exit 1
fi
echo "PDflow agent API SMOKE PASSED"
