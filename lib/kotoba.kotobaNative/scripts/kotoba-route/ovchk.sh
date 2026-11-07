#!/bin/zsh
H=$(cd "$(dirname "$0")" && pwd)
# ovchk.sh : overlay both owned files and run the native checker on each
S=${KR_WORK:-/tmp/kotoba-route}; H=$(cd "$(dirname "$0")" && pwd)
FILES=${@:-machine_ir aarch64}
N=/private/tmp/wt-D-kotoba-native/src
mkdir -p $S/ov/src; rsync -a --delete $N/ $S/ov/src/
for f in machine_ir aarch64; do
  python3 $H/ov.py overlay $N/kotoba/native/$f.cljk $S/ov/src/kotoba/native/$f.cljk
done
for f in ${=FILES}; do
  r=$(MI_CP=$S/cp-ov.txt MI_HEAD=4000 $H/chk.sh $S/ov/src/kotoba/native/$f.cljk)
  if echo "$r" | grep -q ':ok true\|:format :kotoba.check/v1'; then echo "$f OK"; else echo "$f: $(echo $r | grep -o ':message "[^"]*' | cut -c11-400) $(echo $r | grep -o ':span {[^}]*}')"; fi
done
