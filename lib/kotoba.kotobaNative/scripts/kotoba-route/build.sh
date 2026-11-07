#!/bin/zsh
H=$(cd "$(dirname "$0")" && pwd)
# build.sh: regenerate the owned files from pristine host + twins, then overlay-check
S=${KR_WORK:-/tmp/kotoba-route}; H=$(cd "$(dirname "$0")" && pwd)
N=/private/tmp/wt-D-kotoba-native/src/kotoba/native
for f in machine_ir aarch64; do
  [ -f $S/twins/$f.cljk ] && { python3 $H/merge.py $S/host/$f.cljk $S/twins/$f.cljk $N/$f.cljk || exit 1; }
done
$H/ovchk.sh ${@:-machine_ir}
