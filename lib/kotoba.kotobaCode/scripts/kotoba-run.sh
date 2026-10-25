#!/bin/sh
# Operator guest-run after kotoba compile --target web.
# There is no kotoba -M.
#
# Measured on Release kotoba CLI v0.7.3:
# kotoba run kotoba/main.kotoba → kotoba/runtime-rejected (typed forms)
# Guest execution is instantiateKotoba on the emitted .mjs.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

if [ ! -s "target/kotoba/main.mjs" ]; then
  echo "missing target/kotoba/main.mjs" >&2
  echo "compile first: sh scripts/kotoba-compile.sh" >&2
  if ! command -v kotoba >/dev/null 2>&1; then
    echo "kotoba CLI is not on PATH. Could not run:" >&2
    echo "  kotoba compile kotoba/main.kotoba --target web --output target/kotoba/main.mjs --json" >&2
  fi
  exit 127
fi

exec node scripts/kotoba-guest-run.mjs
