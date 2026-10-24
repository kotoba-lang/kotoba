(ns nagare.mesh
  "Unstructured **polyMesh** — the geometric substrate of the finite-volume method.

  OpenFOAM never stores a structured i/j/k grid; it stores a *face list*. Every
  cell is a closed set of flat **faces**; each internal face is shared by exactly
  two cells — an **owner** and a **neighbour** — and each boundary face belongs to
  one cell and one **patch**. This `owner`/`neighbour` addressing is the whole
  trick: a single flat sweep over faces visits every off-diagonal coupling of the
  discrete operator exactly once (owner gets `+flux`, neighbour gets `-flux`),
  which is *why* the conservation laws stay discretely conservative — the flux that
  leaves a cell through a face enters its neighbour byte-for-byte.

  We *build* a 2-D `Nx x Ny` block (unit depth in z) but immediately lower it into
  this unstructured representation, so the operators downstream never assume
  structure — they only ever read `owner`, `neighbour`, face areas/normals and the
  owner->neighbour delta. The geometry of a uniform block is exact (rectangles), so
  there is no discretization error hiding in the mesh itself; that keeps the coarse
  verification meshes trustworthy.

  ## Derived geometry (the finite-volume integrand bookkeeping)
  - **cell volume** `V_P` — area x unit-depth.
  - **face area vector** `Sf = |Sf| n`, with `n` the unit normal pointing *out of
    the owner* (so a positive `U.Sf` is outflow from the owner). For a boundary
    face the normal points out of the domain.
  - **owner->neighbour delta** `d = C_N - C_P` and its magnitude `|d|`, the length
    scale a `laplacian` divides by.
  - **linear interpolation weight** `fx` so that `phi_f = fx phi_P + (1-fx) phi_N`;
    for a uniform block the face bisects the centroid line and `fx = 1/2`.

  Everything below is a pure value (arrays + maps). Operators read it; nothing
  mutates it."
  #?(:clj (:require [kotoba.lang.text])))

;; ---------------------------------------------------------------------------
;; Construction
;; ---------------------------------------------------------------------------

(defn block-mesh
  "Build an `nx` x `ny` rectangular block over `[0,lx] x [0,ly]` (unit depth) and
  return it as an unstructured polyMesh value.

  Cells are numbered `c = j*nx + i` (i fastest). Internal faces are enumerated
  vertical-first (the `+x` faces between (i,j) and (i+1,j)) then horizontal (the
  `+y` faces between (i,j) and (i,j+1)); owner is always the lower-index cell so
  `Sf` points owner->neighbour. Four boundary **patches** are returned in the
  order `:left :right :bottom :top`, each carrying its own primitive arrays.

  Returns a map of primitive arrays (hot path) plus a few convenience vectors:
  `:n-cells :volumes :cell-centres :n-internal :owner :neighbour :if-area
  :if-dmag :if-sfx :if-sfy :if-fx :patches :dx :dy :nx :ny :lx :ly`."
  [{:keys [nx ny lx ly] :or {lx 1.0 ly 1.0}}]
  (let [nx   (int nx)
        ny   (int ny)
        dx   (/ (double lx) nx)
        dy   (/ (double ly) ny)
        nc   (* nx ny)
        vol  (* dx dy)                 ; unit depth
        cidx (fn [i j] (+ (* j nx) i))
        ;; cell volumes + centroids
        volumes (double-array nc vol)
        centres (vec (for [j (range ny) i (range nx)]
                       [(* (+ i 0.5) dx) (* (+ j 0.5) dy)]))
        ;; internal faces: (nx-1)*ny vertical + nx*(ny-1) horizontal
        nv   (* (max 0 (dec nx)) ny)
        nh   (* nx (max 0 (dec ny)))
        nif  (+ nv nh)
        owner     (int-array nif)
        neighbour (int-array nif)
        if-area   (double-array nif)
        if-dmag   (double-array nif)
        if-sfx    (double-array nif)
        if-sfy    (double-array nif)
        if-fx     (double-array nif)]
    ;; vertical (+x) internal faces
    (let [f (atom 0)]
      (doseq [j (range ny) i (range (dec nx))]
        (let [k @f]
          (aset owner k (int (cidx i j)))
          (aset neighbour k (int (cidx (inc i) j)))
          (aset if-area k dy)
          (aset if-dmag k dx)
          (aset if-sfx k dy)             ; |Sf| n = dy * (+1,0)
          (aset if-sfy k 0.0)
          (aset if-fx k 0.5)
          (swap! f inc)))
      ;; horizontal (+y) internal faces
      (doseq [j (range (dec ny)) i (range nx)]
        (let [k @f]
          (aset owner k (int (cidx i j)))
          (aset neighbour k (int (cidx i (inc j))))
          (aset if-area k dx)
          (aset if-dmag k dy)
          (aset if-sfx k 0.0)
          (aset if-sfy k dx)             ; dx * (0,+1)
          (aset if-fx k 0.5)
          (swap! f inc))))
    ;; boundary patches
    (let [mk (fn [name owners area db nfx nfy]
               (let [n (count owners)]
                 {:name  name
                  :n     n
                  :owner (int-array owners)
                  :area  (double-array (repeat n area))
                  :db    (double-array (repeat n db))
                  :nfx   (double-array (repeat n nfx))
                  :nfy   (double-array (repeat n nfy))
                  :sfx   (double-array (repeat n (* area nfx)))
                  :sfy   (double-array (repeat n (* area nfy)))}))
          left   (mk :left   (for [j (range ny)] (cidx 0 j))        dy (* 0.5 dx) -1.0 0.0)
          right  (mk :right  (for [j (range ny)] (cidx (dec nx) j)) dy (* 0.5 dx)  1.0 0.0)
          bottom (mk :bottom (for [i (range nx)] (cidx i 0))        dx (* 0.5 dy)  0.0 -1.0)
          top    (mk :top    (for [i (range nx)] (cidx i (dec ny))) dx (* 0.5 dy)  0.0  1.0)]
      {:nx nx :ny ny :lx (double lx) :ly (double ly) :dx dx :dy dy
       :n-cells nc :volumes volumes :cell-centres centres
       :n-internal nif :owner owner :neighbour neighbour
       :if-area if-area :if-dmag if-dmag
       :if-sfx if-sfx :if-sfy if-sfy :if-fx if-fx
       :patches [left right bottom top]})))

;; ---------------------------------------------------------------------------
;; Queries (used by tests and reporting)
;; ---------------------------------------------------------------------------

(defn total-volume
  "Sum of all cell volumes — must equal the domain volume `lx*ly` (unit depth)."
  [mesh]
  (areduce ^doubles (:volumes mesh) i s 0.0 (+ s (aget ^doubles (:volumes mesh) i))))

(defn internal-face-count [mesh] (:n-internal mesh))

(defn boundary-face-count
  [mesh]
  (reduce + (map :n (:patches mesh))))

(defn patch
  "Look up a boundary patch by name keyword."
  [mesh nm]
  (first (filter #(= nm (:name %)) (:patches mesh))))
