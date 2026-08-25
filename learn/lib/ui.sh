#!/usr/bin/env bash
# Funzioni di interfaccia utente per il corso di physical design.

if [[ -t 1 ]]; then
  C_RESET='\033[0m'
  C_BOLD='\033[1m'
  C_DIM='\033[2m'
  C_RED='\033[0;31m'
  C_GREEN='\033[0;32m'
  C_YELLOW='\033[0;33m'
  C_BLUE='\033[0;34m'
  C_CYAN='\033[0;36m'
  C_MAGENTA='\033[0;35m'
else
  C_RESET='' C_BOLD='' C_DIM='' C_RED='' C_GREEN='' C_YELLOW=''
  C_BLUE='' C_CYAN='' C_MAGENTA=''
fi

ui_banner() {
  local title="$1"
  echo
  echo -e "${C_BOLD}${C_CYAN}════════════════════════════════════════════════════════════════${C_RESET}"
  echo -e "${C_BOLD}${C_CYAN}  ${title}${C_RESET}"
  echo -e "${C_BOLD}${C_CYAN}════════════════════════════════════════════════════════════════${C_RESET}"
  echo
}

ui_section() {
  echo
  echo -e "${C_BOLD}${C_BLUE}── $1 ──${C_RESET}"
  echo
}

ui_step() {
  echo -e "${C_BOLD}${C_GREEN}▶ Step $1${C_RESET} ${C_DIM}— $2${C_RESET}"
}

ui_tip() {
  echo -e "${C_YELLOW}💡 Suggerimento:${C_RESET} $1"
}

ui_note() {
  echo -e "${C_DIM}ℹ $1${C_RESET}"
}

ui_warn() {
  echo -e "${C_YELLOW}⚠ Attenzione:${C_RESET} $1"
}

ui_ok() {
  echo -e "${C_GREEN}✔ $1${C_RESET}"
}

ui_fail() {
  echo -e "${C_RED}✖ $1${C_RESET}"
}

ui_code() {
  echo -e "${C_DIM}\`\`\`${C_RESET}"
  sed 's/^/  /' <<<"$1"
  echo -e "${C_DIM}\`\`\`${C_RESET}"
}

ui_pause() {
  local msg="${1:-Premi INVIO per continuare...}"
  if [[ "${LEARN_AUTO:-0}" == "1" ]]; then
    ui_note "(modalità automatica: pausa saltata)"
    return 0
  fi
  echo
  read -r -p "$(echo -e "${C_MAGENTA}${msg}${C_RESET}") " _
}

learn_prompt_lab() {
  local lesson_id="$1"
  local lab="${LEARN_ROOT}/lessons/${lesson_id}/LAB.md"
  if [[ ! -f "${lab}" ]]; then
    return 0
  fi
  ui_section "Laboratorio esteso — LAB.md"
  ui_note "File: ${lab}"
  ui_note "Il run.sh è una guida rapida; il LAB contiene esercizi da 60–120 min."
  if [[ "${LEARN_DEEP:-0}" == "1" ]]; then
    ui_warn "Modalità --deep: leggi il LAB per intero prima di procedere."
    ui_print_file "Anteprima LAB" "${lab}" 45
    ui_pause "Premi INVIO dopo aver letto il LAB completo..."
  else
    ui_tip "Usa --deep per forzare la lettura guidata del LAB."
  fi
}

ui_confirm() {
  local msg="${1:-Continuare?}"
  if [[ "${LEARN_AUTO:-0}" == "1" ]]; then
    return 0
  fi
  read -r -p "$(echo -e "${C_YELLOW}${msg} [s/N] ${C_RESET}")" ans
  [[ "${ans,,}" == "s" || "${ans,,}" == "si" || "${ans,,}" == "y" || "${ans,,}" == "yes" ]]
}

ui_lesson_header() {
  local num="$1" title="$2" duration="$3"
  ui_banner "Lezione ${num}: ${title}"
  ui_note "Durata stimata: ${duration}"
  ui_note "Design: gcd @ nangate45 | Variante flusso: learn"
  echo
}

ui_print_file() {
  local label="$1" path="$2" max="${3:-40}"
  ui_note "${label}: ${path}"
  if [[ -f "${path}" ]]; then
    echo -e "${C_DIM}--- inizio file (prime ${max} righe) ---${C_RESET}"
    head -n "${max}" "${path}" | sed 's/^/  /'
    echo -e "${C_DIM}--- fine estratto ---${C_RESET}"
  else
    ui_warn "File non trovato (verrà creato durante l'esercizio)."
  fi
}
