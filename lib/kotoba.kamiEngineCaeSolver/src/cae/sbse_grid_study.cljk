(ns cae.sbse-grid-study
  "Wall-resolved NASA SBSE mesh family and nonuniform three-grid GCI helpers.")

(def grids
  {:coarse {:level :coarse :nx 36 :ny 64 :nz 18 :wall-normal-grading 10.0
            :boundary-layer-thickness-m 0.05 :boundary-layer-cells 40 :boundary-layer-grading 500.0}
   :medium {:level :medium :nx 54 :ny 96 :nz 27 :wall-normal-grading 10.0
            :boundary-layer-thickness-m 0.05 :boundary-layer-cells 60 :boundary-layer-grading 500.0}
   :fine {:level :fine :nx 72 :ny 128 :nz 36 :wall-normal-grading 10.0
          :boundary-layer-thickness-m 0.05 :boundary-layer-cells 80 :boundary-layer-grading 500.0}})

(defn grid [level]
  (or (get grids level) (throw (ex-info "unknown SBSE grid level" {:level level :available (keys grids)}))))

(defn layer-metrics
  "OpenFOAM simpleGrading is last/first cell width. Return the geometric
  expansion and first layer for a local floor-to-ceiling height."
  [{:keys [ny wall-normal-grading]} height-m]
  (when-not (and (pos-int? ny) (> wall-normal-grading 1.0) (pos? height-m))
    (throw (ex-info "valid wall-normal grid and height required" {})))
  (let [ratio (Math/pow wall-normal-grading (/ 1.0 (dec ny)))
        sum (/ (- (Math/pow ratio ny) 1.0) (- ratio 1.0))]
    {:cell-expansion-ratio ratio :first-layer-height-m (/ height-m sum)
     :last-layer-height-m (* (/ height-m sum) (Math/pow ratio (dec ny)))}))

(defn enrich [grid]
  (let [layer {:ny (:boundary-layer-cells grid)
               :wall-normal-grading (:boundary-layer-grading grid)}
        low (layer-metrics layer (:boundary-layer-thickness-m grid))
        high low]
    (merge grid {:cells (* (:nx grid) (:ny grid) (:nz grid))
                 :blocks (* (:nx grid) (:nz grid))
                 :minimum-first-layer-height-m (:first-layer-height-m low)
                 :maximum-first-layer-height-m (:first-layer-height-m high)
                 :cell-expansion-ratio (:cell-expansion-ratio high)
                 :boundary-layer-thickness-m (:boundary-layer-thickness-m grid)
                 :boundary-layer-cells (:boundary-layer-cells grid)
                 :boundary-layer-grading (:boundary-layer-grading grid)})))

(defn family [] (mapv #(enrich (grid %)) [:coarse :medium :fine]))

(defn effective-refinement-ratio [coarser finer]
  (Math/pow (/ (double (:cells finer)) (:cells coarser)) (/ 1.0 3.0)))

(defn three-grid-gci
  "Generalized observed order for unequal effective refinement ratios. Solves
  the Celik/Roache order equation by fixed-point iteration and fails closed for
  oscillatory/non-finite sequences. Values are coarse, medium, fine."
  [{:keys [coarse medium fine coarse-grid medium-grid fine-grid safety-factor]
    :or {safety-factor 1.25}}]
  (let [e32 (- coarse medium) e21 (- medium fine)
        monotonic? (pos? (* e32 e21))
        r21 (effective-refinement-ratio medium-grid fine-grid)
        r32 (effective-refinement-ratio coarse-grid medium-grid)
        ratio (when monotonic? (/ (Math/abs e32) (Math/abs e21)))
        p (when (and ratio (pos? ratio))
            (loop [p (/ (Math/log ratio) (Math/log r21)) i 0]
              (let [p (max 0.01 (min 10.0 p))
                    correction (/ (Math/log (/ (- (Math/pow r21 p) 1.0)
                                                (- (Math/pow r32 p) 1.0)))
                                  (Math/log r21))
                    next (+ (/ (Math/log ratio) (Math/log r21)) correction)]
                (if (or (>= i 100) (< (Math/abs (- next p)) 1.0e-10)) next
                    (recur next (inc i))))))
        denominator (when p (- (Math/pow r21 p) 1.0))
        extrapolated (when (and denominator (not (zero? denominator))) (+ fine (/ (- fine medium) denominator)))
        gci (when (and denominator (not (zero? denominator)))
              (/ (* safety-factor (Math/abs (- fine medium)))
                 (* (max (Math/abs fine) 1.0e-30) (Math/abs denominator))))]
    {:coarse coarse :medium medium :fine fine :r21 r21 :r32 r32
     :monotonic? monotonic? :observed-order p :richardson-extrapolated extrapolated
     :fine-grid-gci gci :passed? (boolean (and monotonic? p (pos? p) gci))}))
