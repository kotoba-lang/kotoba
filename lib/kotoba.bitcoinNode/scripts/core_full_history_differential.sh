#!/usr/bin/env bash
set -euo pipefail

for command in bitcoin-cli jq clojure; do
  if ! command -v "$command" >/dev/null; then
    echo "$command is required for full-history differential verification." >&2
    exit 77
  fi
done

network="${CONSENSUS_HISTORY_NETWORK:-mainnet}"
datadir="${CONSENSUS_CORE_DATADIR:-}"
database="${CONSENSUS_DISK_CHAINSTATE:-}"
end_height="${CONSENSUS_HISTORY_END:-}"
restart_interval="${CONSENSUS_RESTART_INTERVAL:-1000}"
expected_utxo_hash="${CONSENSUS_EXPECTED_UTXO_HASH:-}"
genesis_hex="${CONSENSUS_GENESIS_HEX:-}"
evidence_path="${CONSENSUS_EVIDENCE_PATH:-${database}.evidence.json}"

if [[ -z "$datadir" || -z "$database" || -z "$end_height" ]]; then
  echo "Set CONSENSUS_CORE_DATADIR, CONSENSUS_DISK_CHAINSTATE, and CONSENSUS_HISTORY_END." >&2
  exit 2
fi
if [[ "$database" != /* || "$evidence_path" != /* ]]; then
  echo "Disk chainstate and evidence paths must be absolute." >&2
  exit 2
fi
if (( end_height < 0 || restart_interval < 1 )); then
  echo "History end and restart interval are invalid." >&2
  exit 2
fi
mkdir -p "$(dirname "$database")" "$(dirname "$evidence_path")"

case "$network" in
  mainnet) network_args=(); expected_chain="main" ;;
  testnet) network_args=(-testnet); expected_chain="test" ;;
  testnet4) network_args=(-testnet4); expected_chain="testnet4" ;;
  signet) network_args=(-signet); expected_chain="signet" ;;
  regtest) network_args=(-regtest); expected_chain="regtest" ;;
  *) echo "Unsupported network: $network" >&2; exit 2 ;;
esac
cli=(bitcoin-cli "${network_args[@]}" -datadir="$datadir")

lock_path="${database}.full-history.lock"
if ! mkdir "$lock_path" 2>/dev/null; then
  echo "Another full-history verifier owns $lock_path." >&2
  exit 3
fi
cleanup() {
  rmdir "$lock_path" 2>/dev/null || true
}
trap cleanup EXIT

chain_info="$("${cli[@]}" getblockchaininfo)"
core_chain="$(jq -r .chain <<<"$chain_info")"
core_height="$(jq -r .blocks <<<"$chain_info")"
core_headers="$(jq -r .headers <<<"$chain_info")"
pruned="$(jq -r .pruned <<<"$chain_info")"
prune_height="$(jq -r '.pruneheight // 0' <<<"$chain_info")"
target_hash="$("${cli[@]}" getblockhash "$end_height")"
core_version="$("${cli[@]}" getnetworkinfo | jq -r .subversion)"

if [[ "$core_chain" != "$expected_chain" ]]; then
  echo "Core network '$core_chain' does not match '$network'." >&2
  exit 2
fi
if (( end_height > core_height || end_height > core_headers )); then
  echo "Requested height exceeds Core block/header progress." >&2
  exit 2
fi

if [[ -z "$genesis_hex" ]]; then
  genesis_hash="$("${cli[@]}" getblockhash 0)"
  if ! genesis_hex="$("${cli[@]}" getblock "$genesis_hash" 0 2>/dev/null)"; then
    echo "Core pruned genesis; set CONSENSUS_GENESIS_HEX to the trusted raw genesis block." >&2
    exit 2
  fi
fi

existing="$(
  CONSENSUS_NETWORK="$network" \
  CONSENSUS_DATABASE="$database" \
  CONSENSUS_GENESIS_HEX="$genesis_hex" \
  kbb -M -e '
    (require (quote bitcoin.node.disk-consensus))
    (let [env #(System/getenv %)
          hex (env "CONSENSUS_GENESIS_HEX")
          bytes (mapv #(Integer/parseInt (apply str %) 16)
                      (partition 2 hex))
          node
          (bitcoin.node.disk-consensus/open
           {:path (env "CONSENSUS_DATABASE")
            :network (keyword (env "CONSENSUS_NETWORK"))
            :genesis-bytes bytes})
          status (bitcoin.node.disk-consensus/consensus-status node)]
      (println (str (:height status) "|" (:best-block status))))'
)"
IFS='|' read -r existing_height existing_tip <<<"$existing"
if [[ ! "$existing_height" =~ ^[0-9]+$ || -z "$existing_tip" ]]; then
  echo "Kernel chainstate status is malformed: $existing" >&2
  exit 1
fi
if (( existing_height > end_height )); then
  echo "Kernel height $existing_height is beyond requested end $end_height." >&2
  exit 2
fi
canonical_existing="$("${cli[@]}" getblockhash "$existing_height")"
if [[ "$existing_tip" != "$canonical_existing" ]]; then
  echo "Kernel resume tip is not on Core's selected chain at height $existing_height." >&2
  exit 1
fi

next_height=$((existing_height + 1))
if [[ "$pruned" == "true" ]] && (( next_height < prune_height )); then
  echo "Core pruned required blocks below height $prune_height; resume starts at $next_height." >&2
  exit 2
fi

if [[ -z "$expected_utxo_hash" ]]; then
  if (( end_height != core_height )); then
    echo "Set CONSENSUS_EXPECTED_UTXO_HASH for a non-tip historical target." >&2
    exit 2
  fi
  echo "Freezing Core UTXO commitment at height $end_height..." >&2
  core_utxo="$("${cli[@]}" gettxoutsetinfo hash_serialized_3)"
  if [[ "$(jq -r .height <<<"$core_utxo")" != "$end_height" ||
        "$(jq -r .bestblock <<<"$core_utxo")" != "$target_hash" ]]; then
    echo "Core advanced or reorganized while its UTXO commitment was calculated." >&2
    exit 1
  fi
  expected_utxo_hash="$(jq -r .hash_serialized_3 <<<"$core_utxo")"
fi
if [[ ! "$expected_utxo_hash" =~ ^[0-9a-fA-F]{64}$ ]]; then
  echo "Expected UTXO commitment must be a 32-byte hexadecimal hash." >&2
  exit 2
fi
expected_utxo_hash="$(printf '%s' "$expected_utxo_hash" | tr '[:upper:]' '[:lower:]')"

result="$(
  {
    if (( next_height <= end_height )); then
      for height in $(seq "$next_height" "$end_height"); do
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
      CONSENSUS_DATABASE="$database" \
      CONSENSUS_GENESIS_HEX="$genesis_hex" \
      CONSENSUS_END_HEIGHT="$end_height" \
      CONSENSUS_TARGET_HASH="$target_hash" \
      CONSENSUS_RESTART_INTERVAL="$restart_interval" \
      kbb -M -e '
    (require (quote bitcoin.consensus.block)
             (quote bitcoin.consensus.sqlite-utxo)
             (quote bitcoin.node.disk-consensus)
             (quote clojure.string))
    (let [env #(System/getenv %)
          network (keyword (env "CONSENSUS_NETWORK"))
          database (env "CONSENSUS_DATABASE")
          genesis
          (mapv #(Integer/parseInt (apply str %) 16)
                (partition 2 (env "CONSENSUS_GENESIS_HEX")))
          options {:path database :network network :genesis-bytes genesis}
          interval (parse-long (env "CONSENSUS_RESTART_INTERVAL"))
          node (volatile! (bitcoin.node.disk-consensus/open options))
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
          (let [status
                (bitcoin.node.disk-consensus/accept-block!
                 @node bytes (quot (System/currentTimeMillis) 1000))]
            (when-not (= [height expected-hash]
                         [(:height status) (:best-block status)])
              (throw
               (ex-info "Disk consensus tip mismatch."
                        {:height height :status status}))))
          (vswap! verified inc)
          (when (zero? (mod height interval))
            (binding [*out* *err*]
              (println (str "checkpoint height=" height)))
            (vreset! node (bitcoin.node.disk-consensus/open options)))))
      (let [status (bitcoin.node.disk-consensus/consensus-status @node)
            integrity (bitcoin.node.disk-consensus/integrity-check! @node)
            commitment
            (bitcoin.consensus.sqlite-utxo/hash-serialized
             (:backend @node))]
        (when-not (= [(parse-long (env "CONSENSUS_END_HEIGHT"))
                      (env "CONSENSUS_TARGET_HASH")]
                     [(:height status) (:best-block status)])
          (throw
           (ex-info "Full-history validation did not reach its frozen target."
                    {:status status})))
        (when-not (= :ok (:integrity integrity))
          (throw
           (ex-info "Full-history SQLite integrity failed."
                    {:integrity integrity})))
        (println
         (clojure.string/join
          "|"
          [@verified (:height status) (:best-block status)
           (:utxo-count status) commitment]))))'
)"
IFS='|' read -r verified final_height final_tip final_txouts kernel_utxo_hash <<<"$result"

if [[ "$final_height" != "$end_height" || "$final_tip" != "$target_hash" ]]; then
  echo "Kernel result does not match the frozen target: $result" >&2
  exit 1
fi
if [[ "$kernel_utxo_hash" != "$expected_utxo_hash" ]]; then
  echo "Core/kernel UTXO mismatch: Core=$expected_utxo_hash kernel=$kernel_utxo_hash" >&2
  exit 1
fi
if [[ "$("${cli[@]}" getblockhash "$end_height")" != "$target_hash" ]]; then
  echo "Core reorganized the frozen target while verification was running." >&2
  exit 1
fi

completed_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
evidence_tmp="$(mktemp "$(dirname "$evidence_path")/.full-history-evidence.XXXXXX")"
jq -n \
  --arg schema "kotoba.bitcoin.full-history-differential.v1" \
  --arg network "$network" \
  --arg core_version "$core_version" \
  --arg database "$database" \
  --arg completed_at "$completed_at" \
  --arg target_hash "$target_hash" \
  --arg utxo_hash "$kernel_utxo_hash" \
  --argjson target_height "$end_height" \
  --argjson resumed_from "$existing_height" \
  --argjson verified_blocks "$verified" \
  --argjson txouts "$final_txouts" \
  '{schema: $schema, network: $network, core_version: $core_version,
    database: $database, completed_at: $completed_at,
    target: {height: $target_height, hash: $target_hash},
    resumed_from_height: $resumed_from, verified_blocks: $verified_blocks,
    txouts: $txouts, hash_serialized_3: $utxo_hash,
    sqlite_integrity: "ok", result: "match"}' >"$evidence_tmp"
mv "$evidence_tmp" "$evidence_path"

echo "Core/kernel full-history match at height $end_height: $target_hash"
echo "UTXO hash_serialized_3: $kernel_utxo_hash"
echo "Evidence: $evidence_path"
