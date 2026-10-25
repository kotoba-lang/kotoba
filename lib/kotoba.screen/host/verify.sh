#!/usr/bin/env bash
# host/verify.sh — run the screen library golden vectors through the native path.
#
# Prereqs (measured 2026-09-03):
#   1. amu repo at ../amu (sibling checkout)
#   2. a runtime measurement + loader from amu's measure-runtime:
#        cd ../amu && bin/amu measure-runtime --output /tmp/runtime.edn \
#          --loader-output /tmp/kotoba-loader
#      then paste the printed :runtime-sha256 into host/verify.cljk's
#      :trusted-runtime-sha256 (native execution is never trust-on-first-use).
#   3. JVM (the test driver only — the guest itself is JVM-free).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
AMU="$(cd "$HERE/../.." && pwd)/amu"   # adjust if amu lives elsewhere

CP="/tmp:$(cd "$AMU" && kbb -Spath -M:native-run)"

java -cp "$CP" clojure.main -e "(require 'screen-verify) (screen-verify/-main)"
