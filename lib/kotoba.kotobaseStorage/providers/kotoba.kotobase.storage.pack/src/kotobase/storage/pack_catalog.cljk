(ns kotobase.storage.pack-catalog
  "The catalog as datoms — which pack holds a CID, expressed on the plane
  everything else in kotobase is already on.

  A packed read asks two questions and they have two owners. *Where inside
  this pack* is answered by the pack's own CARv2 index. *Which pack* is
  answered here, and it has to be a datom because it has to join: with the
  commit that wrote the pack, with the tenant that owns it, with the lake
  object it came from. Join reach in kotobase is exactly one ref
  (ADR-260726), so a catalog kept anywhere else is a catalog nothing else
  can ask about.

  This namespace ships the vocabulary, the quads and the query, and nothing
  that talks to a store. `kotobase-storage-pack` composes over any object
  store; making it depend on one datom engine would be the same mistake in
  the other plane. `datom-catalog` takes the two ports it needs.

  **A subject is a content address.** `bonsai` made the same choice for git
  objects — a blob's subject IS its own hash — and it is right for the same
  reason: an entity id that is not derived from the bytes is a second
  identity to keep in sync with the first."
  (:require [kotoba.lang.text :as str]))

(def schema
  "The attribute vocabulary. Data, not a schema installation: the datom
  plane this lands on has its own generated `manifest/schema.edn`, and
  duplicating declarations there by hand is how two schemas start."
  {:block/pack         {:doc "The pack CID holding this block's frame."
                        :value-type :ref}
   :block/file-offset  {:doc "Absolute offset of the frame in the pack file."
                        :value-type :long}
   :block/frame-length {:doc "Length of the frame (varint + CID + bytes)."
                        :value-type :long}
   :pack/object-key    {:doc "Key the pack is stored under, when it differs
                              from the pack CID."
                        :value-type :string}
   :pack/size-bytes    {:doc "Size of the whole CARv2 archive."
                        :value-type :long}
   :pack/block-count   {:doc "How many frames the pack carries."
                        :value-type :long}
   :pack/sealed-at     {:doc "When the pack was sealed. Packs are immutable,
                              so this never changes."
                        :value-type :instant}})

(defn cid-ref?
  "Whether a quad's object should be indexed as a reference.

  A pack CID is one: `refs-to` is what answers 'which blocks are in this
  pack', which is the reverse of the only lookup the read path performs and
  the direction compaction needs."
  [o]
  (and (string? o) (str/starts-with? o "baf")))

;; ── facts ───────────────────────────────────────────────────────────────────

(defn entry->quads
  "`{:cid :pack-cid :file-offset :frame-length}` → quads.

  There is no `:block/cid`: the subject IS the CID."
  [{:keys [cid pack-cid file-offset frame-length]}]
  [{:s cid :p :block/pack :o pack-cid}
   {:s cid :p :block/file-offset :o file-offset}
   {:s cid :p :block/frame-length :o frame-length}])

(defn pack->quads
  "`{:pack-cid :size-bytes :entries :sealed-at :object-key}` → quads.

  `:sealed-at` and `:object-key` are omitted when absent rather than
  defaulted — a pack whose seal time nobody recorded should not claim one."
  [{:keys [pack-cid size-bytes entries sealed-at object-key]}]
  (cond-> [{:s pack-cid :p :pack/size-bytes :o size-bytes}
           {:s pack-cid :p :pack/block-count :o (count entries)}]
    sealed-at  (conj {:s pack-cid :p :pack/sealed-at :o sealed-at})
    object-key (conj {:s pack-cid :p :pack/object-key :o object-key})))

;; ── queries ─────────────────────────────────────────────────────────────────

(def locate-query
  "Where one CID lives. `:in [?cid]`.

  One CID per call rather than a batch: the lookup is not what a packed read
  costs — the object fetch is — and a per-CID query uses the index instead
  of scanning. A batch form would be a `(or ...)` over N clauses, which is
  the scan wearing a hat."
  '{:find [?pack ?off ?len]
    :in [?cid]
    :where [[?cid :block/pack ?pack]
            [?cid :block/file-offset ?off]
            [?cid :block/frame-length ?len]]})

(def pack-contents-query
  "Every block in a pack, with its frame. `:in [?pack]`.

  The reverse direction, which is what compaction and a catalog rebuild
  need — and the reason `:block/pack` is indexed as a reference."
  '{:find [?cid ?off ?len]
    :in [?pack]
    :where [[?cid :block/pack ?pack]
            [?cid :block/file-offset ?off]
            [?cid :block/frame-length ?len]]})

(def pack-summary-query
  "The join the datom plane exists for: a block's location alongside facts
  about the pack that holds it. `:in [?cid]`.

  Nothing about this query is possible if the catalog lives in its own
  store."
  '{:find [?pack ?off ?size ?count]
    :in [?cid]
    :where [[?cid :block/pack ?pack]
            [?cid :block/file-offset ?off]
            [?pack :pack/size-bytes ?size]
            [?pack :pack/block-count ?count]]})

;; ── the port ────────────────────────────────────────────────────────────────

(defn locate-row->entry
  "One `locate-query` row as the located-entry map a pack store reads, or nil
  when the CID is not in the catalog.

  Shared by the synchronous catalog and the Promise-returning one in
  `kotobase.storage.pack-catalog-async`, for the reason `pack-plan` is shared
  by the two stores: two constructors that each spelled this out would be two
  shapes the day one of them gained a field."
  [cid row]
  (when-let [[pack off len] row]
    {:cid cid :pack-cid pack :file-offset off :frame-length len}))

(defn entries->quads
  "The facts for a batch of located entries."
  [entries]
  (into [] (mapcat entry->quads) entries))

(defn datom-catalog
  "A catalog over two injected ports.

  - `(transact! quads)` — persist `{:s :p :o}` maps.
  - `(q query inputs)` — run one of the queries above, returning a set of
    `:find`-ordered tuples.

  Returns the same `{:lookup :record!}` shape `pack-block-store` already
  takes, plus `:record-pack!`, which `seal-pack!` calls when present so the
  pack's own facts land with its blocks'.

  Both ports are SYNCHRONOUS here. A Worker's datom store is not, and
  `pack-catalog-async/datom-catalog` is the same catalog over Promise-
  returning ports — the store on that side already awaits both."
  [{:keys [transact! q]}]
  {:lookup
   (fn [cids]
     (reduce (fn [acc cid]
               (if-let [entry (locate-row->entry cid (first (q locate-query [cid])))]
                 (assoc acc cid entry)
                 acc))
             {}
             cids))
   :record! (fn [entries] (transact! (entries->quads entries)))
   :record-pack! (fn [pack] (transact! (pack->quads pack)))})
