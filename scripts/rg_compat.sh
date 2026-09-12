#!/usr/bin/env bash
# Minimal ripgrep compatibility for the repository smoke suites.  The CI
# images normally provide rg; this keeps the checks usable on lean Linux
# hosts without changing their matching semantics.
if ! command -v rg >/dev/null 2>&1; then
  rg() {
    local grep_args=()
    local pattern=""
    local fixed=0
    local glob=""
    local positional_only=0
    local paths=()

    while [[ "$#" -gt 0 ]]; do
      if [[ "${positional_only}" -eq 1 ]]; then
        if [[ -z "${pattern}" ]]; then
          pattern="$1"
        else
          paths+=("$1")
        fi
        shift
        continue
      fi
      case "$1" in
        --)
          positional_only=1
          shift
          continue
          ;;
        --glob)
          [[ "$#" -ge 2 ]] || return 2
          glob="$2"
          shift 2
          ;;
        -F)
          fixed=1
          shift
          ;;
        -q|-n|-i|-c)
          grep_args+=("$1")
          shift
          ;;
        -qi|-iq)
          grep_args+=(-q -i)
          shift
          ;;
        -*)
          # The smoke suites only use the options handled above.  Keep an
          # unsupported option visible instead of silently changing a check.
          return 2
          ;;
        *)
          if [[ -z "${pattern}" ]]; then
            pattern="$1"
          else
            paths+=("$1")
          fi
          shift
          ;;
      esac
    done

    [[ -n "${pattern}" ]] || return 2

    local matcher=(-E)
    if [[ "${fixed}" -eq 1 ]]; then
      matcher=(-F)
    fi

    local recursive=()
    local include=()
    local path
    for path in "${paths[@]}"; do
      if [[ -d "${path}" ]]; then
        recursive=(-R)
        [[ -n "${glob}" ]] && include=("--include=${glob}")
        break
      fi
    done

    grep "${grep_args[@]}" "${matcher[@]}" "${recursive[@]}" "${include[@]}" \
      -- "${pattern}" "${paths[@]}"
  }
fi
