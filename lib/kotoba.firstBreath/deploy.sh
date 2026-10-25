#!/usr/bin/env bash
# deploy.sh — install first-breath cell on a mini via SSH (cron @60s heartbeat).
#
# Idempotent: re-running updates the script + crontab; existing state.edn is preserved.
#
# Usage:
#   ./deploy.sh <ssh-host> <ssh-user> [<rpc-url>] [<anchor-addr>]
#   ./deploy.sh judahnomac-mini.local judah http://192.168.1.9:8545 0x5fbdb...

set -euo pipefail

HOST="${1:?usage: deploy.sh <ssh-host> <ssh-user> [<rpc-url>] [<anchor-addr>]}"
USER="${2:?usage: deploy.sh <ssh-host> <ssh-user> [<rpc-url>] [<anchor-addr>]}"
RPC="${3:-http://192.168.1.9:8545}"
ANCHOR="${4:-0x5fbdb2315678afecb367f032d93f642f64180aa3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[deploy] target: $USER@$HOST"
echo "[deploy] rpc:    $RPC"
echo "[deploy] anchor: $ANCHOR"

# 1) ensure babashka (bb) + create cell dir
ssh -o StrictHostKeyChecking=accept-new "$USER@$HOST" bash -s <<'REMOTE_BOOTSTRAP'
set -e
if ! command -v bb >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/bb" ]; then
  curl -sL https://raw.githubusercontent.com/babashka/babashka/master/install -o /tmp/bb-install
  bash /tmp/bb-install --dir "$HOME/.local/bin" > /dev/null 2>&1
  rm -f /tmp/bb-install
fi
mkdir -p ~/etzhayyim/first-breath
REMOTE_BOOTSTRAP

# 2) scp the cell source (cljc + its standalone bb.edn; no python/uv)
scp -o StrictHostKeyChecking=accept-new \
  "$SCRIPT_DIR/README.md" \
  "$SCRIPT_DIR/bb.edn" \
  "$SCRIPT_DIR/breath.cljk" \
  "$SCRIPT_DIR/.gitignore" \
  "$USER@$HOST:~/etzhayyim/first-breath/" > /dev/null

# 3) first breath smoke (kbb -M:fetches the eth-crypto-clj git dep) + install cron @60s
ssh "$USER@$HOST" bash -s -- "$USER" "$RPC" "$ANCHOR" <<'REMOTE_INSTALL'
set -e
USER_=$1; RPC=$2; ANCHOR=$3
export PATH=$HOME/.local/bin:$PATH
cd ~/etzhayyim/first-breath
ETZ_RPC="$RPC" ETZ_ANCHOR="$ANCHOR" kbb breath.cljk | tail -3

# Install crontab (cd into the cell dir so bb resolves the local bb.edn)
crontab -l 2>/dev/null | grep -v 'first-breath/breath' | grep -v '^ETZ_' > /tmp/cron.bak || true
cat /tmp/cron.bak > /tmp/cron.new
cat >> /tmp/cron.new <<CRON
ETZ_RPC=$RPC
ETZ_ANCHOR=$ANCHOR
* * * * * cd /Users/$USER_/etzhayyim/first-breath && /Users/$USER_/.local/bin/bb breath.cljk >> /Users/$USER_/etzhayyim/first-breath/breath.log 2>&1
CRON
crontab /tmp/cron.new
echo "[deploy] cron installed on $USER_@$(hostname -s)"
REMOTE_INSTALL

echo "[deploy] $USER@$HOST DONE — first breath above, cron @60s active"
