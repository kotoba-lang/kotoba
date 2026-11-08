#!/bin/sh
# Oracle measurement for the kotoba.text twin (JUN-1044).
# One-off only: never a CI gate, build, runtime or fallback input.
# Runs the shared cases on babashka, nbb and Basilisp and requires
# byte-identical output.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$here/test"
SRC="$here/src"
export PYTHONDONTWRITEBYTECODE=1
bb -cp "$SRC:." run.cljc > /tmp/text_oracle_bb.txt 2>&1; echo "bb: $(tail -1 /tmp/text_oracle_bb.txt)"
nbb -cp "$SRC:." run.cljc > /tmp/text_oracle_nbb.txt 2>&1; echo "nbb: $(tail -1 /tmp/text_oracle_nbb.txt)"
basilisp run -p "$SRC" -p . run.cljc > /tmp/text_oracle_lpy.txt 2>&1; echo "basilisp: $(tail -1 /tmp/text_oracle_lpy.txt)"
cmp /tmp/text_oracle_bb.txt /tmp/text_oracle_nbb.txt
cmp /tmp/text_oracle_bb.txt /tmp/text_oracle_lpy.txt
echo "IDENTICAL across bb/nbb/basilisp"
