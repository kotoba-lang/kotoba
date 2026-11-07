#!/bin/zsh
H=$(cd "$(dirname "$0")" && pwd)
# rec.sh FN... : record host calls of machine_ir FN... over the corpus into $S/cases/FN.edn
S=${KR_WORK:-/tmp/kotoba-route}; H=$(cd "$(dirname "$0")" && pwd)
syms=""; for f in "$@"; do syms="$syms 'kotoba.native.machine-ir/$f"; done
w=""; for f in "$@"; do w="$w (println '$f (write-cases! 'kotoba.native.machine-ir/$f \"$S/cases/$f.edn\" ${MAXB:-60000}))"; done
$H/j.sh "(in-ns 'mi) (reset! recordings {}) (doseq [s [$syms]] (wrap! s)) (println (compile-corpus! (corpus-files))) $w (unwrap-all!)" | grep -v "^mi=>\|^user=>" | grep -v "^nil$"
