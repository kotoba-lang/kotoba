(ns filecoin.node.rpc
  "The chain-facing half of Lotus's JSON-RPC, and block headers ⇄ JSON.

  `filecoin.rpc` covers what a *client* asks a node: balances, nonces, gas
  estimates, pushing a message. What is here is what one asks about the
  *chain*: headers, tipsets, the messages in a block, the receipts of the
  parents. The split follows the two repos.

  `json->block-header` matters more than the method builders. Lotus's JSON is
  not the CBOR: `Parents` are `{\"/\": \"bafy…\"}` link objects rather than
  tagged byte strings, the two big amounts are decimal strings rather than
  sign-magnitude bytes, signatures are `{Type, Data}` objects with base64
  data rather than a single byte string, and absent optional fields are
  `null` rather than missing. Converting by renaming keys produces a header
  that looks right and hashes to a CID no peer has."
  (:require [filecoin.address :as addr]
            [filecoin.node.block :as block]
            [filecoin.rpc :as rpc]
            [filecoin.signature :as sig]))

(defn- link->cid [x] (get x "/"))
(defn- cid->link [c] {"/" c})

(defn- json->signature [x]
  (when (some? x)
    (sig/signature (get x "Type") (rpc/base64-decode (get x "Data")))))

(defn- signature->json [s]
  (when s {"Type" (:type s) "Data" (rpc/base64 (:data s))}))

(defn json->block-header
  "A Lotus `BlockHeader` JSON object → a `filecoin.node.block` header map."
  [j]
  (block/block-header
   {:miner (get j "Miner")
    :ticket (when-let [t (get j "Ticket")]
              (block/ticket (rpc/base64-decode (get t "VRFProof"))))
    :election-proof (when-let [e (get j "ElectionProof")]
                      (block/election-proof
                       (get e "WinCount")
                       (rpc/base64-decode (get e "VRFProof"))))
    :beacon-entries (mapv #(block/beacon-entry
                            (get % "Round")
                            (rpc/base64-decode (get % "Data")))
                          (get j "BeaconEntries"))
    :win-post-proof (mapv #(block/post-proof
                            (get % "PoStProof")
                            (rpc/base64-decode (get % "ProofBytes")))
                          (get j "WinPoStProof"))
    :parents (mapv link->cid (get j "Parents"))
    :parent-weight (get j "ParentWeight")
    :height (get j "Height")
    :parent-state-root (link->cid (get j "ParentStateRoot"))
    :parent-message-receipts (link->cid (get j "ParentMessageReceipts"))
    :messages (link->cid (get j "Messages"))
    :bls-aggregate (json->signature (get j "BLSAggregate"))
    :timestamp (get j "Timestamp")
    :block-sig (json->signature (get j "BlockSig"))
    :fork-signaling (get j "ForkSignaling")
    :parent-base-fee (get j "ParentBaseFee")}))

(defn block-header->json
  "The inverse. Every optional field is emitted as an explicit `nil`, which
  is what Lotus sends — the array has 16 slots either way."
  [bh]
  (let [h (block/block-header bh)]
    {"Miner" (addr/to-string (:miner h))
     "Ticket" (when-let [t (:ticket h)]
                {"VRFProof" (rpc/base64 (:vrf-proof t))})
     "ElectionProof" (when-let [e (:election-proof h)]
                       {"WinCount" (:win-count e)
                        "VRFProof" (rpc/base64 (:vrf-proof e))})
     "BeaconEntries" (mapv (fn [b] {"Round" (:round b)
                                    "Data" (rpc/base64 (:data b))})
                           (:beacon-entries h))
     "WinPoStProof" (mapv (fn [p] {"PoStProof" (:post-proof p)
                                   "ProofBytes" (rpc/base64 (:proof-bytes p))})
                          (:win-post-proof h))
     "Parents" (mapv cid->link (:parents h))
     "ParentWeight" (:parent-weight h)
     "Height" (:height h)
     "ParentStateRoot" (cid->link (:parent-state-root h))
     "ParentMessageReceipts" (cid->link (:parent-message-receipts h))
     "Messages" (cid->link (:messages h))
     "BLSAggregate" (signature->json (:bls-aggregate h))
     "Timestamp" (:timestamp h)
     "BlockSig" (signature->json (:block-sig h))
     "ForkSignaling" (:fork-signaling h)
     "ParentBaseFee" (:parent-base-fee h)}))

;; ── methods ──────────────────────────────────────────────────────────────────

(defn chain-get-block [cid]
  (rpc/request "Filecoin.ChainGetBlock" [(cid->link cid)]))

(defn chain-get-block-messages
  "The block's messages, already split into the BLS ones (whose signatures
  are aggregated in the header) and the secp256k1 ones (which carry theirs)."
  [cid]
  (rpc/request "Filecoin.ChainGetBlockMessages" [(cid->link cid)]))

(defn chain-get-parent-messages
  "The messages of the block's *parents* — which is where receipts come from,
  since a block commits to the result of executing its parents."
  [cid]
  (rpc/request "Filecoin.ChainGetParentMessages" [(cid->link cid)]))

(defn chain-get-parent-receipts [cid]
  (rpc/request "Filecoin.ChainGetParentReceipts" [(cid->link cid)]))

(defn chain-get-tipset-by-height
  "The tipset at `height`, walking back from `tsk`. A null round returns the
  most recent earlier tipset rather than nothing, so the result's height is
  not necessarily the height asked for."
  ([height] (chain-get-tipset-by-height height nil))
  ([height tsk] (rpc/request "Filecoin.ChainGetTipSetByHeight" [height tsk])))

(defn chain-get-genesis []
  (rpc/request "Filecoin.ChainGetGenesis" []))

(defn state-network-version
  "Which network version a tipset ran under — the parameter every rule in
  `filecoin.node.mpool` is gated on."
  ([] (state-network-version nil))
  ([tsk] (rpc/request "Filecoin.StateNetworkVersion" [tsk])))
