#!/usr/bin/env bash
set -euo pipefail

for command in bitcoin-cli jq clojure; do
  if ! command -v "$command" >/dev/null; then
    echo "$command is required for normalized snapshot soak." >&2
    exit 77
  fi
done

network="${CONSENSUS_HISTORY_NETWORK:-mainnet}"
datadir="${CONSENSUS_CORE_DATADIR:-}"
header_database="${CONSENSUS_NORMALIZED_HEADER_DATABASE:-}"
snapshot_path="${CONSENSUS_SNAPSHOT_PATH:-}"
snapshot_height="${CONSENSUS_SNAPSHOT_HEIGHT:-}"
snapshot_base_hash="${CONSENSUS_SNAPSHOT_BASE_HASH:-}"
snapshot_commitment="${CONSENSUS_SNAPSHOT_COMMITMENT:-}"
snapshot_chain_txs="${CONSENSUS_SNAPSHOT_CHAIN_TXS:-}"
genesis_hex="${CONSENSUS_GENESIS_HEX:-}"
database="${CONSENSUS_DISK_CHAINSTATE:-}"
end_height="${CONSENSUS_HISTORY_END:-}"
restart_interval="${CONSENSUS_RESTART_INTERVAL:-100}"

if [[ -z "$datadir" || -z "$header_database" || -z "$snapshot_path" ||
      -z "$snapshot_height" || -z "$snapshot_base_hash" ||
      -z "$snapshot_commitment" ||
      -z "$snapshot_chain_txs" || -z "$genesis_hex" ||
      -z "$database" ||
      -z "$end_height" ]]; then
  echo "Set Core datadir, normalized header DB, snapshot metadata, output DB, and end height." >&2
  exit 2
fi
if [[ ! -f "$header_database" || ! -f "$snapshot_path" ]]; then
  echo "Normalized header database or snapshot file is missing." >&2
  exit 2
fi
if (( snapshot_height < 1 || end_height < snapshot_height ||
      restart_interval < 1 )); then
  echo "Invalid snapshot/end/restart configuration." >&2
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
block_manifest="$(mktemp -t bitcoin-normalized-soak.XXXXXX)"
trap 'rm -f -- "$block_manifest"' EXIT

chain_info="$("${cli[@]}" getblockchaininfo)"
core_blocks="$(jq -r .blocks <<<"$chain_info")"
pruned="$(jq -r .pruned <<<"$chain_info")"
prune_height="$(jq -r '.pruneheight // 0' <<<"$chain_info")"
if (( end_height > core_blocks )); then
  echo "Requested end $end_height exceeds Core block height $core_blocks." >&2
  exit 2
fi
if [[ "$pruned" == "true" ]] &&
   (( end_height > snapshot_height && snapshot_height + 1 < prune_height )); then
  echo "Core pruned post-snapshot blocks below height $prune_height." >&2
  exit 2
fi

if (( snapshot_height < end_height )); then
  for height in $(seq "$((snapshot_height + 1))" "$end_height"); do
    block_hash="$("${cli[@]}" getblockhash "$height")"
    block_json="$("${cli[@]}" getblock "$block_hash" 1)"
    block_raw="$("${cli[@]}" getblock "$block_hash" 0)"
    printf '%s|%s|%s|%s|%s\n' \
      "$height" "$block_hash" \
      "$(jq -r .size <<<"$block_json")" \
      "$(jq -r .weight <<<"$block_json")" "$block_raw" \
      >>"$block_manifest"
  done
fi

CONSENSUS_NETWORK="$network" \
    CONSENSUS_HEADER_DATABASE="$header_database" \
    CONSENSUS_SNAPSHOT_PATH="$snapshot_path" \
    CONSENSUS_SNAPSHOT_HEIGHT="$snapshot_height" \
    CONSENSUS_SNAPSHOT_BASE_HASH="$snapshot_base_hash" \
    CONSENSUS_SNAPSHOT_COMMITMENT="$snapshot_commitment" \
    CONSENSUS_SNAPSHOT_CHAIN_TXS="$snapshot_chain_txs" \
    CONSENSUS_GENESIS_HEX="$genesis_hex" \
    CONSENSUS_DATABASE="$database" \
    CONSENSUS_END_HEIGHT="$end_height" \
    CONSENSUS_RESTART_INTERVAL="$restart_interval" \
    kbb -M -e '
  (require (quote bitcoin.consensus.block)
           (quote bitcoin.consensus.sqlite-utxo)
           (quote bitcoin.node.disk-consensus)
           (quote clojure.string))
  (let [env #(System/getenv %)
        network (keyword (env "CONSENSUS_NETWORK"))
        header-database (env "CONSENSUS_HEADER_DATABASE")
        database (env "CONSENSUS_DATABASE")
        snapshot-height (parse-long (env "CONSENSUS_SNAPSHOT_HEIGHT"))
        end-height (parse-long (env "CONSENSUS_END_HEIGHT"))
        interval (parse-long (env "CONSENSUS_RESTART_INTERVAL"))
        checkpoint
        {snapshot-height
         {:blockhash (env "CONSENSUS_SNAPSHOT_BASE_HASH")
          :hash-serialized (env "CONSENSUS_SNAPSHOT_COMMITMENT")
          :chain-tx-count
          (parse-long (env "CONSENSUS_SNAPSHOT_CHAIN_TXS"))}}
        seed-node
        (fn []
          (let [header-node
                (bitcoin.node.disk-consensus/open
                 {:path header-database :network network})
                genesis-bytes
                (mapv #(Integer/parseInt (apply str %) 16)
                      (partition 2 (env "CONSENSUS_GENESIS_HEX")))]
            (with-open
             [snapshot
              (java.io.FileInputStream. (env "CONSENSUS_SNAPSHOT_PATH"))]
              (bitcoin.node.disk-consensus/open
               {:path database :network network
                :header-state @(:state header-node)
                :snapshot-header-backend (:backend header-node)
                :snapshot-source snapshot
                :snapshot-options {:checkpoints checkpoint}
                :background-genesis-bytes genesis-bytes}))))
        open-node
        (fn []
          (try
            (bitcoin.node.disk-consensus/open
             {:path database :network network})
            (catch clojure.lang.ExceptionInfo error
              (if (= :bitcoin.node/missing-genesis
                     (:type (ex-data error)))
                (seed-node)
                (throw error)))))]
    (let [node (volatile! (open-node))
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
             (ex-info "Core block differential mismatch."
                      {:height height :expected expected :actual actual})))
          (let [before
                (bitcoin.node.disk-consensus/consensus-status @node)
                status
                (if (<= height (:height before))
                  (let [active-hash
                        (bitcoin.consensus.sqlite-utxo/header-ancestor-hash-at-height
                         (:backend @node) (:best-block before) height)]
                    (when-not (= expected-hash active-hash)
                      (throw
                       (ex-info "Resumed active-chain block mismatch."
                                {:height height
                                 :expected expected-hash
                                 :actual active-hash})))
                    before)
                  (bitcoin.node.disk-consensus/accept-block!
                   @node bytes (quot (System/currentTimeMillis) 1000)))]
            (when-not (= [height expected-hash]
                         [(min height (:height status))
                          (bitcoin.consensus.sqlite-utxo/header-ancestor-hash-at-height
                           (:backend @node) (:best-block status) height)])
              (throw
               (ex-info "Disk consensus active-chain mismatch."
                        {:height height :status status}))))
          (vswap! verified inc)
          (when (zero? (mod height interval))
            (vreset! node (open-node)))))
      (let [status
            (bitcoin.node.disk-consensus/consensus-status @node)
            integrity
            (bitcoin.node.disk-consensus/integrity-check! @node)]
        (when-not (= end-height (:height status))
          (throw
           (ex-info "Snapshot soak did not reach requested tip."
                    {:expected end-height :status status})))
        (println
         (str "verified=" @verified
              " active-height=" (:height status)
              " tip=" (:best-block status)
              " retained-undo=" (:retained-undo-blocks status)
              " reorg-depth=" (:available-reorg-depth status)
              " integrity=" (name (:integrity integrity)))))))' \
    <"$block_manifest"
