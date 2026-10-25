(ns rtl.synthesis
  "Gate-level synthesis: netlist, gate types, statistics, optimisation.
  Restored from kami-rtl's `synthesis` module (deleted PR #82).")

(def gate-types #{:and :or :not :nand :nor :xor :xnor :buf :mux :dff})

(defn gate [gate-type inputs output] {:gate-type gate-type :inputs inputs :output output})

(defn gate-netlist
  "A fresh, empty gate-level netlist."
  []
  {:gates [] :primary-inputs [] :primary-outputs []})

(defn- output-map [gates]
  (into {} (map-indexed (fn [i g] [(:output g) i]) gates)))

(defn- depth-of [idx gates omap memo]
  (if-let [d (get @memo idx)]
    d
    (if (= (:gate-type (nth gates idx)) :dff)
      (do (vswap! memo assoc idx 0) 0)
      (let [max-input-depth (reduce
                              (fn [best inp]
                                (if-let [pred (get omap inp)]
                                  (max best (depth-of pred gates omap memo))
                                  best))
                              0 (:inputs (nth gates idx)))
            d (inc max-input-depth)]
        (vswap! memo assoc idx d)
        d))))

(defn- estimate-depth [{:keys [gates]}]
  (let [omap (output-map gates)
        memo (volatile! {})]
    (reduce (fn [best i] (max best (depth-of i gates omap memo))) 0 (range (count gates)))))

(defn stats
  "Summary statistics: gate-count (total, excluding DFF from lut-count),
  lut-count (combinational gates), ff-count (DFF gates), and a naive
  max-frequency estimate (1ns/gate delay along the deepest combinational
  chain)."
  [{:keys [gates] :as netlist}]
  (let [ff-count (count (filter #(= (:gate-type %) :dff) gates))
        comb-count (- (count gates) ff-count)
        depth (estimate-depth netlist)
        delay-ns (double (max depth 1))
        max-freq (/ 1000.0 delay-ns)]
    {:gate-count (count gates) :lut-count comb-count :ff-count ff-count
     :estimated-max-freq-mhz max-freq}))

(defn- eval-gate [gate-type input-vals]
  (case gate-type
    :and (every? true? input-vals)
    :or (some true? input-vals)
    :not (not (first input-vals))
    :nand (not (every? true? input-vals))
    :nor (not (boolean (some true? input-vals)))
    :xor (reduce #(not= %1 %2) false input-vals)
    :xnor (not (reduce #(not= %1 %2) false input-vals))
    :buf (first input-vals)
    :mux (if (>= (count input-vals) 3)
           (if (first input-vals) (nth input-vals 2) (nth input-vals 1))
           ::skip)
    :dff ::skip))

(defn optimize
  "Constant-folding pass: iteratively removes gates whose inputs are all
  tied to constants (`\"1'b0\"`/`\"1'b1\"` or a previously-folded gate's
  output), propagating the resulting constant. DFF gates are never folded
  (sequential — skipped, matches the original)."
  [{:keys [gates] :as netlist}]
  (loop [gates gates
         constants {"1'b0" false "1'b1" true}]
    (let [foldable (keep-indexed
                     (fn [i g]
                       (when (and (every? #(contains? constants %) (:inputs g))
                                  (not= (:gate-type g) :dff))
                         (let [input-vals (mapv constants (:inputs g))
                               result (eval-gate (:gate-type g) input-vals)]
                           (when (not= result ::skip)
                             [i (:output g) result]))))
                     gates)]
      (if (empty? foldable)
        (assoc netlist :gates gates)
        (let [to-remove (set (map first foldable))
              constants (into constants (map (fn [[_ out res]] [out res]) foldable))
              gates (vec (keep-indexed (fn [i g] (when-not (to-remove i) g)) gates))]
          (recur gates constants))))))
