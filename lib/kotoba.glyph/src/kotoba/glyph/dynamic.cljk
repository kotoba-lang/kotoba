(ns kotoba.glyph.dynamic
  "Capacity-bounded, LRU-evicted key-set management. Ports the shared
  eviction algorithm behind kami-text (Rust) `DynamicGlyphAtlas::ensure_text`
  and `DynamicColorGlyphAtlas::ensure_text`: both track a growing set of
  required entries (glyph keys for the mono/SDF atlas, emoji cluster
  strings for the color atlas) and, once over capacity, evict the
  least-recently-used non-pinned entries. Deliberately generic — the
  tracked `key` type is whatever the caller's `incoming` collection uses
  (glyph-key maps from `kotoba.glyph.slot/glyph-key`, cluster strings,
  plain chars, ...); `:pinned` must use the same type. Pure data-structure
  logic — no atlas rebuild happens here; the caller rebuilds (via
  `kotoba.glyph.atlas`) only when `ensure-keys` reports `:changed? true`.

  kami-text's own capacity floors/pins for reference (apply them via the
  `capacity`/`pinned` args, not baked in here — resolving `' '`/`'?'`/`✨`
  to concrete glyph keys is itself font/atlas-shape dependent):
  mono min capacity 32 (pins the glyph keys for `' '` and `'?'`); color
  min capacity 8 (pins the `\"✨\"` cluster)."
  )

(defn make-state
  "A fresh tracking state. `capacity` is floored at 1; `pinned` is a coll
  of keys that are never evicted."
  ([capacity] (make-state capacity nil))
  ([capacity pinned]
   {:capacity (max (int capacity) 1)
    :pinned (set pinned)
    :keys #{}
    :last-used {}
    :usage-tick 0}))

(defn- evict
  "Evict least-recently-used non-pinned keys down to capacity. Mirrors the
  `keys.sort_by_key(last_used); take(remove_count); skip pinned` loop
  shared by both Rust `ensure_text` methods."
  [state]
  (let [{:keys [capacity pinned keys last-used]} state]
    (if (<= (count keys) capacity)
      state
      (let [remove-count (- (count keys) capacity)
            ordered (sort-by #(get last-used % 0) keys)
            to-remove (->> ordered (remove pinned) (take remove-count) set)]
        (if (empty? to-remove)
          state
          (-> state
              (update :keys #(reduce disj % to-remove))
              (update :last-used #(apply dissoc % to-remove))))))))

(defn ensure-keys
  "Merge `incoming` keys into `state`: bump the usage tick, mark every
  incoming key as most-recently-used, insert any new ones, then evict
  down to capacity. Returns `{:state state' :changed? bool}` — `:changed?`
  is true iff the resulting key set differs from the one `state` started
  with (mirrors the Rust `changed` flag that gates an atlas rebuild)."
  [state incoming]
  (let [tick (inc (:usage-tick state))
        before (:keys state)
        last-used (reduce (fn [m key] (assoc m key tick)) (:last-used state) incoming)
        keys (into before incoming)
        state' (evict (assoc state :usage-tick tick :last-used last-used :keys keys))]
    {:state state' :changed? (not= before (:keys state'))}))
