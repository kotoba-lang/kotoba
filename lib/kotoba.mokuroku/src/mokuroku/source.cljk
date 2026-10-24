(ns mokuroku.source
  "Where a catalog's items come from — and the line the effect never crosses.

  `mokuroku` performs no effect. A source is a protocol the host implements
  over a capability package (`capability-fs-browse`, `capability-process-list`,
  …); this namespace only defines the shape of the answer and a memory source
  for fixtures and tests.

  The descriptor matters as much as the items. It is what tells a view which
  columns exist, which of them are sortable, and which commands the source is
  willing to accept — so an app does not hardcode `:size` and then break on a
  source that has no sizes."
  (:require [mokuroku.item :as item]))

(defprotocol ISource
  (-descriptor [this]
    "Static description of what this source yields. See `descriptor`.")
  (-fetch [this]
    "Return a vector of `mokuroku.item` maps. Implementations that touch the
     outside world do it here, behind a capability the host already granted."))

(defn descriptor
  "Describe a source.

  ATTRIBUTES is an ordered vector of
  `{:attribute/key :attribute/label :attribute/type :attribute/sortable?}`.
  Order is the default column order; a view may reorder but should not have to
  invent one."
  [{:keys [id item-kind label attributes commands capability]}]
  {:source/id id
   :source/label (or label (str id))
   :source/item-kind item-kind
   :source/attributes (vec attributes)
   ;; Command ids this source will accept. `mokuroku.command` proposes only
   ;; from this set, so an app cannot offer Delete on a read-only source.
   :source/commands (set commands)
   ;; The capability id whose grant makes -fetch legal. Recorded so a view can
   ;; say *why* it is empty when the grant was denied, instead of showing an
   ;; indistinguishable empty list.
   :source/capability capability})

(defn attribute
  ([k label type] (attribute k label type true))
  ([k label type sortable?]
   {:attribute/key k
    :attribute/label label
    :attribute/type type
    :attribute/sortable? sortable?}))

(defn attribute-keys [d]
  (mapv :attribute/key (:source/attributes d)))

(defn sortable? [d k]
  (boolean (some #(and (= k (:attribute/key %)) (:attribute/sortable? %))
                 (:source/attributes d))))

(defn accepts? [d command-id]
  (contains? (:source/commands d) command-id))

(defrecord MemorySource [descriptor items]
  ISource
  (-descriptor [_] descriptor)
  (-fetch [_] (vec items)))

(defn memory-source
  "A source backed by a literal item vector. Fixtures, tests, and the empty
  state an app shows before a capability grant arrives."
  [descriptor items]
  (->MemorySource descriptor (vec items)))

(defn fetch
  "Fetch and validate. Returns `{:fetch/items … :fetch/problems …}`.

  Problems do not throw and do not empty the result: one malformed row from a
  host provider should not blank the window. The caller is expected to surface
  the problems rather than drop them silently — the same discipline
  `manifest/edn-query.cljs` uses when it warns about skipped shapes."
  [source]
  (let [items (vec (-fetch source))]
    {:fetch/items items
     :fetch/problems (item/problems-in items)}))
