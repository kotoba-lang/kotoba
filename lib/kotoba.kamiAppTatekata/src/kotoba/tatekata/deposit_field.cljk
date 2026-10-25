(ns kotoba.tatekata.deposit-field
  "deposit-field — concrete deposition / screed-levelling height field.

  Ported 1:1 from `kami-app-tatekata::deposit_field.rs` (kami-engine, Rust,
  retired per ADR-2607010000-kotoba-runtime-sdk-cljc-migration).

  An application-layer material-process stand-in (the same honest pattern as
  kabitori's `MoldField`): there is no granular/MPM material model here, so
  robotic concrete 3-D printing / floor screeding is approximated as a 2-D
  height grid that a tool head raises toward a target level. It captures
  *coverage progress + tool path*, NOT real concrete rheology (slump,
  segregation, cold-joint) — those need a granular/MPM solver.

  Used by `robot:printer` steps (foundation slab, epoxy floor, paving).

  A field is a map:
  `{:deposit/nx :deposit/ny :deposit/x0 :deposit/y0 :deposit/dx :deposit/dy
    :deposit/target :deposit/h}` — `:deposit/h` is a flat vector of current
  deposited height per cell, row-major (`iy * nx + ix`). Functions here are
  pure: `deposit-at` returns an updated field rather than mutating in place.
  No network, no I/O.")

(defn- idx [nx ix iy] (+ (* iy nx) ix))

(defn make-field
  "`rect` = `[min-x min-y max-x max-y]` (sim x/y, metres); `target` = finish
  level (m). `nx`/`ny` are clamped to a minimum of 2."
  [rect nx ny target]
  (let [nx (max 2 nx)
        ny (max 2 ny)
        [x0 y0 x1 y1] rect]
    {:deposit/nx nx
     :deposit/ny ny
     :deposit/x0 x0
     :deposit/y0 y0
     :deposit/dx (/ (- x1 x0) nx)
     :deposit/dy (/ (- y1 y0) ny)
     :deposit/target target
     :deposit/h (vec (repeat (* nx ny) 0.0))}))

(defn cell-center
  "World `[x y]` at the centre of cell `(ix, iy)`."
  [{:keys [:deposit/x0 :deposit/y0 :deposit/dx :deposit/dy]} ix iy]
  [(+ x0 (* (+ ix 0.5) dx))
   (+ y0 (* (+ iy 0.5) dy))])

(defn height-at
  "Current deposited height (m) at cell `(ix, iy)`."
  [{:keys [:deposit/nx :deposit/h]} ix iy]
  (nth h (idx nx ix iy)))

(defn deposit-at
  "Deposit/level material under a tool head at `(x, y)` of `radius`, raising
  covered cells toward `:deposit/target` at `rate` (m/s) for `dt` seconds.
  Returns an updated field; does not mutate `field`."
  [{:keys [:deposit/nx :deposit/ny :deposit/target :deposit/h] :as field} x y radius rate dt]
  (let [r2 (* radius radius)
        raise (* rate dt)
        n (* nx ny)]
    (assoc field :deposit/h
           (persistent!
            (reduce
             (fn [acc i]
               (let [ix (mod i nx)
                     iy (quot i nx)
                     [cx cy] (cell-center field ix iy)
                     dx (- cx x)
                     dy (- cy y)
                     d2 (+ (* dx dx) (* dy dy))]
                 (if (<= d2 r2)
                   (assoc! acc i (min (+ (nth h i) raise) target))
                   acc)))
             (transient h)
             (range n))))))

(defn progress
  "Fraction of the footprint brought up to `:deposit/target` level (0..1)."
  [{:keys [:deposit/target :deposit/h]}]
  (if (<= target 0.0)
    1.0
    (let [mean (/ (reduce + h) (count h))]
      (min 1.0 (max 0.0 (/ mean target))))))
