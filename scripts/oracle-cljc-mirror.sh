#!/bin/sh
# Generated .cljc mirrors of selected libraries, for hosts that do not read
# .cljk (ClojureScript, JVM Clojure, nbb) — first consumer: the Awai Otehon
# studio bundle (network-awai ADR 0026 D18, AWAI-215).
#
# For each library below, lib/<lib>/src/**/*.cljk is copied byte-for-byte to
# lib/<lib>/oracle/cljc/src/**/*.cljc. The .cljk sources stay canonical; never
# edit a mirror. Mirrors live under the library's oracle/ because native
# Kotoba rejects .clj/.cljc/.cljs anywhere else (JUN-579), and they are not on
# any native gate, build, CI or runtime path (AGENTS.md "CDCI").
#
# Hand-curated oracle twins are the exception: where the byte mirror cannot
# load on a measured host, a curated twin takes its place, listed below as
# "<lib>:<path under oracle/cljc/src>". Curated files are never rewritten
# and never flagged by --check; their rationale lives in that oracle's
# README.md (first: kotoba.text, JUN-1044 — nbb prefers the sibling .cljk,
# Basilisp rejects the mirror's {:kotoba/export} metadata).
#
#   scripts/oracle-cljc-mirror.sh          rewrite the mirrors
#   scripts/oracle-cljc-mirror.sh --check  exit 1 if any mirror is stale or has extra files
set -eu
cd "$(dirname "$0")/.."

LIBS="kotoba.text kotoba.css kotoba.jpGoDigitalDesignSystem"

CURATED="kotoba.text:kotoba/lang/text.cljc"

check=${1:-}
status=0
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

for lib in $LIBS; do
  src=lib/$lib/src
  out=lib/$lib/oracle/cljc/src
  : >"$tmp/expected"
  find "$src" -name '*.cljk' | LC_ALL=C sort >"$tmp/sources"
  while read -r f; do
    rel=${f#"$src"/}
    dst="$out/${rel%.cljk}.cljc"
    echo "$dst" >>"$tmp/expected"
    orel=${dst#"$out"/}
    case " $CURATED " in
      *" $lib:$orel "*) continue ;;
    esac
    if [ "$check" = "--check" ]; then
      cmp -s "$f" "$dst" || { echo "STALE $dst" >&2; status=1; }
    else
      mkdir -p "$(dirname "$dst")"
      cmp -s "$f" "$dst" 2>/dev/null || cp "$f" "$dst"
    fi
  done <"$tmp/sources"
  if [ -d "$out" ]; then
    find "$out" -type f | LC_ALL=C sort >"$tmp/present"
    while read -r dst; do
      grep -qxF "$dst" "$tmp/expected" && continue
      if [ "$check" = "--check" ]; then
        echo "EXTRA $dst" >&2; status=1
      else
        rm "$dst"
      fi
    done <"$tmp/present"
    [ "$check" = "--check" ] || find "$out" -type d -empty -delete
  fi
done

if [ "$status" -ne 0 ]; then
  echo "oracle/cljc mirrors are out of date; run scripts/oracle-cljc-mirror.sh" >&2
fi
exit "$status"
