(ns kotoba.geo.tile
  "Tile management: LRU cache, fetch state, LOD selection.

  Ported from kami-engine/kami-geo/src/tile.rs (Rust, deleted from the
  working tree pre-commit; recovered from git history).

  The Rust `TileManager` was a `&mut self` struct with imperative cache
  mutation. This port keeps the same state shape and transitions but as
  pure functions over an immutable manager map — callers thread the
  returned manager through (`(let [mgr' (begin-frame mgr)] ...)`), matching
  this repo's no-network/no-IO/pure-domain convention. `mesh-handle` /
  `texture-handle` are opaque renderer-assigned ids (kept as plain data;
  no GPU code lives here — that bridge is intentionally unported, see
  README).

  Manager shape:
  `{:cache {<TileCoord> <CachedTile>} :tile-url-template <str> :frame-counter <long>}`

  CachedTile shape:
  `{:coord <TileCoord> :state :pending|:ready|:failed
    :mesh-handle nil-or-int :texture-handle nil-or-int :last-used-frame <long>}`"
  (:require [kotoba.geo.constants :as k]
            [kotoba.geo.projection :as proj]))

(defn make-manager
  "Construct a new, empty TileManager. Mirrors `TileManager::new`."
  [tile-url-template]
  {:cache {}
   :tile-url-template tile-url-template
   :frame-counter 0})

(defn begin-frame
  "Advance frame counter (call once per frame)."
  [mgr]
  (update mgr :frame-counter inc))

(defn touch
  "Mark a tile as needed this frame. Returns `[mgr' ready?]`."
  [mgr coord]
  (if-let [entry (get-in mgr [:cache coord])]
    (let [entry' (assoc entry :last-used-frame (:frame-counter mgr))]
      [(assoc-in mgr [:cache coord] entry') (= :ready (:state entry'))])
    [mgr false]))

(defn tiles-to-fetch
  "Tiles that need to be fetched (not in cache). Returns `[mgr' to-fetch]`."
  [mgr visible]
  (reduce
   (fn [[mgr to-fetch] coord]
     (if (contains? (:cache mgr) coord)
       [mgr to-fetch]
       [(assoc-in mgr [:cache coord]
                  {:coord coord
                   :state :pending
                   :mesh-handle nil
                   :texture-handle nil
                   :last-used-frame (:frame-counter mgr)})
        (conj to-fetch coord)]))
   [mgr []]
   visible))

(defn mark-ready
  "Mark a tile as ready with its GPU handles."
  [mgr coord mesh-handle texture-handle]
  (if (contains? (:cache mgr) coord)
    (update-in mgr [:cache coord] assoc
               :state :ready :mesh-handle mesh-handle :texture-handle texture-handle)
    mgr))

(defn mark-failed
  "Mark a tile fetch as failed."
  [mgr coord]
  (if (contains? (:cache mgr) coord)
    (assoc-in mgr [:cache coord :state] :failed)
    mgr))

(defn evict
  "Evict least-recently-used tiles when cache exceeds `max-cached-tiles`.
  Returns `[mgr' evicted-texture-handles]`."
  [mgr]
  (let [cache (:cache mgr)]
    (if (<= (count cache) k/max-cached-tiles)
      [mgr []]
      (let [sorted (sort-by (comp :last-used-frame val) cache)
            to-remove (- (count cache) k/max-cached-tiles)
            removed (take to-remove sorted)
            evicted-textures (into [] (keep (comp :texture-handle val)) removed)
            cache' (apply dissoc cache (map key removed))]
        [(assoc mgr :cache cache') evicted-textures]))))

(defn ready-tiles
  "Get ready tiles that should be drawn."
  [mgr]
  (into [] (filter #(= :ready (:state %))) (vals (:cache mgr))))

(defn tile-world-position
  "Build the world-space position (top-left corner) for a tile quad."
  [coord center-px]
  (let [origin (proj/tile-origin-px coord)]
    [(- (:x origin) (:x center-px)) 0.0 (- (:y origin) (:y center-px))]))
