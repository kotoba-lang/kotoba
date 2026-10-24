(ns ic-packaging.bonding
  "Wire bond and flip chip bonding diagram generation. Restored from
  kami-pkg's `bonding` module (deleted PR #82).")

;; BondType variants
(defn wire-bond [wire-diameter-um loop-height-um]
  {:kind :wire-bond :wire-diameter-um wire-diameter-um :loop-height-um loop-height-um})
(defn flip-chip [bump-pitch-um bump-diameter-um]
  {:kind :flip-chip :bump-pitch-um bump-pitch-um :bump-diameter-um bump-diameter-um})
(defn thermo-compression [] {:kind :thermo-compression})

(defn pad-location [name x y] {:name name :x x :y y})

(defn bond [{:keys [pad-name die-x die-y pkg-x pkg-y bond-type]}]
  {:pad-name pad-name :die-x die-x :die-y die-y :pkg-x pkg-x :pkg-y pkg-y :bond-type bond-type})

(defn bond-diagram [bonds] {:bonds (vec bonds)})

(defn generate-bond-diagram
  "Generate a bond diagram connecting `die-pads` to `pkg-pads` in order
  (index-matched). `bond-type` is applied uniformly to all connections."
  [die-pads pkg-pads bond-type]
  (let [count (min (count die-pads) (count pkg-pads))
        bonds (mapv (fn [i]
                      (let [dp (nth die-pads i) pp (nth pkg-pads i)]
                        (bond {:pad-name (:name dp) :die-x (:x dp) :die-y (:y dp)
                               :pkg-x (:x pp) :pkg-y (:y pp) :bond-type bond-type})))
                    (range count))]
    (bond-diagram bonds)))
