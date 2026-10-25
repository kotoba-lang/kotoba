#!/usr/bin/env bash
set -euo pipefail

if ! command -v bitcoind >/dev/null || ! command -v bitcoin-cli >/dev/null; then
  echo "Bitcoin Core is required for differential verification." >&2
  exit 77
fi

consensus_datadir="$(mktemp -d "${TMPDIR:-/tmp}/bitcoin-consensus-core.XXXXXX")"
chainstate_path="$consensus_datadir/kernel-chainstate.edn"
differential_blocks="${CONSENSUS_DIFFERENTIAL_BLOCKS:-103}"
restart_interval="${CONSENSUS_RESTART_INTERVAL:-250}"
if (( differential_blocks < 103 )); then
  echo "CONSENSUS_DIFFERENTIAL_BLOCKS must be at least 103." >&2
  exit 2
fi
cleanup() {
  node_pid=""
  if [[ -f "$consensus_datadir/regtest/bitcoind.pid" ]]; then
    node_pid="$(<"$consensus_datadir/regtest/bitcoind.pid")"
  fi
  bitcoin-cli -regtest -datadir="$consensus_datadir" stop >/dev/null 2>&1 || true
  if [[ "$node_pid" =~ ^[0-9]+$ ]]; then
    for _ in $(seq 1 100); do
      if ! kill -0 "$node_pid" 2>/dev/null; then
        break
      fi
      sleep 0.1
    done
  fi
  rm -rf "$consensus_datadir"
}
trap cleanup EXIT

bitcoind -regtest -datadir="$consensus_datadir" -daemonwait -server=1 \
  -listen=0 -fallbackfee=0.00001 >/dev/null

bitcoin-cli -regtest -datadir="$consensus_datadir" createwallet differential \
  >/dev/null
mining_address="$(
  bitcoin-cli -regtest -datadir="$consensus_datadir" getnewaddress
)"
bitcoin-cli -regtest -datadir="$consensus_datadir" \
  generatetoaddress 101 "$mining_address" >/dev/null
destination_address="$(
  bitcoin-cli -regtest -datadir="$consensus_datadir" getnewaddress
)"
bitcoin-cli -regtest -datadir="$consensus_datadir" \
  sendtoaddress "$destination_address" 1 >/dev/null
bitcoin-cli -regtest -datadir="$consensus_datadir" \
  generatetoaddress 1 "$mining_address" >/dev/null
remaining_blocks=$((differential_blocks - 103))
if (( remaining_blocks > 0 )); then
  bitcoin-cli -regtest -datadir="$consensus_datadir" \
    generatetoaddress "$remaining_blocks" "$mining_address" >/dev/null
fi
tip_height=$((differential_blocks - 1))

result="$(
  {
    for height in $(seq 0 "$tip_height"); do
      block_hash="$(
        bitcoin-cli -regtest -datadir="$consensus_datadir" getblockhash "$height"
      )"
      block_json="$(
        bitcoin-cli -regtest -datadir="$consensus_datadir" \
          getblock "$block_hash" 1
      )"
      block_raw="$(
        bitcoin-cli -regtest -datadir="$consensus_datadir" \
          getblock "$block_hash" 0
      )"
      block_size="$(jq -r .size <<<"$block_json")"
      block_weight="$(jq -r .weight <<<"$block_json")"
      printf '%s|%s|%s|%s\n' \
        "$block_hash" "$block_size" "$block_weight" "$block_raw"
    done
  } | CONSENSUS_CHAINSTATE_PATH="$chainstate_path" \
      CONSENSUS_RESTART_INTERVAL="$restart_interval" \
      kbb -M -e '
    (require (quote bitcoin.consensus.block)
             (quote bitcoin.consensus.chainstate)
             (quote bitcoin.consensus.storage)
             (quote clojure.string))
    (let [lines (line-seq (java.io.BufferedReader. *in*))
          chainstate (volatile! nil)
          path (System/getenv "CONSENSUS_CHAINSTATE_PATH")
          restart-interval
          (parse-long (System/getenv "CONSENSUS_RESTART_INTERVAL"))]
      (doseq [[index line] (map-indexed vector lines)]
        (let [[expected-hash expected-size expected-weight hex]
              (clojure.string/split line #"\|")
              bytes (mapv #(Integer/parseInt (apply str %) 16)
                          (partition 2 hex))
              parsed (bitcoin.consensus.block/parse bytes)
              actual [(get-in parsed [:header :hash-hex])
                      (:size parsed) (:weight parsed)]
              expected [expected-hash
                        (parse-long expected-size)
                        (parse-long expected-weight)]]
          (when-not (= expected actual)
            (throw
             (ex-info "Bitcoin Core differential mismatch"
                      {:height index :expected expected :actual actual})))
          (vreset!
           chainstate
           (if (zero? index)
             (bitcoin.consensus.chainstate/initialize :regtest parsed)
             (bitcoin.consensus.chainstate/accept-block
              @chainstate parsed 2000000000)))
          (when (and (pos? index)
                     (pos? restart-interval)
                     (zero? (mod index restart-interval)))
            (bitcoin.consensus.storage/save! path @chainstate)
            (vreset!
             chainstate
             (bitcoin.consensus.storage/load! path :regtest)))))
      (bitcoin.consensus.storage/save! path @chainstate)
      (println
       (str "verified=" (count lines)
            " active-height="
            (bitcoin.consensus.chainstate/active-height @chainstate))))'
)"

if [[ "$result" != \
  "verified=$differential_blocks active-height=$tip_height" ]]; then
  echo "Core/kernel differential did not verify every fixture: '$result'" >&2
  exit 1
fi

snapshot_path="$consensus_datadir/utxo.dat"
snapshot_json="$(
  bitcoin-cli -regtest -datadir="$consensus_datadir" \
    dumptxoutset "$snapshot_path" latest
)"
snapshot_base="$(jq -r .base_hash <<<"$snapshot_json")"
snapshot_height="$(jq -r .base_height <<<"$snapshot_json")"
snapshot_commitment="$(jq -r .txoutset_hash <<<"$snapshot_json")"
snapshot_chain_txs="$(jq -r .nchaintx <<<"$snapshot_json")"
snapshot_coins="$(jq -r .coins_written <<<"$snapshot_json")"

snapshot_result="$(
  CONSENSUS_SNAPSHOT_PATH="$snapshot_path" \
  CONSENSUS_SNAPSHOT_BASE="$snapshot_base" \
  CONSENSUS_SNAPSHOT_HEIGHT="$snapshot_height" \
  CONSENSUS_SNAPSHOT_COMMITMENT="$snapshot_commitment" \
  CONSENSUS_SNAPSHOT_CHAIN_TXS="$snapshot_chain_txs" \
  CONSENSUS_SNAPSHOT_COINS="$snapshot_coins" \
  CONSENSUS_CHAINSTATE_PATH="$chainstate_path" \
  kbb -M -e '
    (require (quote bitcoin.consensus.assumeutxo)
             (quote bitcoin.consensus.storage))
    (let [environment #(System/getenv %)
          path (environment "CONSENSUS_SNAPSHOT_PATH")
          base (environment "CONSENSUS_SNAPSHOT_BASE")
          height (environment "CONSENSUS_SNAPSHOT_HEIGHT")
          commitment (environment "CONSENSUS_SNAPSHOT_COMMITMENT")
          chain-txs (environment "CONSENSUS_SNAPSHOT_CHAIN_TXS")
          expected-coins (environment "CONSENSUS_SNAPSHOT_COINS")
          chainstate-path (environment "CONSENSUS_CHAINSTATE_PATH")
          height (parse-long height)
          loaded
          (bitcoin.consensus.assumeutxo/load-snapshot
           (java.nio.file.Files/readAllBytes
            (java.nio.file.Path/of path (make-array String 0)))
           :regtest
           #(when (= % height) base)
           {:checkpoints
            {height {:blockhash base
                     :hash-serialized commitment
                     :chain-tx-count (parse-long chain-txs)}}})]
      (let [background
            (bitcoin.consensus.storage/load! chainstate-path :regtest)
            background-hash
            (bitcoin.consensus.assumeutxo/hash-serialized
             (get-in background [:utxo :coins]))]
        (when-not (= commitment background-hash)
          (throw
           (ex-info "Core/background UTXO commitment mismatch"
                    {:expected commitment :actual background-hash}))))
      (when-not (= (parse-long expected-coins)
                   (get-in loaded [:snapshot :coins-count]))
        (throw (ex-info "Snapshot coin count mismatch" {})))
      (println
       (str "height=" (get-in loaded [:snapshot :base-height])
            " coins=" (get-in loaded [:snapshot :coins-count])
            " status=" (name (get-in loaded [:snapshot :status])))))'
)"

if [[ "$snapshot_result" != \
  "height=$snapshot_height coins=$snapshot_coins status=assumed" ]]; then
  echo "Core snapshot differential failed: '$snapshot_result'" >&2
  exit 1
fi

echo "Core/kernel regtest differential match: $result; snapshot $snapshot_result"
