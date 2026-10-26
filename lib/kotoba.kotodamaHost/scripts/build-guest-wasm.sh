#!/bin/sh
# scripts/build-guest-wasm.sh — JUN-149: guest モジュールを wasm32-browser
# （kototama-browser-host-v1 = :wasm32-browser-kotoba-v1）へビルドする。
# 使い方: sh scripts/build-guest-wasm.sh
# 1 モジュールずつ module-lock → compile（lock は内容アドレス blocks に積む）。
# 出力: dist/<module>.wasm + .provenance.edn + .publication.edn（JUN-128 の
# guest と同流儀で成果物と provenance は一緒に扱う）。
set -e
AMU=${AMU:-/Users/junkawasaki/github/kotoba-lang/amu/bin/amu}
TEXT_SRC=${TEXT_SRC:-/Users/junkawasaki/github/kotoba-lang/text/src}
mkdir -p blocks dist
for m in host_util host_types host_cadence host_model host_lexicon host_heartbeat; do
  echo "== $m"
  "$AMU" module-lock "src/kotodama/$m.cljk" --blocks blocks \
    --source-path src --source-path "$TEXT_SRC" >/dev/null
  "$AMU" compile "src/kotodama/$m.cljk" \
    --module-lock src/kotodama/kotoba.modules.edn --blocks blocks \
    --target wasm32-browser --output "dist/$m.wasm" | grep -o ':ok true' || exit 1
done
ls -la dist/*.wasm
