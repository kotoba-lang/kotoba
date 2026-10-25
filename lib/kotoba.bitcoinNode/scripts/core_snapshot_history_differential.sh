#!/usr/bin/env bash
set -euo pipefail

for command in bitcoin-cli jq clojure; do
  if ! command -v "$command" >/dev/null; then
    echo "$command is required for snapshot historical verification." >&2
    exit 77
  fi
done

network="${CONSENSUS_HISTORY_NETWORK:-mainnet}"
datadir="${CONSENSUS_CORE_DATADIR:-}"
snapshot_path="${CONSENSUS_SNAPSHOT_PATH:-}"
snapshot_height="${CONSENSUS_SNAPSHOT_HEIGHT:-}"
snapshot_commitment="${CONSENSUS_SNAPSHOT_COMMITMENT:-}"
snapshot_chain_txs="${CONSENSUS_SNAPSHOT_CHAIN_TXS:-}"
header_state="${CONSENSUS_HEADER_CHAINSTATE:-}"
database="${CONSENSUS_DISK_CHAINSTATE:-}"
end_height="${CONSENSUS_HISTORY_END:-}"
restart_interval="${CONSENSUS_RESTART_INTERVAL:-1000}"
background_validate="${CONSENSUS_BACKGROUND_VALIDATE:-false}"
genesis_hex="${CONSENSUS_GENESIS_HEX:-}"

if [[ -z "$datadir" || -z "$snapshot_path" || -z "$snapshot_height" ||
      -z "$header_state" || -z "$database" || -z "$end_height" ]]; then
  echo "Set Core datadir, snapshot path/height, header state, disk state, and end height." >&2
  exit 2
fi
if (( snapshot_height < 1 || end_height < snapshot_height ||
      restart_interval < 1 )); then
  echo "Invalid snapshot/end/restart heights." >&2
  exit 2
fi
if [[ ! -f "$snapshot_path" ]]; then
  echo "Snapshot does not exist: $snapshot_path" >&2
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
core_blocks="$(jq -r .blocks <<<"$chain_info")"
core_headers="$(jq -r .headers <<<"$chain_info")"
pruned="$(jq -r .pruned <<<"$chain_info")"
prune_height="$(jq -r '.pruneheight // 0' <<<"$chain_info")"
if (( end_height > core_blocks || end_height > core_headers )); then
  echo "Requested height exceeds Core block/header progress." >&2
  exit 2
fi
if [[ "$pruned" == "true" ]] &&
   (( end_height > snapshot_height && snapshot_height + 1 < prune_height )); then
  echo "Core pruned post-snapshot blocks below height $prune_height." >&2
  exit 2
fi

if [[ ! -f "$header_state" && -z "$genesis_hex" ]]; then
  genesis_hash="$("${cli[@]}" getblockhash 0)"
  if ! genesis_hex="$("${cli[@]}" getblock "$genesis_hash" 0 2>/dev/null)"; then
    echo "Core pruned genesis; set CONSENSUS_GENESIS_HEX once to seed headers." >&2
    exit 2
  fi
fi

header_height="$(
  CONSENSUS_NETWORK="$network" \
  CONSENSUS_HEADER_STATE="$header_state" \
  CONSENSUS_GENESIS_HEX="$genesis_hex" \
  kbb -M -e '
    (require (quote bitcoin.consensus.block)
             (quote bitcoin.consensus.chainstate)
             (quote bitcoin.consensus.storage))
    (let [env #(System/getenv %)
          path (env "CONSENSUS_HEADER_STATE")
          network (keyword (env "CONSENSUS_NETWORK"))
          file (java.nio.file.Path/of path (make-array String 0))
          state
          (if (java.nio.file.Files/exists
               file (make-array java.nio.file.LinkOption 0))
            (bitcoin.consensus.storage/load! path network)
            (let [hex (env "CONSENSUS_GENESIS_HEX")
                  bytes (mapv #(Integer/parseInt (apply str %) 16)
                              (partition 2 hex))]
              (bitcoin.consensus.chainstate/initialize
               network (bitcoin.consensus.block/parse bytes))))]
      (when-not (zero? (bitcoin.consensus.chainstate/active-height state))
        (throw (ex-info "Header checkpoint is not headers-only at genesis."
                        {:active-height
                         (bitcoin.consensus.chainstate/active-height state)})))
      (bitcoin.consensus.storage/save! path state)
      (println
       (get-in state [:nodes (:best-header state) :height])))'
)"

if (( header_height < end_height )); then
  {
    for height in $(seq "$((header_height + 1))" "$end_height"); do
      block_hash="$("${cli[@]}" getblockhash "$height")"
      raw_header="$("${cli[@]}" getblockheader "$block_hash" false)"
      printf '%s|%s|%s\n' "$height" "$block_hash" "$raw_header"
    done
  } | CONSENSUS_NETWORK="$network" \
      CONSENSUS_HEADER_STATE="$header_state" \
      CONSENSUS_RESTART_INTERVAL="$restart_interval" \
      kbb -M -e '
    (require (quote bitcoin.consensus.chainstate)
             (quote bitcoin.consensus.storage)
             (quote clojure.string)
             (quote kotobase.bitcoin.protocol))
    (let [env #(System/getenv %)
          network (keyword (env "CONSENSUS_NETWORK"))
          path (env "CONSENSUS_HEADER_STATE")
          interval (parse-long (env "CONSENSUS_RESTART_INTERVAL"))
          state (volatile! (bitcoin.consensus.storage/load! path network))]
      (doseq [line (line-seq (java.io.BufferedReader. *in*))]
        (let [[height expected hex] (clojure.string/split line #"\|")
              height (parse-long height)
              bytes (mapv #(Integer/parseInt (apply str %) 16)
                          (partition 2 hex))
              parsed (kotobase.bitcoin.protocol/decode-block-header bytes)]
          (when-not (= expected (:hash-hex parsed))
            (throw (ex-info "Core/header hash mismatch."
                            {:height height :expected expected
                             :actual (:hash-hex parsed)})))
          (vreset!
           state
           (bitcoin.consensus.chainstate/accept-header
            @state parsed (quot (System/currentTimeMillis) 1000)))
          (when (zero? (mod height interval))
            (bitcoin.consensus.storage/save! path @state)
            (vreset!
             state (bitcoin.consensus.storage/load! path network)))))
      (bitcoin.consensus.storage/save! path @state)
      (println
       (str "headers="
            (get-in @state [:nodes (:best-header @state) :height]))))'
fi

existing_height="$(
  CONSENSUS_NETWORK="$network" CONSENSUS_DATABASE="$database" \
  kbb -M -e '
    (require (quote bitcoin.consensus.sqlite-utxo))
    (let [path (System/getenv "CONSENSUS_DATABASE")
          file (java.nio.file.Path/of path (make-array String 0))]
      (println
       (if (java.nio.file.Files/exists
            file (make-array java.nio.file.LinkOption 0))
         (:height
          (bitcoin.consensus.sqlite-utxo/status
           (bitcoin.consensus.sqlite-utxo/open
            {:path path
             :network
             (keyword (System/getenv "CONSENSUS_NETWORK"))})))
         -1)))'
)"
block_start=$((snapshot_height + 1))
if (( existing_height >= snapshot_height )); then
  block_start=$((existing_height + 1))
fi

{
  if (( block_start <= end_height )); then
    for height in $(seq "$block_start" "$end_height"); do
      block_hash="$("${cli[@]}" getblockhash "$height")"
      block_json="$("${cli[@]}" getblock "$block_hash" 1)"
      block_raw="$("${cli[@]}" getblock "$block_hash" 0)"
      printf '%s|%s|%s|%s|%s\n' \
        "$height" "$block_hash" \
        "$(jq -r .size <<<"$block_json")" \
        "$(jq -r .weight <<<"$block_json")" "$block_raw"
    done
  fi
} | CONSENSUS_NETWORK="$network" \
    CONSENSUS_HEADER_STATE="$header_state" \
    CONSENSUS_SNAPSHOT_PATH="$snapshot_path" \
    CONSENSUS_SNAPSHOT_HEIGHT="$snapshot_height" \
    CONSENSUS_SNAPSHOT_COMMITMENT="$snapshot_commitment" \
    CONSENSUS_SNAPSHOT_CHAIN_TXS="$snapshot_chain_txs" \
    CONSENSUS_DATABASE="$database" \
    CONSENSUS_END_HEIGHT="$end_height" \
    CONSENSUS_RESTART_INTERVAL="$restart_interval" \
    kbb -M -e '
  (require (quote bitcoin.consensus.block)
           (quote bitcoin.consensus.storage)
           (quote bitcoin.node.disk-consensus)
           (quote clojure.string))
  (let [env #(System/getenv %)
        network (keyword (env "CONSENSUS_NETWORK"))
        header-state
        (bitcoin.consensus.storage/load!
         (env "CONSENSUS_HEADER_STATE") network)
        database (env "CONSENSUS_DATABASE")
        snapshot (java.io.FileInputStream.
                  (env "CONSENSUS_SNAPSHOT_PATH"))
        interval (parse-long (env "CONSENSUS_RESTART_INTERVAL"))
        snapshot-height (parse-long (env "CONSENSUS_SNAPSHOT_HEIGHT"))
        snapshot-hash
        (loop [hash (:best-header header-state)]
          (let [node (get-in header-state [:nodes hash])]
            (if (= snapshot-height (:height node))
              hash
              (recur (:parent node)))))
        custom-commitment (env "CONSENSUS_SNAPSHOT_COMMITMENT")
        snapshot-options
        (when (seq custom-commitment)
          {:checkpoints
           {snapshot-height
            {:blockhash snapshot-hash
             :hash-serialized custom-commitment
             :chain-tx-count
             (parse-long (env "CONSENSUS_SNAPSHOT_CHAIN_TXS"))}}})
        open-node
        #(bitcoin.node.disk-consensus/open
          {:path database :network network
           :header-state header-state :snapshot-source snapshot
           :snapshot-options snapshot-options})]
    (try
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
              (throw (ex-info "Core block differential mismatch."
                              {:height height :expected expected
                               :actual actual})))
            (let [status
                  (bitcoin.node.disk-consensus/accept-block!
                   @node bytes (quot (System/currentTimeMillis) 1000))]
              (when-not (= [height expected-hash]
                           [(:height status) (:best-block status)])
                (throw (ex-info "Disk consensus tip mismatch."
                                {:height height :status status}))))
            (vswap! verified inc)
            (when (zero? (mod height interval))
              (vreset! node (open-node)))))
        (let [status
              (bitcoin.node.disk-consensus/consensus-status @node)]
          (when-not (= (parse-long (env "CONSENSUS_END_HEIGHT"))
                       (:height status))
            (throw (ex-info "Snapshot history did not reach requested tip."
                            {:status status})))
          (println
           (str "verified=" @verified
                " active-height=" (:height status)
                " tip=" (:best-block status)
                " snapshot=" (name (:snapshot-status status))))))
      (finally (.close snapshot))))'

if [[ "$background_validate" == "true" ]]; then
  if [[ "$pruned" == "true" ]] && (( prune_height > 1 )); then
    echo "Core pruned background blocks below height $prune_height." >&2
    exit 2
  fi
  {
    for height in $(seq 1 "$snapshot_height"); do
      block_hash="$("${cli[@]}" getblockhash "$height")"
      block_raw="$("${cli[@]}" getblock "$block_hash" 0)"
      printf '%s|%s|%s\n' "$height" "$block_hash" "$block_raw"
    done
  } | CONSENSUS_NETWORK="$network" \
      CONSENSUS_DATABASE="$database" \
      CONSENSUS_SNAPSHOT_HEIGHT="$snapshot_height" \
      CONSENSUS_RESTART_INTERVAL="$restart_interval" \
      kbb -M -e '
    (require (quote bitcoin.node.disk-consensus)
             (quote clojure.string))
    (let [env #(System/getenv %)
          options {:path (env "CONSENSUS_DATABASE")
                   :network (keyword (env "CONSENSUS_NETWORK"))}
          interval (parse-long (env "CONSENSUS_RESTART_INTERVAL"))
          base-height (parse-long (env "CONSENSUS_SNAPSHOT_HEIGHT"))
          node (volatile! (bitcoin.node.disk-consensus/open options))
          verified (volatile! 0)]
      (doseq [line (line-seq (java.io.BufferedReader. *in*))]
        (let [[height expected-hash hex] (clojure.string/split line #"\|")
              height (parse-long height)
              bytes (mapv #(Integer/parseInt (apply str %) 16)
                          (partition 2 hex))
              status
              (bitcoin.node.disk-consensus/accept-background-block!
               @node bytes (quot (System/currentTimeMillis) 1000))]
          (when-not
           (if (= height base-height)
             (and (= :validated (:snapshot-status status))
                  (:fully-validated? status))
             (= [height expected-hash]
                [(:background-height status) (:background-tip status)]))
            (throw (ex-info "Background disk consensus mismatch."
                            {:height height :expected expected-hash
                             :status status})))
          (vswap! verified inc)
          (when (and (< height base-height)
                     (zero? (mod height interval)))
            (vreset! node (bitcoin.node.disk-consensus/open options)))))
      (let [status (bitcoin.node.disk-consensus/consensus-status @node)]
        (when-not (and (= :validated (:snapshot-status status))
                       (:fully-validated? status)
                       (bitcoin.node.disk-consensus/ready? @node))
          (throw (ex-info "Background validation did not promote snapshot."
                          {:status status})))
        (println
         (str "background-verified=" @verified
              " snapshot=" (name (:snapshot-status status))
              " ready=true"))))'
fi
