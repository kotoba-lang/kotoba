#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

rustup target add wasm32-unknown-unknown >/dev/null
RUSTFLAGS='--cfg getrandom_backend="wasm_js"' \
  cargo build --release --target wasm32-unknown-unknown \
    -p actor_runtime_integrity \
    -p actor_runtime

HC_AGENT_RUNTIME_ROOT="${ROOT_DIR}" \
  cargo run --release -p holochain-agent-runtime-call-zome-smoke
