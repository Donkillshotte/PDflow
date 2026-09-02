#!/usr/bin/env bash
# Course progress tracking.

learn_progress_file() {
  echo "${LEARN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/.progress.json"
}

learn_progress_init() {
  local pf
  pf="$(learn_progress_file)"
  if [[ ! -f "${pf}" ]]; then
    cat >"${pf}" <<EOF
{
  "started_at": "$(date -Iseconds)",
  "completed_lessons": [],
  "last_lesson": null,
  "notes": []
}
EOF
  fi
}

learn_mark_complete() {
  local lesson_id="$1"
  learn_progress_init
  python3 - "${lesson_id}" "$(learn_progress_file)" <<'PY'
import json, sys, datetime
lesson, path = sys.argv[1], sys.argv[2]
with open(path) as f:
    data = json.load(f)
done = set(data.get("completed_lessons", []))
done.add(lesson)
data["completed_lessons"] = sorted(done)
data["last_lesson"] = lesson
data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
with open(path, "w") as f:
    json.dump(data, f, indent=2)
PY
  ui_ok "Lesson ${lesson_id} marked complete."
}

learn_show_progress() {
  learn_progress_init
  ui_section "Course progress"
  python3 - "$(learn_progress_file)" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
print("  Started:", d.get("started_at", "?"))
print("  Last lesson:", d.get("last_lesson", "(none)"))
print("  Completed:", ", ".join(d.get("completed_lessons", [])) or "(none)")
PY
}

learn_is_complete() {
  local lesson_id="$1"
  learn_progress_init
  python3 - "${lesson_id}" "$(learn_progress_file)" <<'PY'
import json, sys
lesson, path = sys.argv[1], sys.argv[2]
with open(path) as f:
    d = json.load(f)
raise SystemExit(0 if lesson in d.get("completed_lessons", []) else 1)
PY
}
