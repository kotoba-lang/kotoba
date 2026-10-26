#!/bin/zsh
# Run test/kotoba/kir/interp_diff.cljk with a stall-tolerant host phase.
#   tools/interp_diff.sh [cache-file]     env: DIFF_GEN DIFF_FUEL DIFF_SEED DIFF_DIRS DIFF_BATCH STALL (seconds, default 90)
# The host KIR interpreter charges no fuel for a zero-charge `recur` loop, so a corpus
# program with a non-terminating loop stalls the host oracle. The host phase runs in
# its own process, appends "[i outcome heads]" per case (preceded by "[i :begin]"), and
# is restarted past the stalled case when the file stops growing.
here=${0:A:h}/..
cache=${1:-/private/tmp/scratch/interp-diff.cache}
rm -f $cache; touch $cache
start=0
while true; do
  DIFF_CACHE=$cache DIFF_MODE=host DIFF_START=$start /private/tmp/kirrun.sh $here/test/kotoba/kir/interp_diff.cljk > $cache.log 2>&1 &
  pid=$!
  last=-1; idle=0
  while kill -0 $pid 2>/dev/null; do
    sleep 5
    size=$(wc -c < $cache | tr -d " ")
    if [[ $size == $last ]]; then idle=$((idle+5)); else idle=0; last=$size; fi
    if [[ $size == 0 ]]; then idle=0; fi   # still enumerating the corpus
    if [[ $idle -ge ${STALL:-90} ]]; then pkill -f "test/kotoba/kir/interp_diff.cljk"; break; fi
  done
  wait $pid 2>/dev/null
  if grep -q "host phase done" $cache.log; then break; fi
  start=$(tail -1 $cache | python3 -c 'import sys,re; m=re.match(r"\[(\d+) ", sys.stdin.read()); print(int(m.group(1))+1 if m else 0)')
  echo "stalled; restarting from $start"
done
DIFF_CACHE=$cache /private/tmp/kirrun.sh $here/test/kotoba/kir/interp_diff.cljk
