#!/bin/sh
set -eu

command -v clojure >/dev/null 2>&1 || { echo "build-native: clojure is required at build time" >&2; exit 1; }
command -v native-image >/dev/null 2>&1 || { echo "build-native: GraalVM native-image is required" >&2; exit 1; }

clojure -T:build uber
mkdir -p target/native
native-image \
  --no-fallback \
  -H:+ReportExceptionStackTraces \
  -jar target/kotoba-standalone.jar \
  target/native/kotoba

target/native/kotoba selfhost check --json >/dev/null
