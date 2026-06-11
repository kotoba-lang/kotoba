#!/bin/sh
# Wrapper for the launchd-driven social-economy tick (ADR-2606082100).
# Sources the env file next to it, then execs the built tick binary.
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SOCIAL_ECONOMY_ENV:-$HERE/social-economy.env}"

if [ -f "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
else
  echo "run-tick: no env file at $ENV_FILE — tick will run its FAKE demo" >&2
fi

BIN="${KOTOBA_TICK_BIN:-}"
if [ -z "$BIN" ] || [ ! -x "$BIN" ]; then
  echo "run-tick: KOTOBA_TICK_BIN not set / not executable ($BIN)" >&2
  echo "  build it: cargo build --release --example social_economy_tick -p kotoba-server" >&2
  exit 1
fi

exec "$BIN"
