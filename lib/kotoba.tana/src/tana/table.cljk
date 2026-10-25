(ns tana.table
  "A table root: one immutable value that says which bytes a query needs.

  Below this, `columnar` reads one object well and `columnar.stats` decides
  whether a chunk can be skipped. What neither can do is answer *which of a
  thousand objects to open*, because that answer lives in a thousand footers
  and reading them is the cost being avoided. A table root is those footers,
  already read, in one addressable value.

  ## What makes it a root and not a directory listing

  Three things, and dropping any one of them turns it back into a listing:

  1. **It carries the statistics**, so a predicate prunes members before any
     object is opened.
  2. **It carries byte ranges**, so a surviving chunk is one ranged GET —
     not a footer fetch followed by a chunk fetch.
  3. **It is content-addressed**, so a reader that pins a root digest is
     reading one snapshot and cannot observe a half-published table.

  ## Snapshots name their members explicitly

  A snapshot is a vector of members, not a prefix or a time. There is no
  clock to ask and a datom carries no time (`kotobase.lake.table` states the
  same rule for the datom-plane manifest, and this is that rule at the
  self-describing plane). Appending an object writes a new root naming the
  old members plus the new one; the old root keeps answering what it
  answered.

  ## `:bounds-authority` has no default, and that is the safety property

  Statistics read out of the object at query time are as trustworthy as the
  object. Statistics read out of a root are as trustworthy as **whoever
  wrote the root** — and the failure is not symmetric. Bounds that are too
  wide cost an unnecessary read; bounds that are too narrow **delete rows
  from the answer**, silently, with no error and no way for the reader to
  notice.

  So a root must declare where its bounds came from:

  | value | meaning |
  |---|---|
  | `:from-footers` | extracted from the objects' own metadata by the publisher |
  | `:declared` | asserted by a writer; not read out of the bytes |

  and `tana.plan/plan` requires the caller to say which of those it will
  trust. Neither is a default. This is the discipline `kotobase-storage`
  applies to ref profiles for the same reason: **guessing is silent**, and an
  ignored precondition returns success."
  (:require [kotoba.lang.text :as str]
            [tana.member :as member]))

(def bounds-authorities
  "Where a root's statistics came from. A root declaring neither is refused."
  #{:from-footers :declared})

(defn table
  "A table root.

  `{:table name :columns [..] :members [..] :bounds-authority ..}`"
  [{:keys [table columns members bounds-authority] :as t}]
  (when (str/blank? (str table))
    (throw (ex-info "a table needs a name" {:type :tana/invalid-table})))
  (when-not (contains? bounds-authorities bounds-authority)
    (throw (ex-info "a table must declare where its bounds came from"
                    {:type :tana/no-bounds-authority
                     :table table :allowed bounds-authorities
                     :got bounds-authority})))
  (let [members (vec members)
        declared (vec columns)]
    (doseq [m members]
      (let [missing (remove (member/columns m) declared)]
        (when (seq missing)
          ;; Recorded, not refused: a member that predates a column is normal
          ;; and `columnar.evolve` reads an absent column as all-null, which
          ;; prunes. What must not happen is a root that claims a column a
          ;; member does not have without saying so.
          (when-not (:evolving? t)
            (throw (ex-info "member is missing declared columns; pass :evolving? true to admit it"
                            {:type :tana/schema-mismatch
                             :object (:object m) :missing (vec missing)}))))))
    (cond-> {:table (str table)
             :columns declared
             :bounds-authority bounds-authority
             :members members
             :rows (reduce + 0 (map :rows members))}
      (:evolving? t) (assoc :evolving? true))))

(defn append
  "A new root with `new-members` added. The old root is untouched."
  [root new-members]
  (table (assoc root :members (into (vec (:members root)) new-members))))

(defn- canonical-value [x]
  (cond
    (map? x) (into (sorted-map) (map (fn [[k v]] [k (canonical-value v)])) x)
    (set? x) (mapv canonical-value (sort-by pr-str x))
    (sequential? x) (mapv canonical-value x)
    :else x))

(defn canonical
  "The root's canonical text — sorted keys, vectors for sequences.

  The bytes a digest is taken over. Two roots that describe the same table
  produce the same text, so a publisher that rebuilds a root without changing
  anything republishes the same address."
  [root]
  (pr-str (canonical-value root)))

(defn address
  "`(hash-fn canonical-bytes)` — the root's content address.

  The hasher is injected. This library owns no crypto, for the reason
  ADR-2608161600 gives: a protocol that hashes has to pick a runtime, and
  this one runs on all of them."
  [hash-fn root]
  (hash-fn (canonical root)))

;; ── signing a root ──────────────────────────────────────────────────────────

(defn sign
  "Attach a signature over the root's canonical bytes.

  One signature covers everything transitively: the statistics, the byte
  ranges and the member list are all inside `canonical`. For a sharded table
  the top's signature covers every manifest, because the top names them by
  digest.

  ## Why a root needs this when a pack's tip does not

  `kotobase-storage-pack` leaves its tip object unsigned, and it is right to:
  every block leaving a pack is rehashed against the CID that was asked for,
  so a planted tip costs a lookup that FAILS. It cannot produce a block that
  is wrong.

  **Statistics have no such backstop.** A bound that is too narrow means the
  reader never fetches the bytes that would disprove it — the rows are simply
  absent from the answer, with no error and nothing to re-hash. So the one
  thing this plane cannot do without a signature is trust a root it did not
  produce."
  [root sign-fn signer]
  (assoc root
         :table/signer signer
         :table/signature (sign-fn (canonical (dissoc root :table/signer :table/signature
                                                        :table/verified-signer)))))

(defn verify
  "-> the root marked verified, or nil.

  nil rather than a throw: a root that fails verification is one a caller
  should treat as absent, and `tana.plan` refuses to fold bounds from a root
  that is not marked."
  [root verify-fn]
  (let [signer (:table/signer root)
        sig (:table/signature root)
        payload (canonical (dissoc root :table/signer :table/signature :table/verified-signer))]
    (when (and signer sig (verify-fn signer payload sig))
      (assoc root :table/verified-signer signer))))
