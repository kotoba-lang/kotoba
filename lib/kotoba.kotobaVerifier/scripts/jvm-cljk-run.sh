#!/bin/sh
# jvm-cljk-run.sh -- run a .cljk Clojure-family script on the REAL JVM.
#
# Usage: scripts/jvm-cljk-run.sh <script.cljk> [args...]
#
# Why this exists: this repository's sources are named `.cljk`
# (cljk-origin.edn, adr-2609111500), and the JVM clojure loader only looks
# for .clj/.cljc, so `clojure -M:test` on a tree of .cljk files reports
# "Ran 0 tests" without loading a single namespace -- a suite that cannot
# run does not look like a suite that ran. The established way to exercise
# the JVM host (the `:clj` reader branch, java.security Ed25519 in
# kotoba.verifier.signing) is the renamed-copy overlay described in
# amu's tee-guest-lessons.md: mirror every .cljk on the classpath as .cljc
# into a scratch overlay and run the script with that overlay first on the
# classpath. The script ITSELF is loaded by path, so it keeps its .cljk name.
#
# Environment: JAVA_CMD (default `java`) and CLOJURE_CMD (default `clojure`)
# name the real JVM toolchain. PATH shadowing (e.g. JVM-refusing stubs) is
# the caller's responsibility; this script does not rewrite PATH.
set -eu

if [ "$#" -lt 1 ]; then
  printf 'usage: %s <script.cljk> [args...]\n' "$0" >&2
  exit 64
fi

script=$1
shift

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
java_cmd=${JAVA_CMD:-java}
clojure_cmd=${CLOJURE_CMD:-clojure}

scratch=$(mktemp -d "${TMPDIR:-/tmp}/jvm-cljk.XXXXXX")
trap 'rm -rf "$scratch"' EXIT INT TERM
overlay="$scratch/ov"
mkdir -p "$overlay"

# The classpath the JVM would use (same gitlibs cache kbb resolves into),
# plus this repository's test tree -- the parity test namespaces live there.
cp=$(cd "$repo_root" && "$clojure_cmd" -Spath)
full_cp="$cp:$repo_root/test"

# Mirror every *.cljk as *.cljc, preserving paths under its own root -- .cljc
# is the extension the JVM loader reads WITH reader conditionals enabled
# (a plain .clj copy dies with "Conditional read not allowed", measured
# 2026-10-19). Files stay shared via symlink when possible.
old_ifs=$IFS
IFS=:
for root in $full_cp; do
  IFS=$old_ifs
  case "$root" in
    /*) dir=$root ;;
    *) dir=$repo_root/$root ;;
  esac
  [ -d "$dir" ] || continue
  find "$dir" -name '*.cljk' -type f 2>/dev/null | while read -r src; do
    rel=${src#"$dir"/}
    dest="$overlay/${rel%.cljk}.cljc"
    mkdir -p "$(dirname "$dest")"
    ln -sf "$src" "$dest" 2>/dev/null || cp "$src" "$dest"
  done
  IFS=:
done
IFS=$old_ifs

# The script is loaded through scripts/jvm-cljk-boot.clj, which pre-interns
# the :kotoba/export names clojure.core/ns would otherwise fail to resolve.
exec "$java_cmd" -cp "$overlay:$full_cp" clojure.main "$repo_root/scripts/jvm-cljk-boot.clj" "$overlay" "$script" "$@"
