#!/usr/bin/env bash
# Compare docs/stack-requirements.json vs discovered manifest stack
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

INIT=0
SUMMARY=""
REQ_PATH="docs/stack-requirements.json"
for arg in "$@"; do
  case "$arg" in
    --init) INIT=1 ;;
    --summary=*) SUMMARY="${arg#*=}" ;;
    -r|--requirements) shift; REQ_PATH="${1:-$REQ_PATH}" ;;
  esac
done

gap_warn() {
  local tech_name=$1
  local msg=$2
  echo ""
  printf '\033[43;30m REQUIREMENTS GAP \033[0m \033[43;30m %s \033[0m\n' "$tech_name"
  printf '\033[33m%s\033[0m\n' "$msg"
  printf '\033[33m%s\033[0m\n' "Add to manifests or update docs/stack-requirements.json before deploy."
  echo ""
}

pick_python() {
  local tag bin
  if command -v py >/dev/null 2>&1; then
    for tag in 3.13 3.12 3.11 3.10 3.9; do
      if py -"$tag" -c "import sys" 2>/dev/null; then
        echo "py -$tag"
        return 0
      fi
    done
  fi
  for bin in python3.12 python3 python; do
    command -v "$bin" >/dev/null 2>&1 && echo "$bin" && return 0
  done
  return 1
}

PY_CMD=$(pick_python) || { echo "ERROR: Python required"; exit 1; }
# shellcheck disable=SC2207
PARTS=($PY_CMD)

ARGS=(--requirements "$REQ_PATH")
(( INIT )) && ARGS+=(--init)
[[ -n "$SUMMARY" ]] && ARGS+=(--summary "$SUMMARY")

set +e
OUTPUT=$("${PARTS[@]}" "$ROOT/scripts/lib/stack_requirements.py" "${ARGS[@]}" 2>&1)
CODE=$?
set -e

while IFS= read -r line; do
  if [[ "$line" =~ ^@GAP\|([^|]+)\|([^|]+)\|(.+)$ ]]; then
    gap_warn "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}"
  elif [[ "$line" =~ ^@REQ_OK\|(.+)$ ]]; then
    echo "REQ OK: ${BASH_REMATCH[1]}"
  elif [[ "$line" =~ ^@OK\|(.+)$ ]]; then
    echo "OK: ${BASH_REMATCH[1]}"
  elif [[ "$line" =~ ^@WARN\|(.+)$ ]]; then
    echo "WARNING: ${BASH_REMATCH[1]}"
  elif [[ "$line" =~ ^@ERR\|(.+)$ ]]; then
    echo "ERROR: ${BASH_REMATCH[1]}"
  elif [[ "$line" =~ ^@INFO\|(.+)$ ]]; then
    echo "INFO: ${BASH_REMATCH[1]}"
  else
    echo "$line"
  fi
done <<< "$OUTPUT"

exit "$CODE"
