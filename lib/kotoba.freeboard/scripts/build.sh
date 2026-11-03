#!/usr/bin/env bash
# freeboard static authority surface. Runtime hosts consume the CLJC board model
# and render-IR directly; this repo no longer owns a shadow-cljs browser bundle.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$HERE/public"
echo "==> freeboard CLJC/render-IR authority is in src/"
echo "==> static fixture: $HERE/public/index.html"
