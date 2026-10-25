#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
script="$repo_root/python/isaac_sim_6_smoke.py"

if [[ -n "${ISAACSIM_PYTHON:-}" ]]; then
  exec "$ISAACSIM_PYTHON" "$script" "$@"
fi

if [[ -n "${ISAACSIM_PATH:-}" && -x "${ISAACSIM_PATH}/python.sh" ]]; then
  exec "${ISAACSIM_PATH}/python.sh" "$script" "$@"
fi

cat >&2 <<'EOF'
Isaac Sim's Python launcher was not found.
Set ISAACSIM_PATH to an Isaac Sim 6.0 installation, or set ISAACSIM_PYTHON to
its configured Python interpreter (for example: /path/to/isaac-sim/python.sh).
EOF
exit 2
