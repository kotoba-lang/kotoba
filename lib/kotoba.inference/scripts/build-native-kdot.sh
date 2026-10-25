#!/usr/bin/env sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$root/target/native"

case "$(uname -s)" in
  Darwin) out="$root/target/native/libkotodama_kdot.dylib" ;;
  Linux) out="$root/target/native/libkotodama_kdot.so" ;;
  *) echo "unsupported native kdot platform: $(uname -s)" >&2; exit 2 ;;
esac

cc -O3 -std=c11 -fPIC -pthread -shared "$root/native/kotodama_kdot.c" -o "$out"
printf '%s\n' "$out"
