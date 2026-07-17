#!/bin/sh
set -eu

command -v clojure >/dev/null 2>&1 || { echo "build-native: clojure is required at build time" >&2; exit 1; }
command -v native-image >/dev/null 2>&1 || { echo "build-native: GraalVM native-image is required" >&2; exit 1; }

clojure -T:build uber
jar tf target/kotoba-standalone.jar | grep -q '^kotoba/launcher.class$' || {
  echo "build-native: AOT main class missing from uberjar" >&2
  exit 1
}
mkdir -p target/native
native-image \
  --no-fallback \
  -H:+ReportExceptionStackTraces \
  --features=clj_easy.graal_build_time.InitClojureClasses \
  '-H:IncludeResources=.*\.(clj|cljc|edn)$' \
  -jar target/kotoba-standalone.jar \
  target/native/kotoba

target/native/kotoba selfhost check --json >/dev/null
