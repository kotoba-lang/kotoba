#!/usr/bin/env bash
# Static packaging checks for the component-authority receiver.
# No root / no systemctl required — safe for CI and local.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
check() {
  local msg="$1"; shift
  if "$@"; then
    echo "ok  $msg"
  else
    echo "FAIL $msg" >&2
    fail=1
  fi
}

check "README runbook exists" test -f deploy/systemd/README.md
check "authority daemon wrapper exists" test -f deploy/bin/kototama-authority-daemon
check "authority service unit exists" test -f deploy/systemd/kototama-authority-daemon.service
check "authority config example exists" test -f deploy/systemd/component-authority.edn.example
check "authority wrapper help exits 0" \
  bash deploy/bin/kototama-authority-daemon --help >/dev/null
for key in Type=simple ExecStart= EnvironmentFile= ProtectSystem=; do
  check "authority service has $key" \
    grep -q "$key" deploy/systemd/kototama-authority-daemon.service
done

if [[ $fail -ne 0 ]]; then
  echo "packaging validation failed" >&2
  exit 1
fi
echo "packaging validation passed"
