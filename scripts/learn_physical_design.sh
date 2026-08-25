#!/usr/bin/env bash
# Corso interattivo completo di Physical Design con OpenROAD / ORFS.
#
# Uso:
#   ./scripts/learn_physical_design.sh --list
#   ./scripts/learn_physical_design.sh --lesson 01
#   ./scripts/learn_physical_design.sh --all
#   ./scripts/learn_physical_design.sh --resume
#   ./scripts/learn_physical_design.sh --status
#   ./scripts/learn_physical_design.sh --check
#   ./scripts/learn_physical_design.sh --auto --lesson 02   # senza pause
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export LEARN_ROOT="${ROOT}/learn"
export REPO_ROOT="${ROOT}"

# shellcheck source=learn/lib/ui.sh
source "${LEARN_ROOT}/lib/ui.sh"
# shellcheck source=learn/lib/orfs.sh
source "${LEARN_ROOT}/lib/orfs.sh"
# shellcheck source=learn/lib/progress.sh
source "${LEARN_ROOT}/lib/progress.sh"
# shellcheck source=learn/lib/validate.sh
source "${LEARN_ROOT}/lib/validate.sh"

LEARN_AUTO=0
LEARN_DEEP=0
LESSON=""
RUN_ALL=0
RESUME=0

usage() {
  cat <<'EOF'
Corso Physical Design — OpenROAD + ORFS

Opzioni:
  --list              Elenco lezioni
  --lesson ID         Esegue una lezione (es. 01, 03-floorplan, floorplan)
  --all               Percorso completo 00 → 07
  --resume            Riprende dall'ultima lezione incompleta
  --status            Mostra progresso salvato
  --check             Verifica prerequisiti e toolchain
  --auto              Salta le pause interattive
  --deep              Modalità approfondita: richiede lettura LAB.md per lezione
  --help              Questo messaggio

Esempi:
  ./scripts/learn_physical_design.sh --check
  ./scripts/learn_physical_design.sh --lesson 01-constraints
  ./scripts/learn_physical_design.sh --all

Documentazione estesa: learn/README.md e learn/CURRICULUM.md
EOF
}

list_lessons() {
  ui_banner "Corso Physical Design — Indice lezioni"
  find "${LEARN_ROOT}/lessons" -mindepth 1 -maxdepth 1 -type d | sort | while read -r d; do
    id="$(basename "${d}")"
    title="$(rg -m1 '^# ' "${d}/README.md" 2>/dev/null | sed 's/^# //' || echo "${id}")"
    printf "  %-18s %s\n" "${id}" "${title}"
  done
  echo
  ui_tip "Ogni lezione ha README.md (teoria) + run.sh (esercizi guidati)."
}

normalize_lesson_id() {
  local raw="$1"
  case "${raw}" in
    00|intro|00-intro) echo "00-intro" ;;
    01|constraints|01-constraints) echo "01-constraints" ;;
    02|synth|synthesis|02-synthesis) echo "02-synthesis" ;;
    03|floorplan|03-floorplan) echo "03-floorplan" ;;
    04|place|placement|04-placement) echo "04-placement" ;;
    05|cts|05-cts) echo "05-cts" ;;
    06|route|routing|06-routing) echo "06-routing" ;;
    07|finish|07-finish) echo "07-finish" ;;
    *)
      if [[ -d "${LEARN_ROOT}/lessons/${raw}" ]]; then
        echo "${raw}"
      else
        echo ""
      fi
      ;;
  esac
}

run_one_lesson() {
  local id="$1"
  local dir="${LEARN_ROOT}/lessons/${id}"
  if [[ ! -f "${dir}/run.sh" ]]; then
    ui_fail "Lezione non trovata: ${id}"
    exit 1
  fi
  # shellcheck source=/dev/null
  source "${dir}/run.sh"
  learn_prompt_lab "${id}"
  lesson_main
  learn_mark_complete "${id}"
}

all_lesson_ids() {
  find "${LEARN_ROOT}/lessons" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list) list_lessons; exit 0 ;;
    --lesson) LESSON="${2:-}"; shift 2 ;;
    --all) RUN_ALL=1; shift ;;
    --resume) RESUME=1; shift ;;
    --status) learn_show_progress; exit 0 ;;
    --check) learn_check_prerequisites; exit $? ;;
    --auto) LEARN_AUTO=1; export LEARN_AUTO; shift ;;
    --deep) LEARN_DEEP=1; export LEARN_DEEP; shift ;;
    --help|-h) usage; exit 0 ;;
    *) ui_fail "Opzione sconosciuta: $1"; usage; exit 1 ;;
  esac
done

learn_orfs_env
learn_progress_init

if [[ "${RUN_ALL}" == "1" ]]; then
  ui_banner "Percorso completo Physical Design"
  ui_warn "Durata totale stimata: 6–10 ore (con esercizi e GUI)."
  ui_confirm "Avviare tutte le lezioni in sequenza?" || exit 0
  while read -r id; do
    run_one_lesson "${id}"
  done < <(all_lesson_ids)
  ui_banner "Corso completato"
  learn_show_progress
  exit 0
fi

if [[ "${RESUME}" == "1" ]]; then
  last="$(python3 - "$(learn_progress_file)" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
done = set(d.get("completed_lessons", []))
for lid in ["00-intro","01-constraints","02-synthesis","03-floorplan","04-placement","05-cts","06-routing","07-finish"]:
    if lid not in done:
        print(lid)
        break
else:
    print("")
PY
)"
  if [[ -z "${last}" ]]; then
    ui_ok "Tutte le lezioni risultano già completate."
    learn_show_progress
    exit 0
  fi
  ui_note "Ripresa da lezione: ${last}"
  run_one_lesson "${last}"
  exit 0
fi

if [[ -z "${LESSON}" ]]; then
  usage
  exit 1
fi

id="$(normalize_lesson_id "${LESSON}")"
if [[ -z "${id}" ]]; then
  ui_fail "ID lezione non valido: ${LESSON}"
  list_lessons
  exit 1
fi

run_one_lesson "${id}"
