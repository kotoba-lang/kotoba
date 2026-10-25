(ns pnr.floorplan
  "Chip floorplanning — block placement, IO pin assignment, and utilization
  analysis. Restored from kami-pnr's `floorplan` module (kami-engine/
  kami-pnr/src/floorplan.rs, deleted PR #82).")

(def block-types #{:macro :std-cell-region :io-pad :power-domain})
(def pin-sides #{:north :south :east :west})

(defn block-area [block] (* (:width block) (:height block)))

(defn floorplan
  "A fresh floorplan of `die-width` x `die-height`, no blocks/pins."
  [die-width die-height]
  {:die-width die-width :die-height die-height :blocks [] :io-pins []})

(defn add-block [fp block] (update fp :blocks conj block))
(defn add-io-pin [fp pin] (update fp :io-pins conj pin))

(defn utilization
  "Ratio of total block area to die area (0.0 if die area is zero)."
  [fp]
  (let [total-block-area (reduce + 0.0 (map block-area (:blocks fp)))
        die-area (* (:die-width fp) (:die-height fp))]
    (if (zero? die-area) 0.0 (/ total-block-area die-area))))

(defn- overlaps? [a b]
  (and (< (:x a) (+ (:x b) (:width b)))
       (> (+ (:x a) (:width a)) (:x b))
       (< (:y a) (+ (:y b) (:height b)))
       (> (+ (:y a) (:height a)) (:y b))))

(defn validate
  "Check for die-boundary violations and overlapping blocks. Returns a
  vector of violation description strings."
  [fp]
  (let [blocks (:blocks fp)
        n (count blocks)]
    (vec
     (concat
      (for [a blocks
            :when (or (< (:x a) 0.0) (< (:y a) 0.0)
                      (> (+ (:x a) (:width a)) (:die-width fp))
                      (> (+ (:y a) (:height a)) (:die-height fp)))]
        (str "Block '" (:name a) "' extends outside die boundary"))
      (for [i (range n) j (range (inc i) n)
            :let [a (nth blocks i) b (nth blocks j)]
            :when (overlaps? a b)]
        (str "Overlap between '" (:name a) "' and '" (:name b) "'"))))))

(defn auto-floorplan
  "Simple row-based automatic floorplan: packs `blocks` left-to-right,
  wrapping to a new row when a block would exceed `die-width`."
  [blocks die-width die-height]
  (loop [remaining blocks
         fp (floorplan die-width die-height)
         cursor-x 0.0
         cursor-y 0.0
         row-height 0.0]
    (if (empty? remaining)
      fp
      (let [block (first remaining)
            wraps? (> (+ cursor-x (:width block)) die-width)
            cursor-x (if wraps? 0.0 cursor-x)
            cursor-y (if wraps? (+ cursor-y row-height) cursor-y)
            row-height (if wraps? 0.0 row-height)
            placed (assoc block :x cursor-x :y cursor-y)]
        (recur (rest remaining) (add-block fp placed)
               (+ cursor-x (:width block)) cursor-y (max row-height (:height block)))))))
