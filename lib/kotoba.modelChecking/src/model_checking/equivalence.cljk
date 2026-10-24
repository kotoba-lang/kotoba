(ns model-checking.equivalence
  "Combinational equivalence checking between golden and revised gate-
  level netlists. Uses exhaustive input-vector comparison for small
  circuits (< 20 inputs); structured for future BDD-based expansion.
  Restored from kami-verify's `equivalence` module (kami-engine/
  kami-verify/src/lib.rs, deleted PR #82). A gate is a `[output-name
  gate-type input-names]` triple.")

(def equiv-statuses #{:pass :fail :inconclusive})

(defn mismatch [output-name golden-value revised-value input-vector]
  {:output-name output-name :golden-value golden-value :revised-value revised-value
   :input-vector input-vector})

(defn equiv-result [status mismatches checked-points time-ms]
  {:status status :mismatches mismatches :checked-points checked-points :time-ms time-ms})

(defn- eval-gate [gate-type inputs]
  (case gate-type
    "AND" (every? true? inputs)
    "OR" (boolean (some true? inputs))
    "NOT" (not (first inputs))
    "XOR" (reduce #(not= %1 %2) false inputs)
    "NAND" (not (every? true? inputs))
    "NOR" (not (boolean (some true? inputs)))
    "BUF" (boolean (first inputs))
    false))

(defn- simulate
  "Simulate `gates` for one `input-vector`. Returns `{signal-name -> value}`."
  [gates primary-inputs input-vector]
  (let [signals0 (into {} (map vector primary-inputs input-vector))]
    (reduce
     (fn [signals _]
       (reduce
        (fn [signals [out gate-type ins]]
          (let [vals (map #(get signals %) ins)]
            (if (every? some? vals)
              (assoc signals out (eval-gate gate-type vals))
              signals)))
        signals gates))
     signals0
     (range (inc (count gates))))))

(defn- primary-inputs
  "Names referenced as gate inputs but never produced as gate outputs
  (order-preserving, first-seen)."
  [gates]
  (let [outputs (into #{} (map first gates))]
    (vec (distinct (mapcat (fn [[_ _ ins]] (remove outputs ins)) gates)))))

(defn- primary-outputs
  "Gate outputs never consumed by another gate."
  [gates]
  (let [consumed (into #{} (mapcat (fn [[_ _ ins]] ins) gates))]
    (mapv first (remove (fn [[o _ _]] (consumed o)) gates))))

(defn- union-preserve-order [a b]
  (vec (concat a (remove (set a) b))))

(defn check-equivalence
  "Exhaustive equivalence check between `golden-gates` and `revised-gates`
  for small combinational circuits (< 20 combined inputs). For larger
  circuits the result is `:inconclusive`."
  [golden-gates revised-gates]
  (let [pi (union-preserve-order (primary-inputs golden-gates) (primary-inputs revised-gates))]
    (if (> (count pi) 20)
      (equiv-result :inconclusive [] 0 0)
      (let [outputs (union-preserve-order (primary-outputs golden-gates) (primary-outputs revised-gates))
            total (bit-shift-left 1 (count pi))
            mismatches
            (vec
             (mapcat
              (fn [idx]
                (let [vec-in (mapv (fn [b] (= 1 (bit-and (bit-shift-right idx b) 1))) (range (count pi)))
                      g (simulate golden-gates pi vec-in)
                      r (simulate revised-gates pi vec-in)]
                  (keep
                   (fn [out]
                     (let [gv (boolean (get g out false))
                           rv (boolean (get r out false))]
                       (when (not= gv rv)
                         (mismatch out (str gv) (str rv) vec-in))))
                   outputs)))
              (range total)))
            status (if (empty? mismatches) :pass :fail)]
        (equiv-result status mismatches total 0)))))
