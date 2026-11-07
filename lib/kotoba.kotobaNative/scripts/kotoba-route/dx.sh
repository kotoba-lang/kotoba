#!/bin/zsh
H=$(cd "$(dirname "$0")" && pwd)
# dx.sh FN... : differential of the Kotoba twins of FN... (compiled natively, run by the C loader) against host recordings
# cases: $S/cases/<FN>.edn, one `[args... expected]` per line (mi/write-cases!)
S=${KR_WORK:-/tmp/kotoba-route}; H=$(cd "$(dirname "$0")" && pwd)
G=$S/guest/src/kotoba/native; mkdir -p $G $S/dxout
rsync -a --delete $S/ov/src/ $S/guest/src/
# guest-only: aggregate_abi's Kotoba arms never call kotoba.lang.coll, whose typed keyword sets are not native yet
sed -i '' 's/(:require \[kotoba.lang.coll :as set\])/(:require #?@(:kotoba [] :default [[kotoba.lang.coll :as set]]))/' $S/guest/src/kotoba/native/aggregate_abi.cljk
ROOT=${ROOT:-machine_ir}
OVDIR=$S/ov/src TWDIR=$S/twins GUESTDIR=$S/guest/src python3 $H/gen-guest.py $ROOT "$@" || exit 1
t0=$(date +%s)
if [ -n "$NOCOMPILE" ]; then r="{:offset $(cat $S/dxout/offset)"; else r=$($H/j.sh "(in-ns 'mi) (prn (compile-guest \"$G/$ROOT.cljk\" \"$S/dxout/guest\" [] [3 37 41]))" | grep -o '{:offset [0-9]*\|{:refused.*' | head -1); fi
t1=$(date +%s)
echo "compile: $(( t1 - t0 ))s $r" | cut -c1-600
off=$(echo $r | grep -o '[0-9]*$')
[ -z "$off" ] && exit 1
echo $off > $S/dxout/offset
rm -f $S/dxout/answers $S/dxout/inputs $S/dxout/traps
if [ -n "$DX_INPUTS" ]; then cp $DX_INPUTS $S/dxout/inputs; else
for spec in "$@"; do fn=${spec%:a}; sed "s/^/$fn /" $S/cases/$fn.edn | grep -v "^$fn $" >> $S/dxout/inputs; done; fi
python3 $H/dxrun.py $S/dxout/guest.bin $off $S/dxout/inputs $S/dxout/verdicts
t2=$(date +%s)
echo "run: $(( t2 - t1 ))s"
sort $S/dxout/verdicts | uniq -c
