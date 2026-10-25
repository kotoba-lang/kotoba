(ns kami-app-giemon.mold-field
  "A scrubbable mold-coverage field over the cleaning surface.

  1:1 port of `mold_field.rs` from the legacy `kami-app-giemon` crate
  (kotoba-lang/kami-engine, deleted in PR #82 \"Remove Rust workspace\") as
  part of the clj-wgsl migration (ADR-2607010930, `com-junkawasaki/root`).

  The kami-genesis contact solver is rigid-body only (no FEM/MPM erodible
  material), so the mold itself is modelled here, at the giemon
  application layer, as a 2-D coverage grid lying on the contact ground
  plane. Each cell holds a coverage value in `[0, 1]` (1 = full mold, 0 =
  clean). The brush removes coverage where it presses AND slides — i.e.
  proportional to scrub work (a pressure proxy x tangential slip),
  localised to the brush footprint. This is pure grid math, entirely
  independent of the native kami-genesis rigid-body solver that drives the
  brush, so it ports without any adaptation."
  )

(defn new-field
  "A field of `nx` x `ny` cells, every cell initialised to `initial`.
  `origin` is `[x y]`, world coordinates of the cell-(0,0) corner. `cell`
  is the square cell size (m)."
  [origin cell nx ny initial]
  (let [c (max 0.0 (min 1.0 initial))]
    {:origin origin :cell cell :nx nx :ny ny
     :coverage (vec (repeat (* nx ny) c))}))

(defn total-coverage
  "Total remaining mold coverage (sum over cells)."
  [field]
  (reduce + (:coverage field)))

(defn cell-index
  "Cell index for a world `(x, y)`, or `nil` if outside the grid."
  [{:keys [origin cell nx ny]} x y]
  (let [[ox oy] origin
        ix (Math/floor (/ (- x ox) cell))
        iy (Math/floor (/ (- y oy) cell))]
    (when (and (>= ix 0.0) (>= iy 0.0))
      (let [ix (long ix) iy (long iy)]
        (when (and (< ix nx) (< iy ny))
          (+ (* iy nx) ix))))))

(defn coverage-at
  "Coverage at a world `(x, y)`, or `nil` if outside the grid."
  [field x y]
  (when-let [i (cell-index field x y)]
    (get (:coverage field) i)))

(defn scrub
  "Remove mold under a circular brush footprint centred at world `(cx, cy)`
  with `radius`, at the given scrub `intensity` (removal at the centre per
  call; falls off linearly to the footprint edge). Returns `[field'
  removed]`, `removed` being the total coverage removed this call."
  [{:keys [origin cell nx ny coverage] :as field} cx cy radius intensity]
  (if (or (<= intensity 0.0) (<= radius 0.0))
    [field 0.0]
    (let [[ox oy] origin
          r2 (* radius radius)
          ix0 (long (max 0.0 (Math/floor (/ (- (- cx radius) ox) cell))))
          iy0 (long (max 0.0 (Math/floor (/ (- (- cy radius) oy) cell))))
          ix1 (min nx (long (max 0.0 (Math/ceil (/ (- (+ cx radius) ox) cell)))))
          iy1 (min ny (long (max 0.0 (Math/ceil (/ (- (+ cy radius) oy) cell)))))]
      (loop [iy iy0
             cov (transient coverage)
             removed 0.0]
        (if (>= iy iy1)
          [(assoc field :coverage (persistent! cov)) removed]
          (let [[cov' removed']
                (loop [ix ix0
                       cov cov
                       removed removed]
                  (if (>= ix ix1)
                    [cov removed]
                    (let [wx (+ ox (* (+ ix 0.5) cell))
                          wy (+ oy (* (+ iy 0.5) cell))
                          d2 (+ (* (- wx cx) (- wx cx)) (* (- wy cy) (- wy cy)))]
                      (if (> d2 r2)
                        (recur (inc ix) cov removed)
                        (let [falloff (- 1.0 (/ (Math/sqrt d2) radius))
                              idx (+ (* iy nx) ix)
                              cur (get cov idx)
                              take (max 0.0 (min cur (* intensity falloff)))]
                          (recur (inc ix)
                                 (assoc! cov idx (- cur take))
                                 (+ removed take)))))))]
            (recur (inc iy) cov' removed')))))))
