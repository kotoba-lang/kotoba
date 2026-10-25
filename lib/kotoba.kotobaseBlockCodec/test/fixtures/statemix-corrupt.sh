#!/bin/sh
set -eu
case "$1" in
  c) cp "$2" "$3" ;;
  d) printf 'not-the-input' > "$3" ;;
  *) exit 64 ;;
esac
