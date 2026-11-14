#!/usr/bin/env bash
# Full-stack preflight via scripts/lib/stack_check.py
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

YES=0
STRICT=0
CI_FLAG=0
if [[ "${CI:-}" == "true" ]] || [[ "${CHECK_ENV_CI:-}" == "1" ]]; then
  CI_FLAG=1
  YES=1
fi
for arg in "$@"; do
  case "$arg" in
    -y|--yes) YES=1 ;;
    --strict) STRICT=1 ;;
  esac
done

ctx7_warn() {
  local tech_name=$1
  local msg=$2
  echo ""
  printf '\033[43;30m CONTEXT7 \033[0m \033[43;30m %s \033[0m\n' "$tech_name"
  printf '\033[33m%s\033[0m\n' "$msg"
  printf '\033[33m%s\033[0m\n' "Investigate official docs before confirming deployment."
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
    if command -v "$bin" >/dev/null 2>&1; then
      echo "$bin"
      return 0
    fi
  done
  return 1
}

PY_CMD=$(pick_python) || {
  echo "ERROR: Python required to run scripts/lib/stack_check.py"
  exit 1
}

ARGS=()
(( YES )) && ARGS+=(-y)
(( STRICT )) && ARGS+=(--strict)
(( CI_FLAG )) && ARGS+=(--ci)

# shellcheck disable=SC2207
PARTS=($PY_CMD)
set +e
OUTPUT=$("${PARTS[@]}" "$ROOT/scripts/lib/stack_check.py" "${ARGS[@]}" 2>&1)
CODE=$?
set -e

while IFS= read -r line; do
  if [[ "$line" =~ ^@CTX7\|([^|]+)\|([^|]+)\|(.+)$ ]]; then
    ctx7_warn "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}"
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
