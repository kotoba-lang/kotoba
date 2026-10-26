#!/bin/sh
# The frozen-bigram model's relay-side check. The kernel-side decision moved
# to os/aiueos/kotoba/micro-infer-next.kotoba (ADR-0220); its evidence is
# contracts/micro-infer-next-v1.edn (task cfree-wave-2-contracts), seeded with
# the retired C's answers. What this smoke still does is keep the Mac relay's
# MURAKUMO_MICRO_INFER_ROWS identical to the matrix's source of truth,
# contracts/micro-infer-transitions-v1.edn.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
python3 "$repo/os/aiueos/tests/micro_infer_relay_model.py"
