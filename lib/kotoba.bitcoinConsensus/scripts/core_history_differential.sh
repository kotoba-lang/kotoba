#!/usr/bin/env bash
set -euo pipefail

for command in bitcoin-cli jq clojure; do
  if ! command -v "$command" >/dev/null; then
    echo "$command is required for historical differential verification." >&2
    exit 77
  fi
done

network="${CONSENSUS_HISTORY_NETWORK:-mainnet}"
datadir="${CONSENSUS_CORE_DATADIR:-}"
start_height="${CONSENSUS_HISTORY_START:-0}"
end_height="${CONSENSUS_HISTORY_END:-}"
chainstate_path="${CONSENSUS_HISTORY_CHAINSTATE:-}"
checkpoint_interval="${CONSENSUS_HISTORY_CHECKPOINT_INTERVAL:-1000}"

if [[ -z "$datadir" || -z "$end_height" || -z "$chainstate_path" ]]; then
  echo "Set CONSENSUS_CORE_DATADIR, CONSENSUS_HISTORY_END, and CONSENSUS_HISTORY_CHAINSTATE." >&2
  exit 2
fi
if (( start_height < 0 || end_height < start_height )); then
  echo "Invalid historical range: $start_height..$end_height" >&2
  exit 2
fi

case "$network" in
  mainnet) network_args=() ;;
  testnet) network_args=(-testnet) ;;
  testnet4) network_args=(-testnet4) ;;
  signet) network_args=(-signet) ;;
  regtest) network_args=(-regtest) ;;
  *) echo "Unsupported network: $network" >&2; exit 2 ;;
esac
cli=(bitcoin-cli "${network_args[@]}" -datadir="$datadir")

chain_info="$("${cli[@]}" getblockchaininfo)"
core_height="$(jq -r .blocks <<<"$chain_info")"
pruned="$(jq -r .pruned <<<"$chain_info")"
prune_height="$(jq -r '.pruneheight // 0' <<<"$chain_info")"
if (( end_height > core_height )); then
  echo "Requested height $end_height exceeds Core tip $core_height." >&2
  exit 2
fi
if [[ "$pruned" == "true" ]] && (( start_height < prune_height )); then
  echo "Core has pruned requested blocks below height $prune_height." >&2
  exit 2
fi
if (( start_height > 0 )) && [[ ! -f "$chainstate_path" ]]; then
  echo "A prior kernel chainstate is required when start height is non-zero." >&2
  exit 2
fi

{
  for height in $(seq "$start_height" "$end_height"); do
    block_hash="$("${cli[@]}" getblockhash "$height")"
    block_json="$("${cli[@]}" getblock "$block_hash" 1)"
    block_raw="$("${cli[@]}" getblock "$block_hash" 0)"
    printf '%s|%s|%s|%s|%s\n' \
      "$height" "$block_hash" \
      "$(jq -r .size <<<"$block_json")" \
      "$(jq -r .weight <<<"$block_json")" "$block_raw"
  done
} | CONSENSUS_HISTORY_NETWORK="$network" \
    CONSENSUS_HISTORY_START="$start_height" \
    CONSENSUS_HISTORY_END="$end_height" \
    CONSENSUS_HISTORY_CHAINSTATE="$chainstate_path" \
    CONSENSUS_HISTORY_CHECKPOINT_INTERVAL="$checkpoint_interval" \
    kbb -M -e '
  (require (quote bitcoin.consensus.block)
           (quote bitcoin.consensus.chainstate)
           (quote bitcoin.consensus.storage)
           (quote clojure.string))
  (let [environment #(System/getenv %)
        network (keyword (environment "CONSENSUS_HISTORY_NETWORK"))
        start (parse-long (environment "CONSENSUS_HISTORY_START"))
        end (parse-long (environment "CONSENSUS_HISTORY_END"))
        path (environment "CONSENSUS_HISTORY_CHAINSTATE")
        interval
        (parse-long (environment "CONSENSUS_HISTORY_CHECKPOINT_INTERVAL"))
        initial
        (when (pos? start)
          (bitcoin.consensus.storage/load! path network))]
    (when (and initial
               (not= (dec start)
                     (bitcoin.consensus.chainstate/active-height initial)))
      (throw
       (ex-info "Kernel checkpoint does not precede requested range"
                {:start start
                 :checkpoint-height
                 (bitcoin.consensus.chainstate/active-height initial)})))
    (let [state (volatile! initial)
          verified (volatile! 0)]
      (doseq [line (line-seq (java.io.BufferedReader. *in*))]
        (let [[height expected-hash expected-size expected-weight hex]
              (clojure.string/split line #"\|")
              height (parse-long height)
              bytes (mapv #(Integer/parseInt (apply str %) 16)
                          (partition 2 hex))
              parsed (bitcoin.consensus.block/parse bytes)
              expected [expected-hash (parse-long expected-size)
                        (parse-long expected-weight)]
              actual [(get-in parsed [:header :hash-hex])
                      (:size parsed) (:weight parsed)]]
          (when-not (= expected actual)
            (throw
             (ex-info "Bitcoin Core historical differential mismatch"
                      {:height height :expected expected :actual actual})))
          (vreset!
           state
           (if (zero? height)
             (bitcoin.consensus.chainstate/initialize network parsed)
             (bitcoin.consensus.chainstate/accept-block
              @state parsed (quot (System/currentTimeMillis) 1000))))
          (vswap! verified inc)
          (when (and (pos? interval)
                     (zero? (mod (inc height) interval)))
            (bitcoin.consensus.storage/save! path @state)
            (vreset! state
                     (bitcoin.consensus.storage/load! path network)))))
      (bitcoin.consensus.storage/save! path @state)
      (when-not (= end
                   (bitcoin.consensus.chainstate/active-height @state))
        (throw (ex-info "Historical range did not reach requested tip" {})))
      (println
       (str "verified=" @verified " active-height=" end
            " tip=" (:active-tip @state))))))'
