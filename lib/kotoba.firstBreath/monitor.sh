#!/usr/bin/env bash
# monitor.sh — observe all first-breath cells across the fleet + chain rootCount.
#
# Usage:
#   ./monitor.sh                                          # default fleet, default anvil
#   FLEET="naphtali simeon judah" ./monitor.sh            # subset
#   ETZ_RPC=http://other:8545 ./monitor.sh

set -u

FLEET="${FLEET:-naphtali simeon judah zebulun levi}"
ETZ_RPC="${ETZ_RPC:-http://localhost:8545}"
ETZ_ANCHOR="${ETZ_ANCHOR:-0x5fbdb2315678afecb367f032d93f642f64180aa3}"

echo "─── etzhayyim organism monitor ──────────────────────────────"
echo "  rpc:    $ETZ_RPC"
echo "  anchor: $ETZ_ANCHOR"
echo

# Chain-side observation
if command -v cast >/dev/null; then
  count=$(cast call "$ETZ_ANCHOR" 'rootCount()(uint256)' --rpc-url "$ETZ_RPC" 2>/dev/null || echo "?")
  block=$(cast block-number --rpc-url "$ETZ_RPC" 2>/dev/null || echo "?")
  echo "  chain block:        $block"
  echo "  Anchor.rootCount(): $count   ← total breaths committed substrate-wide"
  echo
fi

# Per-cell observation
printf "  %-12s  %-10s  %-12s  %s\n" "cell" "counter" "last_block" "last_tick_at"
printf "  %-12s  %-10s  %-12s  %s\n" "----" "-------" "----------" "------------"
for h in $FLEET; do
  ssh -o ConnectTimeout=3 -o BatchMode=yes "$h@${h}nomac-mini.local" \
    "cat ~/etzhayyim/first-breath/state.edn 2>/dev/null" 2>/dev/null \
    | kbb -e "(let [s (try (clojure.edn/read-string (slurp *in*)) (catch Throwable _ nil))]
               (when s (println (str \"$h:counter:\" (get s :counter \"?\")
                                     \":block:\" (get s :last-block \"?\")
                                     \":ts:\" (subs (str (get s :last-tick-at \"?\")) 0 (min 19 (count (str (get s :last-tick-at \"?\")))))))))" \
        2>/dev/null | awk -F: '{printf "  %-12s  %-10s  %-12s  %s\n", $1, $3, $5, $7}'
done

echo
echo "  (cron heartbeat every 60s; counters increase monotonically as cells breathe)"
