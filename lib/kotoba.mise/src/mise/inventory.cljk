(ns mise.inventory
  "Stock tracking (pure). A Stock is a map {sku → on-hand qty}. All ops are pure
  fns returning a new Stock map. Reservation is decremental; the host decides
  whether to commit (e.g. at order placement) vs hold (a separate holds map)."
  (:refer-clojure :exclude [available?]))

(defrecord Stock [levels])

(defn stock
  "Build a Stock from a {sku → qty} map (or a seq of [sku qty] pairs)."
  [m]
  (->Stock (into {} m)))

(defn levels [stock] (:levels stock {}))

(defn on-hand
  "On-hand qty for a sku (0 if absent)."
  [stock sku]
  (get (levels stock) sku 0))

(defn available?
  "True if on-hand(qty) >= needed."
  ([stock sku]
   (available? stock sku 1))
  ([stock sku needed]
   (>= (on-hand stock sku) (max 0 needed))))

(defn reserve
  "Decrement on-hand by qty (clamped at 0). Returns a new Stock."
  [stock sku qty]
  (when (available? stock sku qty)
    (update stock :levels assoc sku (- (on-hand stock sku) (max 0 qty)))))

(defn reserve-clamped
  "Old `reserve`: decrement to a floor of 0 and never refuse.

  Kept for callers that genuinely want a best-effort decrement (e.g.
  reconciling against a count that is already known to be behind). **Do not
  use it on the order path** — that is what made overselling silent."
  [stock sku qty]
  (update stock :levels assoc sku (max 0 (- (on-hand stock sku) (max 0 qty)))))

(defn restock
  "Increment on-hand by qty. Returns a new Stock."
  [stock sku qty]
  (let [cur (on-hand stock sku)]
    (update stock :levels assoc sku (+ cur (max 0 qty)))))

(defn set-level
  "Set on-hand to an absolute qty. Returns a new Stock."
  [stock sku qty]
  (update stock :levels assoc sku (max 0 (long qty))))

(defn reserve-many
  "Reserve a seq of [sku qty] **all-or-nothing**. Returns a new Stock, or
  nil when any line cannot be satisfied — no partial application.

  The previous version folded the clamping `reserve` over the lines, so an
  order for 10 of a sku with 3 in stock drove that sku to 0, carried on
  decrementing the remaining lines, and returned a Stock that looked like a
  successful reservation. A partly-unfulfillable order is not a partly
  successful one; the caller has to know before it promises anything."
  [stock reservations]
  (reduce (fn [s [sku qty]]
            (if-let [s' (and s (reserve s sku qty))] s' (reduced nil)))
          stock
          reservations))

(defn sufficient?
  "Can every [sku qty] in `reservations` be satisfied from `stock` at once?
  Accumulates repeated skus rather than checking each line in isolation."
  [stock reservations]
  (every? (fn [[sku needed]] (available? stock sku needed))
          (reduce (fn [m [sku qty]] (update m sku (fnil + 0) (max 0 qty)))
                  {} reservations)))
