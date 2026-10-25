(ns pnr.placement
  "Standard cell placement — greedy left-to-right row-based placement.
  Restored from kami-pnr's `placement` module (deleted PR #82).")

(def orientations #{:n :s :fn :fs :w :e :fw :fe})

(defn placement-row [{:keys [y height site-width num-sites]}]
  {:y y :height height :site-width site-width :num-sites num-sites})

(defn row-total-width [row] (* (:site-width row) (:num-sites row)))

(defn placement
  "A fresh placement container over `rows`, no cells placed yet."
  [rows]
  {:rows (vec rows) :cells []})

(defn placement-stats
  "Total cells, row-area utilization, and a bounding-box HPWL estimate."
  [{:keys [rows cells]}]
  (let [total-cells (count cells)
        total-row-area (reduce + 0.0 (map #(* (row-total-width %) (:height %)) rows))
        cell-area (reduce + 0.0
                           (map (fn [c]
                                  (if-let [row (get rows (:row-idx c))]
                                    (* (:site-width row) (:height row))
                                    0.0))
                                cells))
        utilization (if (pos? total-row-area) (/ cell-area total-row-area) 0.0)
        hpwl (if (>= (count cells) 2)
               (let [xs (map :x cells) ys (map :y cells)]
                 (+ (- (apply max xs) (apply min xs))
                    (- (apply max ys) (apply min ys))))
               0.0)]
    {:total-cells total-cells :utilization utilization :hpwl hpwl}))

(defn netlist-cell [{:keys [cell-name instance-name width-sites]}]
  {:cell-name cell-name :instance-name instance-name :width-sites width-sites})

(defn place-cells
  "Greedy left-to-right placement: fill rows sequentially, alternating
  orientation per row (`:n` even rows, `:fs` odd rows) for abutment. Cells
  that overflow all rows are silently dropped (matches the original, which
  logs a warning and breaks)."
  [netlist rows]
  (loop [remaining netlist
         cells []
         row-idx 0
         site-cursor 0]
    (if (empty? remaining)
      {:rows (vec rows) :cells cells}
      (let [rows-v (vec rows)
            ;; advance to a row with space
            [row-idx site-cursor]
            (loop [row-idx row-idx site-cursor site-cursor]
              (if (>= row-idx (count rows-v))
                [row-idx site-cursor]
                (if (<= (+ site-cursor (:width-sites (first remaining)))
                        (:num-sites (nth rows-v row-idx)))
                  [row-idx site-cursor]
                  (recur (inc row-idx) 0))))]
        (if (>= row-idx (count rows-v))
          {:rows rows-v :cells cells} ; overflow — stop, matches original `break`
          (let [cell (first remaining)
                row (nth rows-v row-idx)
                orientation (if (even? row-idx) :n :fs)
                x (* site-cursor (:site-width row))
                y (:y row)
                placed {:cell-name (:cell-name cell) :instance-name (:instance-name cell)
                        :x x :y y :orientation orientation :row-idx row-idx}]
            (recur (rest remaining) (conj cells placed) row-idx (+ site-cursor (:width-sites cell)))))))))
