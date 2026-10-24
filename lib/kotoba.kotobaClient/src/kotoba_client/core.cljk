(ns kotoba-client.core
  "Browser-oriented orchestration for kotoba's content-addressed graph:
  CID-verified block ingest and hydrate-to-convergence over injected
  fetch/store ports. Mirrors the deleted `KotobaNode.ingestBlock` /
  `hydrateViaBlocks` JS/wasm client (git-history-only since
  `kotoba-lang/kotoba` commit `604896171b`, 2026-07-01).

  IPNS-record signature verification (trustless head resolution, mirroring
  the deleted `hydrate-and-query-verified!`) is `verify-ipns-head` below,
  via `ipns.head` (ADR-2607061800) -- `:clj`-only, matching `ipns.head`'s
  own JVM-only convention (a `:cljs` port is `ipns.head`'s own tracked
  follow-up, not fabricated here)."
  (:require [ipld.core :as ipld]
            #?(:clj [ipns.head :as ipns-head])))

(defn ingest-block
  "Verify `bytes` actually hashes to `claimed-cid` (dag-cbor codec) before
  accepting it. Returns `bytes` on success; throws `ex-info` on CID
  mismatch (never silently accepts unverified content)."
  [claimed-cid bytes]
  (let [actual-cid (ipld/cid bytes)]
    (when (not= actual-cid claimed-cid)
      (throw (ex-info "kotoba-client: CID mismatch on block ingest"
                       {:claimed claimed-cid :actual actual-cid})))
    bytes))

(defn hydrate-via-blocks
  "Walk `root-cid`'s missing blocks to convergence, fetching each via the
  injected `fetch-block` port and ingesting (CID-verified) into the
  injected `store` port, mirroring the deleted `hydrateViaBlocks` loop.

  opts:
    :missing-cids (root-cid, store) -> seq of CIDs still needed to resolve
                  `root-cid` (e.g. `kotoba-client.prolly-hydrate/missing-cids`
                  for prolly-tree/quad-store-shaped trees).
    :fetch-block  cid -> bytes (may throw; not caught here).
    :store        {:put! (cid, bytes -> _), :get-fn (cid -> bytes)}.
    :max-rounds   safety cap on hydrate iterations (default 64, matching
                  the deleted JS client's default).

  Returns the number of blocks ingested this call. Throws if convergence
  is not reached within :max-rounds (never loops forever)."
  [{:keys [missing-cids fetch-block store max-rounds]
    :or {max-rounds 64}}
   root-cid]
  (loop [round 0 ingested 0]
    (let [missing (missing-cids root-cid store)]
      (cond
        (empty? missing) ingested

        (>= round max-rounds)
        (throw (ex-info "kotoba-client: hydrate-via-blocks did not converge"
                         {:root root-cid :max-rounds max-rounds}))

        :else
        (do
          (doseq [cid missing]
            ((:put! store) cid (ingest-block cid (fetch-block cid))))
          (recur (inc round) (+ ingested (count missing))))))))

#?(:clj
   (defn verify-ipns-head
     "Trustless verification of a fetched IPNS head record (as
      `ipns.head/sign` produces, ADR-2607061800): the signature over the
      record's own fields is checked against its `:public_key_multibase`
      did:key, with no server trusted to have told the truth about it.
      Returns `{:valid? bool :name ...}` -- `hydrate-via-blocks` above can
      then be pointed at `(:value record)` (the verified head's CID) only
      if `:valid?` is true."
     [record]
     (ipns-head/verify record)))
