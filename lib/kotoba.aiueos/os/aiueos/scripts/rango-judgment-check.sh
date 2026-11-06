#!/bin/sh
# usage: rango-judgment-check.sh AMU -- run the self-check of the two rango judgment modules natively with AMU
# (native/rango_touch.kotoba and native/bcm_hcd.kotoba) and require every bit. Hosted only: no device, no QEMU,
# and neither module is linked into an image. A copy of each module is made with its export list replaced by `main`,
# because `amu run` takes one source with one exported main. JUN-862.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
native=$(CDPATH= cd -- "$here/../native" && pwd)
amu=$1
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
run() {
  name=$1 want=$2
  sed 's/(:export \[[^]]*\])/(:export [main])/' "$native/$name.kotoba" > "$tmp/$name.kotoba"
  printf '(defn main [] :i64 (self-check))\n' >> "$tmp/$name.kotoba"
  "$amu" check "$tmp/$name.kotoba" >/dev/null
  got=$("$amu" run "$tmp/$name.kotoba")
  echo "$name self-check $got want $want"
  test "$got" = "$want"
}
run rango_touch 8388607
run bcm_hcd 1048575
echo "RANGO_JUDGMENT_OK"
