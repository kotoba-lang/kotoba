(ns engi.chain
  "engi's source chain, addressed so that inga can order it.

  Superproject ADR-2608038000 H1 says what inga orders: the ADVANCE of an
  agent chain head, not a transaction. `inga.chain` landed the consensus half
  — a committed proposal becomes an `:actor-advance` and the agent's head
  moves. This namespace is the production half: it addresses an engi entry so
  there is something for a proposal to name.

  ## One link, not two

  engi already chains its entries: `:engi/prev-hash` is the hash of the
  previous entry, and `next-entry` takes it explicitly because \"computing
  the hash of an entry needs a hash-fn\". inga needs `prev` to be the CID of
  the previous entry, because the actor tree stores it in `:state` and that
  field has to stay walkable.

  Those are the same link, so **use `entry-cid` as engi's `hash-fn`**. Then
  `:engi/prev-hash` IS the CID inga reads, `fold-balance`'s continuity check
  and inga's `:forked` check are checking one thing, and there is no second
  chain to keep in agreement with the first.

  Getting this wrong would not have failed loudly: two links over one chain
  agree until they don't, and the disagreement surfaces as a fork nobody
  authored.

  ## What the block is

  The entry itself, as a DAG-CBOR map, minus `:db/id` — an entity id is a
  storage detail and `canonical-entry` already excludes it for the same
  reason. So a generic IPLD walker reaching an actor's `:state` from the
  state root arrives at the ledger entry, with no engi-specific decoder.

  `canonical-entry` remains what is SIGNED. Signing a string and addressing a
  map is not two canonical forms in conflict: they commit to exactly the same
  fields, and `entry-fields` is the one list both read.

  ## Not in this namespace

  Signing (`engi.crypto`), storage (`engi.store`), and whether an entry is
  economically valid (`fold-balance`). An advance says an agent moved its own
  head from here to there; whether it should have is the application's
  question, answered before it votes — `inga.chain`'s docstring draws that
  line and this side does not cross it."
  (:require [kotoba.lang.text :as str]
            [ipld.core :as ipld]))

(defn valid-advance?
  "Is this advance one `inga.state` could apply? Shape only — an entry's
  validity is the application's question, answered before it votes.

  **This mirrors `inga.chain/valid-advance?` on purpose, and the copy is the
  lesser evil.** engi does not depend on inga at runtime (the README's line,
  and the reason the consensus cut was clean), so `engi.pool` cannot call
  inga's copy to decide what it will admit. Two predicates that can drift is
  the real cost; `engi.chain-test` pays it down by asserting the two agree
  over every combination of a grid, so a rule added on either side turns into
  a failing test rather than a proposal that passes admission here and halts
  a replica there."
  [{:keys [author seq prev entry]}]
  (boolean
   (and (string? author) (not (str/blank? author))
        (nat-int? seq)
        (or (nil? prev) (string? prev))
        (string? entry)
        (if (zero? seq) (nil? prev) (some? prev)))))

(def entry-fields
  "The fields an entry consists of, in `canonical-entry`'s order.

  One list, read by both the signing form and the addressing form, so a field
  can never be in the signature and out of the CID."
  [[:engi/kind "kind"]
   [:engi/seq "seq"]
   [:engi/prev-hash "prev-hash"]
   [:engi/counterparty "counterparty"]
   [:engi/amount "amount"]
   [:engi/memo "memo"]
   [:engi/transfer-id "transfer-id"]
   [:engi/self-sig "self-sig"]
   [:engi/counter-sig "counter-sig"]
   [:engi/ts "ts"]])

(def genesis-prev
  "What `next-entry` writes as `prev-hash` for the first entry of a chain.
  inga expresses the same thing as `prev` = nil, and `advance` translates."
  "genesis")

(defn entry-node
  "One entry as the DAG-CBOR node its CID addresses."
  [entry]
  (into {} (map (fn [[k s]] [s (get entry k)])) entry-fields))

(defn entry-cid
  "The CID of `entry`.

  This is the `:hash-fn` shape `engi.core/fold-balance` already takes, and
  passing it there is the point: the chain engi verifies and the chain inga
  orders become the same chain."
  [entry]
  (ipld/cid (ipld/encode (entry-node entry))))

(defn put-entry!
  "Write the entry's block through `put!` and return its CID."
  [put! entry]
  (ipld/put-node! put! (entry-node entry)))

(defn advance
  "`author`'s entry -> the advance `inga.chain/advance-op` turns into an op.

  `author` is not read from the entry because it is not in one: an entry
  names its `:engi/counterparty`, and whose chain it belongs to is the graph
  it was written to (`kotobase/db/<did:key>/engi`). Passing it explicitly is
  the honest shape — deriving an author from a counterparty would be exactly
  backwards."
  [author entry]
  (let [prev (:engi/prev-hash entry)]
    {:author author
     :seq (:engi/seq entry)
     :prev (when-not (= genesis-prev prev) prev)
     :entry (entry-cid entry)}))

(defn resolver
  "An `inga.chain/decode-block` resolver over a lookup of proposals.

  `lookup-fn` is `(fn [proposal-id] -> {:author _ :entry <entry map>} | nil)`
  — the deployment's read of its own store, which is where the knowledge of
  what a proposal refers to belongs. Returning nil is what makes a replica
  stop rather than invent a state; `inga.chain` explains why that is the
  correct halt."
  [lookup-fn]
  (when-not (ifn? lookup-fn)
    (throw (ex-info "engi.chain/resolver: lookup-fn is not callable"
                    {:type :engi.chain/invalid-seam})))
  (fn [proposal-id]
    (when-let [{:keys [author entry]} (lookup-fn proposal-id)]
      (advance author entry))))
