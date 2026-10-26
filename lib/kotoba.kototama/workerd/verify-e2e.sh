#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
fixture="$root/workerd/fixtures"
log="${TMPDIR:-/tmp}/kototama-workerd-e2e.log"

wasm-tools parse "$fixture/guest.wat" -o "$fixture/guest.wasm"
cleanup() {
  if [[ -n "${workerd_pid:-}" ]]; then
    kill "$workerd_pid" 2>/dev/null || true
    for _ in {1..20}; do
      kill -0 "$workerd_pid" 2>/dev/null || break
      sleep 0.05
    done
    kill -KILL "$workerd_pid" 2>/dev/null || true
    wait "$workerd_pid" 2>/dev/null || true
  fi
  rm -f "$fixture/guest.wasm"
}
trap cleanup EXIT

"$root/node_modules/.bin/workerd" serve "$root/workerd/config.capnp" >"$log" 2>&1 &
workerd_pid=$!

for _ in {1..50}; do
  if response="$(curl --fail --silent http://127.0.0.1:18787/)"; then
    break
  fi
  if ! kill -0 "$workerd_pid" 2>/dev/null; then
    cat "$log"
    exit 1
  fi
  sleep 0.1
done

test "${response:-}" = \
  '{"result":"107","providerCalls":1,"runtime":"workerd-core","ambientWasi":false,"negativeChecks":2}'
