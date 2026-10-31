#!/usr/bin/env bash
set -euo pipefail

# Only audited manifest IDs are accepted. The Clojure verifier resolves every
# file through its immutable 40-character revision and rejects hash/size drift.
exec kbb -M:dataset -m verify-external-dataset "${1:-aethron-cfd-pinn}"
