#!/bin/bash
# SessionStart hook — etzhayyim/kotoba
#
# Bootstraps the Rust + IPFS toolchain so a Claude Code on the web session can
# build, test, and run kotoba (incl. the real-Kubo IPFS cold-tier E2E path)
# WITHOUT any secrets touching the cloud container.
#
# What it installs (all idempotent, all from public sources — no credentials):
#   - rustup wasm32-unknown-unknown target   (kotoba-store-web / WASM runtime)
#   - wasm-tools                              (validate WASM components)
#   - kubo (ipfs)                             (KuboBlockStore cold tier, CID, CAR)
#   - an OFFLINE ipfs repo                    (--only-hash / dag export, no daemon)
#
# For the real-Kubo E2E tests (TieredBlockStore<…, KuboIpfs>) a daemon is
# needed; this hook only installs kubo + inits an offline repo. Start a daemon
# yourself when a test needs one:  `ipfs daemon --offline &`  (no peers, no net).
#
# Deliberately NOT done (operating-entity / no-server-key boundary):
#   - no IPFS-pin / Cloudflare / fleet credentials (those live in GitHub Actions)
#   - on-chain settlement / DID signing stays etzhayyim-exclusive (operator step)
#
# Runs only in the remote (web) environment. Local Macs already have the toolchain.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  echo "session-start: not a remote session — skipping toolchain bootstrap"
  exit 0
fi

BIN_DIR="/usr/local/bin"
WASM_TOOLS_VER="1.225.0"
KUBO_VER="v0.34.1"
ARCH="$(uname -m)"

log() { echo "session-start: $*"; }

# ── 1. Rust wasm32 target ────────────────────────────────────────────────────
if command -v rustup >/dev/null 2>&1; then
  if ! rustup target list --installed 2>/dev/null | grep -q '^wasm32-unknown-unknown$'; then
    log "adding rust target wasm32-unknown-unknown"
    rustup target add wasm32-unknown-unknown
  else
    log "wasm32-unknown-unknown target already present"
  fi
else
  log "WARN: rustup not found — WASM builds will be unavailable"
fi

# ── 2. wasm-tools (validate WASM components) ──────────────────────────────────
if ! command -v wasm-tools >/dev/null 2>&1; then
  log "installing wasm-tools ${WASM_TOOLS_VER}"
  tmp="$(mktemp -d)"
  url="https://github.com/bytecodealliance/wasm-tools/releases/download/v${WASM_TOOLS_VER}/wasm-tools-${WASM_TOOLS_VER}-${ARCH}-linux.tar.gz"
  if curl -sSL -o "$tmp/wt.tar.gz" "$url" && tar xzf "$tmp/wt.tar.gz" -C "$tmp"; then
    cp "$tmp/wasm-tools-${WASM_TOOLS_VER}-${ARCH}-linux/wasm-tools" "$BIN_DIR/" && log "wasm-tools installed: $(wasm-tools --version)"
  else
    log "WARN: wasm-tools download failed"
  fi
  rm -rf "$tmp"
else
  log "wasm-tools already present: $(wasm-tools --version)"
fi

# ── 3. kubo / ipfs (KuboBlockStore cold tier + deterministic CID/CAR) ────────
if ! command -v ipfs >/dev/null 2>&1; then
  log "installing kubo ${KUBO_VER}"
  tmp="$(mktemp -d)"
  url="https://dist.ipfs.tech/kubo/${KUBO_VER}/kubo_${KUBO_VER}_linux-amd64.tar.gz"
  if curl -sSL -o "$tmp/kubo.tar.gz" "$url" && tar xzf "$tmp/kubo.tar.gz" -C "$tmp"; then
    cp "$tmp/kubo/ipfs" "$BIN_DIR/" && log "kubo installed: $(ipfs --version)"
  else
    log "WARN: kubo download failed — IPFS-backed tests will be unavailable"
  fi
  rm -rf "$tmp"
else
  log "kubo already present: $(ipfs --version)"
fi

# ── 4. Offline IPFS repo (no daemon, no network, no peers) ───────────────────
export IPFS_PATH="${IPFS_PATH:-$HOME/.ipfs}"
if command -v ipfs >/dev/null 2>&1 && [ ! -f "$IPFS_PATH/config" ]; then
  log "initializing offline ipfs repo at $IPFS_PATH"
  ipfs init --profile=lowpower >/dev/null 2>&1 || log "WARN: ipfs init failed"
fi
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export IPFS_PATH=\"$IPFS_PATH\"" >> "$CLAUDE_ENV_FILE"
fi

log "toolchain ready — cargo test + WASM + real-Kubo IPFS path enabled (deploy is operator/CI-driven)"
