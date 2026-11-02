#!/bin/sh
set -eu
: "${AIUEOS_AMU_SOURCE:?set AIUEOS_AMU_SOURCE to the pinned Amu checkout}"
: "${TMPDIR:?set TMPDIR to a scratch directory under the workspace}"
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
runner="$here/../../scripts/run-native-generator.sh"
work=$(mktemp -d "$TMPDIR/flash-probe-file.XXXXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
# Strip only the namespace and test entry. The sampled functions used by the
# file fixture are the exact source that the component test executes.
sed '1,2d; /;; Native self-test/,$d' "$here/probe.kotoba" > "$work/generator.kotoba"
cat "$here/file-fixture.kotoba" >> "$work/generator.kotoba"
"$runner" "$work/generator.kotoba" "$work/result" --
[ "$(cat "$work/result")" = 'OK' ]
sed 's/(fixture-token nonce addr word))]/(+ 1 (fixture-token nonce addr word)))]/' "$work/generator.kotoba" > "$work/corrupt.kotoba"
if "$runner" "$work/corrupt.kotoba" "$work/corrupt-result" -- > "$work/control.log" 2>&1; then
  echo 'negative control unexpectedly passed' >&2; exit 1
fi
if [ -e "$work/corrupt-result" ]; then echo 'negative control produced output' >&2; exit 1; fi
if ! grep -q 'refused (exit 1)' "$work/control.log"; then cat "$work/control.log" >&2; exit 1; fi
printf '%s\n' 'native FS2 regular-file fixture: honest=0 wrap=detected; corruption control refused'
