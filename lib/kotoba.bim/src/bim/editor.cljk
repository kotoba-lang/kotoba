(ns bim.editor
  "Pure BIM editor state: atomic serializable transactions, undo/redo,
  selection, and deterministic geometric snapping."
  (:require [kotoba.lang.coll :as coll]))

(def schema-version 1)

(defn editor-state [document]
  {:editor/schema-version schema-version :editor/document document
   :editor/undo [] :editor/redo [] :editor/selection #{}})

(defn- collection-indexed? [value] (or (vector? value) (sequential? value)))

(defn- apply-operation [document {:keys [op path value index]}]
  (case op
    :set
    (let [parent (get-in document (pop path)) key (peek path)
          existed? (if (map? parent) (contains? parent key)
                       (and (collection-indexed? parent) (< -1 key (count parent))))
          old (get-in document path)]
      [(assoc-in document path value)
       (if existed? {:op :set :path path :value old} {:op :dissoc :path path})])

    :dissoc
    (let [parent-path (pop path) key (peek path) parent (get-in document parent-path)]
      (when-not (and (map? parent) (contains? parent key))
        (throw (ex-info "transaction dissoc target does not exist" {:path path})))
      [(if (empty? parent-path) (dissoc document key)
           (update-in document parent-path dissoc key))
       {:op :set :path path :value (get parent key)}])

    :insert
    (let [items (vec (get-in document path)) position (or index (count items))]
      (when-not (<= 0 position (count items))
        (throw (ex-info "transaction insert index is out of bounds"
                        {:path path :index position :count (count items)})))
      [(assoc-in document path (vec (concat (subvec items 0 position) [value]
                                            (subvec items position))))
       {:op :remove :path path :index position}])

    :remove
    (let [items (vec (get-in document path))]
      (when-not (< -1 index (count items))
        (throw (ex-info "transaction remove index is out of bounds"
                        {:path path :index index :count (count items)})))
      [(assoc-in document path (vec (concat (subvec items 0 index)
                                            (subvec items (inc index)))))
       {:op :insert :path path :index index :value (nth items index)}])

    (throw (ex-info "unsupported editor operation" {:operation op}))))

(defn- apply-operations [document operations]
  (reduce (fn [[current inverses] operation]
            (let [[next-document inverse] (apply-operation current operation)]
              [next-document (conj inverses inverse)]))
          [document []] operations))

(defn transact
  "Apply all operations atomically and record their inverses as one undo unit."
  [state {:keys [id label operations] :as transaction}]
  (when-not (seq operations)
    (throw (ex-info "editor transaction requires operations" {:transaction transaction})))
  (let [[document inverses] (apply-operations (:editor/document state) operations)
        entry {:transaction/id id :transaction/label label
               :transaction/operations (vec operations)
               :transaction/inverses (vec (reverse inverses))}]
    (-> state
        (assoc :editor/document document :editor/redo [])
        (update :editor/undo conj entry))))

(defn undo [state]
  (if-let [entry (peek (:editor/undo state))]
    (let [[document _] (apply-operations (:editor/document state)
                                         (:transaction/inverses entry))]
      (-> state (assoc :editor/document document)
          (update :editor/undo pop) (update :editor/redo conj entry)))
    state))

(defn redo [state]
  (if-let [entry (peek (:editor/redo state))]
    (let [[document _] (apply-operations (:editor/document state)
                                         (:transaction/operations entry))]
      (-> state (assoc :editor/document document)
          (update :editor/redo pop) (update :editor/undo conj entry)))
    state))

(defn select
  ([state ids] (select state ids :replace))
  ([state ids mode]
   (let [ids (set ids)]
     (update state :editor/selection
             (fn [selection]
               (case mode :replace ids :add (coll/set-union selection ids)
                     :remove (coll/set-difference selection ids)
                     :toggle (reduce (fn [result id]
                                       (if (contains? result id) (disj result id) (conj result id)))
                                     selection ids)
                     (throw (ex-info "unsupported selection mode" {:mode mode}))))))))

(defn- snap-distance-rank [distance]
  (#?(:clj Math/round :cljs js/Math.round) (/ distance 1.0e-9)))

(defn snap-point
  "Return the nearest endpoint/midpoint/intersection/grid candidate in tolerance."
  [point candidates {:keys [grid tolerance] :or {tolerance 0.15}}]
  (let [dimension (count point)
        grid-point (when (and (number? grid) (pos? grid))
                     (mapv #(* grid (#?(:clj Math/round :cljs js/Math.round) (/ % grid))) point))
        candidates (cond-> (vec candidates)
                     grid-point (conj {:snap/kind :grid :snap/point grid-point}))
        distance (fn [candidate]
                   (#?(:clj Math/sqrt :cljs js/Math.sqrt)
                    (reduce + (map (fn [a b] (let [delta (- a b)] (* delta delta)))
                                   point (:snap/point candidate)))))
        ranked (sort-by (juxt #(snap-distance-rank (distance %))
                              #(case (:snap/kind %) :endpoint 0 :intersection 1
                                     :midpoint 2 :grid 3 4)
                              distance)
                        candidates)
        winner (first ranked)]
    (when (and winner (= dimension (count (:snap/point winner)))
               (<= (distance winner) tolerance))
      (assoc winner :snap/distance (distance winner)))))

(defn- closed-segments [points]
  (let [points (vec points)]
    (if (< (count points) 2) []
        (mapv vec (partition 2 1 (conj points (first points)))))))

(declare geometry-snap-segments)

(defn- curve-snap-segments [curve]
  (case (:kind curve)
    (:polyline :indexed-polycurve :b-spline-curve)
    (mapv vec (partition 2 1 (or (:points curve) (:control-points curve))))
    :composite-curve (vec (mapcat #(curve-snap-segments (:parent-curve %))
                                  (:segments curve)))
    []))

(defn- bound-snap-segments [bound]
  (if (seq (:edges bound))
    (mapv (fn [edge] [(:start edge) (:end edge)]) (:edges bound))
    (closed-segments (:points bound))))

(defn- tessellated-segments [geometry]
  (let [coordinates (:coordinates geometry)
        index-rings (case (:kind geometry)
                      :triangulated-face-set (:coord-indices geometry)
                      :polygonal-face-set (mapcat #(cons (:outer %) (:inners %))
                                                  (:faces geometry))
                      [])]
    (->> index-rings
         (mapcat (fn [indices]
                   (closed-segments (mapv #(nth coordinates (dec %)) indices))))
         (map (fn [[a b]] (if (neg? (compare a b)) [a b] [b a])))
         distinct
         vec)))

(defn- extruded-snap-segments [geometry]
  (let [profile (:profile geometry)
        profile-points
        (case (:kind profile)
          :rectangle (let [half-x (/ (or (:x-dim profile) (:width profile) 0.0) 2.0)
                           half-y (/ (or (:y-dim profile) (:depth profile) 0.0) 2.0)]
                       [[(- half-x) (- half-y)] [half-x (- half-y)]
                        [half-x half-y] [(- half-x) half-y]])
          :arbitrary-closed (vec (distinct (:points profile)))
          [])
        [ox oy oz] (get-in geometry [:position :location] [0.0 0.0 0.0])
        [px py] (get-in profile [:position :location] [0.0 0.0])
        [dx dy dz] (or (:direction geometry) [0.0 0.0 1.0])
        depth (or (:depth geometry) 0.0)
        bottom (mapv (fn [[x y]] [(+ ox px x) (+ oy py y) oz]) profile-points)
        top (mapv (fn [point] (mapv + point [(* dx depth) (* dy depth) (* dz depth)]))
                  bottom)]
    (vec (concat (closed-segments bottom) (closed-segments top)
                 (map vector bottom top)))))

(defn geometry-snap-segments
  "Return finite line segments that define meaningful authoring snaps."
  [geometry]
  (case (:kind geometry)
    :axis-sweep (if (= 2 (count (:axis geometry))) [(:axis geometry)] [])
    :slab-extrusion (closed-segments (:boundary geometry))
    :extruded-area-solid (extruded-snap-segments geometry)
    :swept-disk-solid (mapv vec (partition 2 1 (:directrix geometry)))
    (:fixed-reference-swept-area-solid :surface-curve-swept-area-solid)
    (curve-snap-segments (:directrix geometry))
    (:faceted-brep :advanced-brep)
    (vec (mapcat (fn [face] (mapcat bound-snap-segments (:bounds face)))
                 (:faces geometry)))
    (:triangulated-face-set :polygonal-face-set) (tessellated-segments geometry)
    :collection (vec (mapcat geometry-snap-segments (:items geometry)))
    :boolean-result (vec (concat (geometry-snap-segments (:first-operand geometry))
                                 (geometry-snap-segments (:second-operand geometry))))
    []))

(defn element-snap-segments
  "Attach element identity to every authoring segment in its geometry."
  [element]
  (mapv (fn [[start end]]
          {:element/id (:id element) :segment/start (vec start) :segment/end (vec end)})
        (geometry-snap-segments (:geometry element))))

(defn- midpoint [a b] (mapv #(/ (+ %1 %2) 2.0) a b))
(defn- cross2 [[ax ay] [bx by]] (- (* ax by) (* ay bx)))

(defn- segment-intersection [left right]
  (let [p (:segment/start left) p2 (:segment/end left)
        q (:segment/start right) q2 (:segment/end right)
        r (mapv - p2 p) s (mapv - q2 q)
        denominator (cross2 r s)]
    (when (> (#?(:clj Math/abs :cljs js/Math.abs) denominator) 1.0e-12)
      (let [q-p (mapv - q p)
            t (/ (cross2 q-p s) denominator)
            u (/ (cross2 q-p r) denominator)]
        (when (and (< 1.0e-9 t (- 1.0 1.0e-9))
                   (< 1.0e-9 u (- 1.0 1.0e-9)))
          (let [point (mapv + p (mapv #(* t %) r))
                other (mapv + q (mapv #(* u %) s))]
            (when (or (< (count point) 3)
                      (< (#?(:clj Math/abs :cljs js/Math.abs)
                          (- (nth point 2) (nth other 2))) 1.0e-6))
              point)))))))

(defn model-snap-candidates
  "Build deterministic endpoint, midpoint, and cross-element intersection snaps."
  [elements]
  (let [segments (vec (mapcat element-snap-segments elements))
        endpoint-candidates
        (mapcat (fn [segment]
                  [{:snap/kind :endpoint :snap/point (:segment/start segment)
                    :element/id (:element/id segment)}
                   {:snap/kind :endpoint :snap/point (:segment/end segment)
                    :element/id (:element/id segment)}]) segments)
        midpoint-candidates
        (map (fn [segment]
               {:snap/kind :midpoint
                :snap/point (midpoint (:segment/start segment) (:segment/end segment))
                :element/id (:element/id segment)}) segments)
        intersections
        (for [left-index (range (count segments))
              right-index (range (inc left-index) (count segments))
              :let [left (nth segments left-index) right (nth segments right-index)]
              :when (not= (:element/id left) (:element/id right))
              :let [point (segment-intersection left right)] :when point]
          {:snap/kind :intersection :snap/point point
           :element/ids [(:element/id left) (:element/id right)]})]
    (->> (concat endpoint-candidates midpoint-candidates intersections)
         (sort-by (juxt (comp str :snap/kind) :snap/point
                        #(str (or (:element/id %) (:element/ids %)))))
         (partition-by (juxt :snap/kind :snap/point))
         (mapv first))))

(defn snap-translation
  "Correct a proposed element translation by snapping any source candidate to
  the nearest model or grid target. Returns the corrected delta and evidence."
  [source-candidates target-candidates delta options]
  (let [attempts
        (keep (fn [source]
                (let [proposed (mapv + (:snap/point source) delta)]
                  (when-let [target (snap-point proposed target-candidates options)]
                    {:snap/kind (:snap/kind target)
                       :snap/source-point (:snap/point source)
                       :snap/target-point (:snap/point target)
                       :snap/distance (:snap/distance target)
                       :snap/delta (mapv - (:snap/point target) (:snap/point source))
                       :snap/target-element (:element/id target)
                       :snap/target-elements (:element/ids target)})))
              source-candidates)]
    (first (sort-by (juxt #(snap-distance-rank (:snap/distance %))
                          #(case (:snap/kind %) :endpoint 0 :intersection 1
                                 :midpoint 2 :grid 3 4)
                          :snap/distance
                          :snap/source-point)
                    attempts))))
