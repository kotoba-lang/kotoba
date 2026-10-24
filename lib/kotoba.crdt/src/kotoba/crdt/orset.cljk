(ns kotoba.crdt.orset
  "Observed-Remove Set (add-wins). An element is present iff it has at least
  one add-tag that hasn't been tombstoned. A `remove` can only tombstone tags
  it has actually observed, so an add that is concurrent with (i.e. not
  observed by) a remove survives it — the classic OR-Set \"concurrent add
  beats remove\" guarantee, which is what keeps two editors from losing a
  shape one of them just added while the other deleted the same shape.")

(defn init [] {:crdt/adds {} :crdt/tombstones #{}})

(defn add
  "Record `elem` as present via a fresh, globally-unique `tag` (e.g.
  [actor-id counter] from kotoba.crdt.clock)."
  [orset elem tag]
  (update-in orset [:crdt/adds elem] (fnil conj #{}) tag))

(defn observed-tags
  "The add-tags this replica has observed for `elem` — pass these to `remove`
  on another replica (or embed them in the remove op, see kotoba.crdt.doc)."
  [orset elem]
  (get-in orset [:crdt/adds elem] #{}))

(defn remove-tags
  "Tombstone exactly `tags` (previously observed add-tags for some element).
  A tag never observed locally is simply not present and removing it is a
  no-op — that's what lets a concurrent add survive a remove."
  [orset tags]
  (update orset :crdt/tombstones into tags))

(defn elements [orset]
  (into #{}
        (keep (fn [[elem tags]]
                (when (seq (remove (:crdt/tombstones orset) tags))
                  elem)))
        (:crdt/adds orset)))

(defn contains-elem? [orset elem]
  (contains? (elements orset) elem))

(defn merge-orset
  "Union of adds, union of tombstones — commutative, associative, idempotent."
  [a b]
  {:crdt/adds (merge-with into (:crdt/adds a) (:crdt/adds b))
   :crdt/tombstones (into (:crdt/tombstones a) (:crdt/tombstones b))})
