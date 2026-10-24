(ns kotoba.fea.fatigue
  "Spectrum fatigue damage accumulation (Miner's rule) over a Basquin S-N
  curve — the smallest upstream contract that lets a stress history
  (e.g. duty-cycle load spectra of the magnesium-hydrogen PEMFC electric-drive
  vehicle, or FEA post-processed stress ranges) be turned into an auditable
  cumulative-damage number.

  This namespace is deliberately *not* a material-property authority. Every
  curve parameter must arrive with `:provenance` (`{:source string,
  :date string}` minimum); a call without provenance throws, because an
  unlabelled curve would let invented Mg/MgH2 or structural-fatigue constants
  silently pass for measured ones. Unknown quantities stay unmeasured: this
  contract only divides and sums — it never estimates a constant.

  Curve form (SI units):
    `{:type :basquin, :basquin-b (1/cycles exponent, negative),
      :basquin-C (cycles * Pa^b scale), :endurance-limit-Pa (optional)`
  Basquin life: `N(Sa) = C * Sa^b` for `Sa > :endurance-limit-Pa`; at or
  below the endurance limit the block is treated as non-damaging (infinite
  life, contributes zero damage). Without an endurance limit every positive
  stress range damages.

  Spectrum blocks: `{:stress-range-Pa (> 0), :cycles (> 0)}` — constant
  amplitude blocks; cycle counting (rainflow etc.) is out of scope here.

  100% pure/portable `.cljc`, no I/O, matching this repo's domain-namespace
  convention.")

(defn- pow* [x e] #?(:clj (Math/pow x e) :cljs (js/Math.pow x e)))

(defn- require!
  [cond msg data]
  (when-not cond (throw (ex-info msg data))))

(defn- positive!
  ([m ks] (positive! m ks nil))
  ([m ks extra]
   (doseq [k ks]
     (let [v (get m k)]
       (require! (and (number? v) (pos? v))
                 (str "must be a positive number: " (name k))
                 (assoc extra :key k :value v))))))

(def provenance-required
  "Minimum `:provenance` keys every S-N curve must carry."
  [:source :date])

(defn curve
  "Validate and return a fatigue S-N curve map. `m` must be a `:basquin`
  curve with `:basquin-b` (negative), `:basquin-C` (positive), optional
  non-negative `:endurance-limit-Pa`, and a `:provenance` map carrying
  `:source` and `:date`. Throws ex-info on violation. The returned map is the input, unchanged."
  [m]
  (require! (map? m) "curve must be a map" {:curve m})
  (require! (= :basquin (:type m)) "only :type :basquin curves are supported"
            {:type (:type m) :supported [:basquin]})
  (require! (map? (:provenance m)) "curve requires :provenance {:source :date}"
            {:curve (dissoc m :provenance)})
  (doseq [k provenance-required]
    (require! (or (string? (get (:provenance m) k))
                  (keyword? (get (:provenance m) k)))
              (str "provenance requires " (name k))
              {:provenance (select-keys (:provenance m) provenance-required)
               :key k}))
  (require! (number? (:basquin-b m)) ":basquin-b must be a number" {:value (:basquin-b m)})
  (require! (neg? (:basquin-b m)) ":basquin-b must be negative (life decreases with stress range)"
            {:value (:basquin-b m)})
  (positive! m [:basquin-C])
  (when-some [el (:endurance-limit-Pa m)]
    (require! (and (number? el) (not (neg? el)))
              ":endurance-limit-Pa must be a non-negative number" {:value el}))
  m)

(defn basquin-cycles
  "Cycles to failure `N` at constant stress range `stress-range-Pa` under
  the validated Basquin `curve`: `N = C * Sa^b`. Returns `:infinite` when an
  endurance limit is present and `stress-range-Pa` is at or below it."
  [curve stress-range-Pa]
  (require! (number? stress-range-Pa) "stress range must be a number"
            {:value stress-range-Pa})
  (require! (pos? stress-range-Pa) "stress range must be positive"
            {:value stress-range-Pa})
  (if (and (:endurance-limit-Pa curve)
           (<= stress-range-Pa (:endurance-limit-Pa curve)))
    :infinite
    (* (:basquin-C curve) (pow* stress-range-Pa (:basquin-b curve)))))

(defn damage
  "Miner damage of one constant-amplitude block `block`
  (`:stress-range-Pa`, `:cycles`) against validated `curve`:
  `cycles / N(stress-range-Pa)`. Non-damaging (at/below endurance limit)
  blocks return exactly `0.0`. Throws ex-info on malformed input."
  [curve block]
  (require! (map? block) "block must be a map" {:block block})
  (positive! block [:stress-range-Pa :cycles] {:block block})
  (let [n (basquin-cycles curve (:stress-range-Pa block))]
    (if (= :infinite n)
      0.0
      (/ (double (:cycles block)) (double n)))))

(defn spectrum-damage
  "Miner cumulative damage for a load spectrum — a sequence of constant
  amplitude blocks (`:stress-range-Pa`, `:cycles`) — against validated
  `curve`. Returns:

    {:damage-per-block [d0 d1 ...]          ; order-preserving, per input block
     :total-damage d                        ; sum (Miner's rule)
     :fatigue-margin (- 1 d)                ; > 0 means life remains at the
     :criterion :miner-linear               ; stated spectrum, per Miner
     :curve (:type + provenance echoed)}
  plus `:non-damaging-blocks` (count at/below the endurance limit).

  Always echoes `:curve` provenance so downstream datoms keep material
  provenance. Throws ex-info on any malformed block."
  [curve blocks]
  (require! (sequential? blocks) "spectrum must be a sequence of blocks"
            {:blocks blocks})
  (let [per-block (mapv #(damage curve %) blocks)
        total (reduce + 0.0 per-block)
        non-damaging (count (filter #(and (:endurance-limit-Pa curve)
                                          (<= (:stress-range-Pa %)
                                              (:endurance-limit-Pa curve)))
                                    blocks))]
    {:damage-per-block per-block
     :total-damage total
     :fatigue-margin (- 1.0 total)
     :non-damaging-blocks non-damaging
     :criterion :miner-linear
     :curve {:type (:type curve)
             :provenance (:provenance curve)}}))
