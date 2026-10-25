#!/bin/sh
set -eu
case "$1" in
  c|d) cp "$2" "$3" ;;
  *) exit 64 ;;
esac
