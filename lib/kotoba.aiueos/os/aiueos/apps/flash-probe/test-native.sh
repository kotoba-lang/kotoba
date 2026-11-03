#!/bin/sh
set -eu
: "${AMU:?set AMU to the Amu native CLI}"
: "${TMPDIR:?set TMPDIR to a scratch directory under the workspace}"
case "$AMU" in /*) ;; *) echo 'AMU must be an absolute path' >&2; exit 2;; esac
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
work=$(mktemp -d "$TMPDIR/flash-probe.XXXXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
actual=$("$AMU" run "$here/probe.kotoba")
[ "$actual" = 0 ] || { echo "native self-test failed: $actual" >&2; exit 1; }
# Negative control: an honest device substituted for a wraparound fixture
# must break the assertion. Only the staged copy is changed.
sed 's/model-mismatches 16 4 0 0/model-mismatches 16 16 0 0/' "$here/probe.kotoba" > "$work/negative.kotoba"
negative=$("$AMU" run "$work/negative.kotoba")
[ "$negative" = 1 ] || { echo "negative control not detected: $negative" >&2; exit 1; }
sed 's/(fixture-token nonce addr word))]/(+ 1 (fixture-token nonce addr word)))]/' "$here/probe.kotoba" > "$work/corrupt.kotoba"
corrupt=$("$AMU" run "$work/corrupt.kotoba")
[ "$corrupt" = 1 ] || { echo "write corruption control not detected: $corrupt" >&2; exit 1; }
printf '%s\n' 'flash probe native model: 28 assertions passed; two negative controls detected'
