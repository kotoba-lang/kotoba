#!/bin/zsh
# Run the admission differential (test/kotoba/kir/admission_diff.cljk): host reading vs the Kotoba reading of
# kotoba.kir.admission/check on the seed route.
#   AMU=<amu checkout: node_modules/nbb, deps-lock.edn, build/seed-boot/r6n>  FARM=<the image's source farm (scan/src)>
#   OBJECTS=<the image's frontend objects (front.sh output)>  LOADER=<kexe loader with the kgraph budget>
#   tools/admission_diff.sh [corpus-list]     env: ADM_GEN ADM_SEED ADM_BATCH ADM_SCRATCH
# 1. host phase (nbb, BOOTSTRAP-REFERENCE): cases and host outcomes into ADM_SCRATCH/batches/*.edn, expected.edn.
#    Host classpath: this checkout's src and test, the farm's kotoba.security (the host arms whose Kotoba arms the
#    Kotoba reading calls), AMU's src, resources and locked classpath.
# 2. seed route: a copy of OBJECTS with kotoba.kir.admission compiled from this checkout, the probe
#    (test/kotoba/kir/admission_diff_probe.cljk) compiled, linked and extracted; one loader run per batch.
# 3. compare phase (nbb).
emulate -L zsh; setopt pipefail
here=${0:A:h:h}
: ${AMU:?AMU=<amu checkout>} ${FARM:?FARM=<source farm>} ${OBJECTS:?OBJECTS=<frontend objects>} ${LOADER:?LOADER=<kexe loader>}
tmp=${ADM_SCRATCH:-/private/tmp/scratch/admission-diff}; mkdir -p $tmp/hostsec/kotoba; tmp=${tmp:A}
rm -rf $tmp/hostsec/kotoba/security $tmp/batches; cp -R $FARM/kotoba/security $tmp/hostsec/kotoba/security
[ -s $tmp/cp.txt ] || (cd $AMU && node node_modules/nbb/cli.js --classpath src scripts/print-classpath.cljk $AMU > $tmp/cp.txt) || exit 2
cp="$here/src:$here/test:$tmp/hostsec:$AMU/src:$AMU/resources:$(tr '\n' ':' < $tmp/cp.txt | sed 's/:$//')"
nbb() { node --stack-size=40000 $AMU/node_modules/nbb/cli.js --classpath "$cp" $here/test/kotoba/kir/admission_diff.cljk; }
ADM_CORPUS=${1:-$ADM_CORPUS} ADM_SCRATCH=$tmp ADM_MODE=host nbb || exit 1
SEED=$AMU/build/seed-boot/r6n/seed-1.bin; O=$tmp/o; rm -rf $O; mkdir -p $O; cp $OBJECTS/*.kso $O/
seed() { KEXE_COMMAND=1 KEXE_CAP_RESOURCES_35=$here:$tmp KEXE_STRING_POOL=268435456 KEXE_PAIRS=16777216 KEXE_VECTORS=65536 \
           KEXE_VECTOR_ITEMS=134217728 KEXE_CPU_SECONDS=1800 KEXE_WALL_SECONDS=1800 $LOADER $SEED 0 0 aarch64 35,37,38,39 -- "$@"; }
seed compile $here/src/kotoba/kir/admission.cljk --emit-module --object-dir $O --output $O/kotoba.kir.admission.kso > $tmp/emit.log 2>&1 \
  && seed compile $here/test/kotoba/kir/admission_diff_probe.cljk --emit-module --entry --object-dir $O --output $O/probe.adm-diff-main.kso >> $tmp/emit.log 2>&1 \
  && seed link $O/probe.adm-diff-main.kso --object-dir $O --output $tmp/probe.kseed >> $tmp/emit.log 2>&1 \
  && seed extract-native $tmp/probe.kseed --symbol main --output $tmp/probe.bin > $tmp/extract.log 2>&1 || { tail -3 $tmp/emit.log $tmp/extract.log; exit 1; }
off=$(sed -n 's/.*:offset \([0-9]*\).*/\1/p' $tmp/extract.log)
echo "probe $(shasum -a 256 $tmp/probe.bin | cut -c1-16) admission object $(shasum -a 256 $O/kotoba.kir.admission.kso | cut -c1-16)"
probe() { KEXE_COMMAND=1 KEXE_CAP_RESOURCES_35=$tmp KEXE_STRING_POOL=1073741824 KEXE_PAIRS=67108864 KEXE_VECTORS=67108864 \
            KEXE_VECTOR_ITEMS=134217728 KEXE_HASHCONS=16 KEXE_KGRAPH=1048576 KEXE_CPU_SECONDS=600 KEXE_WALL_SECONDS=900 \
            $LOADER $tmp/probe.bin $off 0 aarch64 3,35,37,38,39 -- $1 ${1%.edn}.out > ${1%.edn}.log 2>&1; }
for f in $tmp/batches/*.edn; do
  probe $f
  if [ ! -s ${f%.edn}.out ]; then
    # the batch trapped: rerun its cases one by one; a trapping case answers TRAP:<the loader's line>
    echo "batch ${f:t}: $(head -c 120 ${f%.edn}.log | tr '\n' ' ') -- rerunning singly"
    for c in ${f%.edn}/*.edn; do
      probe $c
      if [ -s ${c%.edn}.out ]; then cat ${c%.edn}.out; else printf 'TRAP:%s\n|~|\n' "$(head -1 ${c%.edn}.log)"; fi
    done > ${f%.edn}.out
  fi
done
ADM_SCRATCH=$tmp ADM_MODE=compare nbb
