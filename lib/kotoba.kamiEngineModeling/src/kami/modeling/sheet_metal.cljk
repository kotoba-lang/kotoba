(ns kami.modeling.sheet-metal
  "Sheet metal: bend allowance, flat patterns, and folding back.

  A sheet metal part is a flat blank that a press brake bends. Every dimension
  on the drawing is an OUTSIDE mold-line length — where the two outside faces
  would meet if the bend were a sharp corner — and the blank is shorter than
  their sum, because material at the outside of a bend stretches and material
  at the inside compresses. The line between them, which neither stretches nor
  compresses, sits at `k-factor` of the way through the thickness.

  So the whole subject is one number and its consequences:

      bend allowance   BA = theta (R + K T)          arc length of the neutral line
      outside setback  OSSB = (R + T) tan(theta/2)   OML corner to bend tangent
      bend deduction   BD = 2 OSSB - BA              what the blank is short by
      flat length      = sum(OML) - sum(BD)

  `unfold` produces the blank; `fold` walks the neutral line back into space.
  The test that matters is not that they invert each other — two functions
  sharing a wrong formula invert perfectly — but that the folded path's ARC
  LENGTH, computed from the geometry of the arcs, equals the flat length,
  computed from the deduction formula. Those are different derivations.

  Not here: multi-directional (branching) flanges, curved bend lines, hems,
  jogs, louvres, corner relief, springback compensation, and material-specific
  K-factor tables. `unfold` refuses a part it cannot lay flat rather than
  returning a blank that would be cut wrong."
  (:require [kotoba.lang.text :as string]))

(def ^:private pi #?(:clj Math/PI :cljs js/Math.PI))
(defn- tan [x] (#?(:clj Math/tan :cljs js/Math.tan) x))
(defn- cos [x] (#?(:clj Math/cos :cljs js/Math.cos) x))
(defn- sin [x] (#?(:clj Math/sin :cljs js/Math.sin) x))
(defn- radians [deg] (* pi (/ deg 180.0)))

(defn k-factor-for-ratio
  "A K-factor from the bend radius / thickness ratio, by the table most press
  brake handbooks print for soft mild steel and aluminium.

  It is a STARTING POINT, not a material property: the real value depends on
  alloy, temper, grain direction and the tooling, and shops determine it by
  bending a coupon and measuring. `k-factor-from-flat` is that measurement."
  [r-over-t]
  (cond (< r-over-t 0.5) 0.33
        (< r-over-t 1.0) 0.38
        (< r-over-t 1.5) 0.41
        (< r-over-t 3.0) 0.44
        (< r-over-t 5.0) 0.46
        :else 0.50))

(defn bend-allowance
  "Arc length of the neutral line through one bend. `angle` in degrees is the
  bend angle (90 for a right angle), not the included angle."
  [{:keys [angle radius thickness k-factor]}]
  (* (radians angle) (+ radius (* k-factor thickness))))

(defn outside-setback
  "Distance from the outside mold-line corner to the bend tangent."
  [{:keys [angle radius thickness]}]
  (* (+ radius thickness) (tan (/ (radians angle) 2.0))))

(defn bend-deduction
  "How much shorter the blank is than the sum of the outside mold-line lengths,
  for one bend."
  [bend]
  (- (* 2.0 (outside-setback bend)) (bend-allowance bend)))

(defn- bend-with-defaults [{:keys [thickness k-factor]} bend]
  (let [r (:radius bend thickness)
        k (or (:k-factor bend) k-factor (k-factor-for-ratio (/ r thickness)))]
    (assoc bend :thickness thickness :radius r :k-factor k)))

(defn- validation-error [{:keys [thickness flanges bends] :as part}]
  (cond
    (not (and (number? thickness) (pos? thickness)))
    (str "sheet metal needs a positive :thickness (got " (pr-str thickness) ")")

    (or (empty? flanges) (some #(not (and (number? %) (pos? %))) flanges))
    (str "flanges must be positive outside mold-line lengths (got " (pr-str flanges) ")")

    (not= (count flanges) (inc (count bends)))
    (str "a chain of " (count bends) " bend(s) needs " (inc (count bends))
         " flange(s), got " (count flanges) ". This unfolds a SINGLE chain of"
         " flanges; branching flanges, hems and jogs are not laid flat here"
         " because the blank they need is not a function of this chain alone.")

    :else
    (let [bs (map #(bend-with-defaults part %) bends)]
      (cond
        (some #(not (and (number? (:angle %)) (< 0 (:angle %) 180))) bs)
        (str "every bend needs an :angle in (0, 180) degrees, got "
             (pr-str (mapv :angle bs)))

        (some #(not (<= 0.0 (:k-factor %) 0.5)) bs)
        (str "a K-factor outside [0, 0.5] puts the neutral line outside the"
             " material, got " (pr-str (mapv :k-factor bs)))

        (some #(neg? (:radius %)) bs)
        (str "bend radius cannot be negative, got " (pr-str (mapv :radius bs)))

        ;; A flange has to reach past the setbacks on both of its ends, or the
        ;; bends overlap and the "flat pattern" describes a blank that cannot
        ;; be bent. Returning one anyway is how a part gets cut wrong.
        :else
        (let [sb (mapv outside-setback bs)
              needed (map-indexed (fn [i _]
                                    (+ (if (pos? i) (nth sb (dec i)) 0.0)
                                       (if (< i (count bs)) (nth sb i) 0.0)))
                                  flanges)
              short (keep-indexed (fn [i f] (when (< f (nth needed i)) [i f (nth needed i)]))
                                  flanges)]
          (when (seq short)
            (str "flange(s) " (pr-str (mapv first short)) " are shorter than their"
                 " own setbacks — the bends would overlap: "
                 (string/join ", " (map (fn [[i f n]]
                                          (str "flange " i " is " f " but needs " n))
                                        short)))))))))

(defn flat-length
  "Blank length for a chain of outside mold-line flanges and the bends between
  them. Returns `[:ok length]` or `[:error msg]`."
  [{:keys [flanges bends] :as part}]
  (if-let [e (validation-error part)]
    [:error e]
    [:ok (- (reduce + flanges)
            (reduce + (map #(bend-deduction (bend-with-defaults part %)) bends)))]))

(defn unfold
  "The flat pattern: total blank length, and where each bend zone falls on it.

  Bend lines are given at the MIDDLE of each bend zone, which is where a press
  brake operator scribes them, and the zone itself is reported so a nesting
  program can keep cutouts out of it."
  [{:keys [flanges bends] :as part}]
  (if-let [e (validation-error part)]
    [:error e]
    (let [bs (mapv #(bend-with-defaults part %) bends)
          [_ total] (flat-length part)]
      (loop [i 0 x 0.0 segs [] lines []]
        (if (= i (count flanges))
          [:ok {:flat/length total
                :flat/segments segs
                :flat/bend-lines lines
                :flat/bends (mapv (fn [b] {:bend/angle (:angle b)
                                           :bend/radius (:radius b)
                                           :bend/k-factor (:k-factor b)
                                           :bend/allowance (bend-allowance b)
                                           :bend/deduction (bend-deduction b)
                                           :bend/direction (:direction b :up)})
                                  bs)}]
          (let [f (nth flanges i)
                ;; tangent-to-tangent length of this flange on the blank
                lead (if (pos? i) (outside-setback (nth bs (dec i))) 0.0)
                trail (if (< i (count bs)) (outside-setback (nth bs i)) 0.0)
                straight (- f lead trail)
                x1 (+ x straight)
                ba (when (< i (count bs)) (bend-allowance (nth bs i)))]
            (recur (inc i)
                   (if ba (+ x1 ba) x1)
                   (cond-> (conj segs {:segment/kind :flange :segment/index i
                                       :segment/from x :segment/to x1})
                     ba (conj {:segment/kind :bend-zone :segment/index i
                               :segment/from x1 :segment/to (+ x1 ba)
                               :segment/allowance ba}))
                   (if ba (conj lines (+ x1 (* 0.5 ba))) lines))))))))

(defn fold
  "Walk the neutral line of the folded part in the XY plane.

  Returns the polyline of the neutral line, sampling each bend arc, and the
  arc-length of the whole path. That length is computed from the GEOMETRY —
  straight runs plus sampled arc chords are not used; each arc contributes
  `radius * angle` with the neutral radius — so comparing it against
  `flat-length` compares two derivations, not one formula against itself."
  ([part] (fold part 32))
  ([{:keys [flanges bends] :as part} arc-samples]
   (if-let [e (validation-error part)]
     [:error e]
     (let [bs (mapv #(bend-with-defaults part %) bends)]
       (loop [i 0 p [0.0 0.0] heading 0.0 pts [[0.0 0.0]] len 0.0]
         (if (= i (count flanges))
           [:ok {:fold/points pts :fold/length len}]
           (let [f (nth flanges i)
                 lead (if (pos? i) (outside-setback (nth bs (dec i))) 0.0)
                 trail (if (< i (count bs)) (outside-setback (nth bs i)) 0.0)
                 straight (- f lead trail)
                 p1 [(+ (nth p 0) (* straight (cos heading)))
                     (+ (nth p 1) (* straight (sin heading)))]
                 pts (conj pts p1)]
             (if (>= i (count bs))
               (recur (inc i) p1 heading pts (+ len straight))
               (let [b (nth bs i)
                     rn (+ (:radius b) (* (:k-factor b) (:thickness b)))
                     sweep (radians (:angle b))
                     dir (if (= :down (:direction b :up)) -1.0 1.0)
                     ;; centre is perpendicular to the heading, on the inside
                     cx (+ (nth p1 0) (* rn (cos (+ heading (* dir (/ pi 2.0))))))
                     cy (+ (nth p1 1) (* rn (sin (+ heading (* dir (/ pi 2.0))))))
                     start-a (+ heading (* dir (- (/ pi 2.0))))
                     arc (mapv (fn [s]
                                 (let [a (+ start-a (* dir sweep (/ s (double arc-samples))))]
                                   [(+ cx (* rn (cos a))) (+ cy (* rn (sin a)))]))
                               (range 1 (inc arc-samples)))]
                 (recur (inc i) (last arc) (+ heading (* dir sweep))
                        (into pts arc)
                        (+ len straight (* rn sweep))))))))))))

(defn k-factor-from-flat
  "The K-factor implied by a blank that was actually cut and bent — the
  measurement a shop makes with a test coupon, run backwards.

  Solving `flat = sum(OML) - sum(2 OSSB - BA)` for K when every bend shares
  one K: the setbacks do not contain K, so it falls out linearly."
  [{:keys [flanges bends thickness]} measured-flat]
  (let [bs (map #(assoc % :thickness thickness :radius (:radius % thickness)) bends)
        sum-oml (reduce + flanges)
        sum-sb (reduce + (map #(* 2.0 (outside-setback %)) bs))
        sum-theta (reduce + (map #(radians (:angle %)) bs))
        sum-theta-r (reduce + (map #(* (radians (:angle %)) (:radius %)) bs))
        ;; flat = sum-oml - sum-sb + sum-theta-r + K * T * sum-theta
        k (/ (- measured-flat (- sum-oml sum-sb) sum-theta-r) (* thickness sum-theta))]
    (if (<= 0.0 k 0.5)
      [:ok k]
      [:error (str "a flat of " measured-flat " implies K = " k
                   ", which puts the neutral line outside the material —"
                   " check the bend radius or the measurement")])))
