(ns pnr.cts
  "Clock Tree Synthesis — balanced buffer tree construction via recursive
  bisection. Restored from kami-pnr's `cts` module (deleted PR #82)."
  )

(defn cts-spec [{:keys [clock-name target-skew-ps max-transition-ps buffer-cell]}]
  {:clock-name clock-name :target-skew-ps target-skew-ps
   :max-transition-ps max-transition-ps :buffer-cell buffer-cell})

(defn clock-tree-stats
  "Buffer count (root + all level buffers), level count, a rough skew
  estimate (10ps per unit of max-min wire-length spread), and total wire length."
  [{:keys [levels]}]
  (let [wires (mapcat :wire-segments levels)
        lengths (map :length wires)
        num-buffers (+ 1 (reduce + 0 (map #(count (:buffers %)) levels)))
        total-wire-length (reduce + 0.0 lengths)
        max-skew-ps (if (seq lengths)
                      (* (- (apply max lengths) (apply min lengths)) 10.0)
                      0.0)]
    {:num-buffers num-buffers :num-levels (count levels)
     :max-skew-ps max-skew-ps :total-wire-length total-wire-length}))

(defn- centroid [points]
  (let [n (double (count points))]
    [(/ (reduce + 0.0 (map first points)) n)
     (/ (reduce + 0.0 (map second points)) n)]))

(defn- bisect-sinks
  "Split `sinks` in half, sorted along whichever axis (x or y) has the
  larger spread."
  [sinks]
  (let [xs (map first sinks) ys (map second sinks)
        x-spread (- (apply max xs) (apply min xs))
        y-spread (- (apply max ys) (apply min ys))
        sorted (if (>= x-spread y-spread)
                 (sort-by first sinks)
                 (sort-by second sinks))
        mid (quot (count sorted) 2)]
    [(vec (take mid sorted)) (vec (drop mid sorted))]))

(defn- dist [[ax ay] [bx by]]
  (Math/sqrt (+ (Math/pow (- bx ax) 2) (Math/pow (- by ay) 2))))

(defn- find-buf-pos [root levels name]
  (if (= (:name root) name)
    [(:x root) (:y root)]
    (or (some (fn [level] (some (fn [buf] (when (= (:name buf) name) [(:x buf) (:y buf)]))
                                 (:buffers level)))
              levels)
        [(:x root) (:y root)])))

(defn build-clock-tree
  "Build a balanced H-tree clock distribution from `sink-positions` (a seq
  of `[x y]`). Recursive bisection: at each level, split sinks into two
  groups, place a buffer at the centroid of each group (down to groups of
  <=4 sinks), then wire leaf buffers to their sinks."
  [spec sink-positions]
  (if (empty? sink-positions)
    {:root-buffer {:name (str (:clock-name spec) "_root") :cell-type (:buffer-cell spec)
                    :x 0.0 :y 0.0 :load-cap 0.0}
     :levels []}
    (let [[cx cy] (centroid sink-positions)
          root-buffer {:name (str (:clock-name spec) "_root") :cell-type (:buffer-cell spec)
                        :x cx :y cy :load-cap (* (count sink-positions) 0.01)}]
      (loop [current-groups [[(:name root-buffer) (vec sink-positions)]]
             levels []
             buf-counter 0]
        (if (not-any? (fn [[_ sinks]] (> (count sinks) 4)) current-groups)
          ;; final level: wire leaf buffers to sinks
          (let [leaf-wires (mapcat
                             (fn [[parent-name sinks]]
                               (let [parent-pos (find-buf-pos root-buffer levels parent-name)]
                                 (map-indexed
                                  (fn [i sink]
                                    {:from parent-name :to (str "sink_" parent-name "_" i)
                                     :length (dist sink parent-pos) :layer "M2"})
                                  sinks)))
                             current-groups)
                levels (if (seq leaf-wires)
                         (conj levels {:buffers [] :wire-segments (vec leaf-wires)})
                         levels)]
            {:root-buffer root-buffer :levels levels})
          ;; one bisection round
          (let [[level next-groups buf-counter]
                (reduce
                 (fn [[level next-groups buf-counter] [parent-name sinks]]
                   (if (<= (count sinks) 4)
                     [level (conj next-groups [parent-name sinks]) buf-counter]
                     (let [[left right] (bisect-sinks sinks)]
                       (reduce
                        (fn [[level next-groups buf-counter] half]
                          (let [[bx by] (centroid half)
                                buf-name (str (:clock-name spec) "_buf" buf-counter)
                                parent-pos (find-buf-pos root-buffer levels parent-name)
                                wire-len (dist [bx by] parent-pos)
                                buf {:name buf-name :cell-type (:buffer-cell spec)
                                     :x bx :y by :load-cap (* (count half) 0.01)}
                                wire {:from parent-name :to buf-name :length wire-len :layer "M3"}]
                            [(-> level (update :buffers conj buf) (update :wire-segments conj wire))
                             (conj next-groups [buf-name half])
                             (inc buf-counter)]))
                        [level next-groups buf-counter]
                        [left right]))))
                 [{:buffers [] :wire-segments []} [] buf-counter]
                 current-groups)]
            (recur next-groups (conj levels level) buf-counter)))))))
