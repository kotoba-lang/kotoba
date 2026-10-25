(ns bim.drawing
  "BIM-to-SVG projection. XML/SVG rendering is owned by kotoba-lang/svg."
  (:require [bim :as bim]
            [kotoba.lang.text :as string]
            [svg.core :as svg]
            [svg.shapes :as shapes]))

(defn- bounds-2d [points]
  (let [points (seq points) xs (map first points) ys (map second points)]
    (if points
      {:min [(reduce min xs) (reduce min ys)] :max [(reduce max xs) (reduce max ys)]}
      {:min [0.0 0.0] :max [10.0 10.0]})))

(defn- cross-2d
  "Signed area (x2) of the triangle o,a,b: positive when o->a->b turns left
  (counter-clockwise), negative when it turns right, zero when collinear."
  [[ox oy] [ax ay] [bx by]]
  (- (* (- ax ox) (- by oy)) (* (- ay oy) (- bx ox))))

(defn convex-hull-2d
  "2D convex hull via Andrew's monotone chain, returned as a
  counter-clockwise polygon with no repeated closing point. Degenerate
  input (fewer than 3 distinct points, or all collinear) returns the
  distinct input points sorted lexicographically."
  [points]
  (let [sorted (vec (sort-by (fn [[x y]] [x y]) (distinct points)))]
    (if (< (count sorted) 3)
      sorted
      (let [build (fn [pts]
                    (reduce (fn [hull point]
                              (loop [hull hull]
                                (if (and (>= (count hull) 2)
                                         (<= (cross-2d (nth hull (- (count hull) 2))
                                                       (peek hull) point) 0.0))
                                  (recur (pop hull))
                                  (conj hull point))))
                            [] pts))
            lower (build sorted)
            upper (build (rseq sorted))]
        (vec (concat (pop lower) (pop upper)))))))

(defn polygon-area-2d
  "Shoelace-formula area of a (not necessarily convex) simple polygon."
  [polygon]
  (if (< (count polygon) 3)
    0.0
    (/ (#?(:clj Math/abs :cljs js/Math.abs)
        (reduce + (map (fn [[[x1 y1] [x2 y2]]] (- (* x1 y2) (* x2 y1)))
                       (map vector polygon (concat (rest polygon) [(first polygon)])))))
       2.0)))

(defn- line-intersection-2d
  "Intersection of segment p1-p2 with the infinite line through a,b."
  [p1 p2 a b]
  (let [[x1 y1] p1 [x2 y2] p2
        d1 (cross-2d a b p1) d2 (cross-2d a b p2)
        t (/ d1 (- d1 d2))]
    [(+ x1 (* t (- x2 x1))) (+ y1 (* t (- y2 y1)))]))

(defn- clip-against-edge [polygon a b]
  (if (empty? polygon)
    []
    (let [inside? (fn [p] (>= (cross-2d a b p) 0.0))]
      (loop [result [] prev (peek polygon) prev-in (inside? (peek polygon)) remaining polygon]
        (if (empty? remaining)
          result
          (let [current (first remaining)
                current-in (inside? current)
                result (cond-> result
                         (not= prev-in current-in)
                         (conj (line-intersection-2d prev current a b))
                         current-in (conj current))]
            (recur result current current-in (rest remaining))))))))

(defn sutherland-hodgman-clip
  "Clip `subject` (any simple polygon) to the region inside `clip-polygon`
  (must be convex and counter-clockwise), returning the (possibly empty)
  intersection polygon."
  [subject clip-polygon]
  (reduce (fn [polygon edge] (clip-against-edge polygon (first edge) (second edge)))
          subject
          (map vector clip-polygon (concat (rest clip-polygon) [(first clip-polygon)]))))

(defn- dimension-group [[x1 y1] [x2 y2] offset label]
  (let [dx (- x2 x1) dy (- y2 y1)
        length (#?(:clj Math/sqrt :cljs js/Math.sqrt) (+ (* dx dx) (* dy dy)))
        nx (if (pos? length) (/ (- dy) length) 0.0)
        ny (if (pos? length) (/ dx length) 0.0)
        ax (+ x1 (* offset nx)) ay (+ y1 (* offset ny))
        bx (+ x2 (* offset nx)) by (+ y2 (* offset ny))
        mx (/ (+ ax bx) 2.0) my (/ (+ ay by) 2.0)]
    [:g {:class "dimension"}
     (shapes/line x1 y1 ax ay {:stroke "#475569" :stroke-width 1})
     (shapes/line x2 y2 bx by {:stroke "#475569" :stroke-width 1})
     (shapes/line ax ay bx by {:stroke "#0f172a" :stroke-width 1
                               :marker-start "url(#arrow)" :marker-end "url(#arrow)"})
     (shapes/text mx (- my 4) label {:text-anchor "middle" :font-family "sans-serif"
                                     :font-size 11 :fill "#0f172a"})]))

(defn- format-2 [value]
  #?(:clj (format "%.2f" (double value)) :cljs (.toFixed value 2)))

(defn- category-visible? [options element]
  (not= false (get (:category-visibility options) (:kind element) true)))

(defn- category-override [options element defaults]
  (merge defaults (get (:category-overrides options) (:kind element))))

(defn- element-z-range [element]
  (let [points (concat (get-in element [:geometry :axis])
                       (get-in element [:geometry :boundary]))
        zs (keep #(when (and (sequential? %) (number? (nth % 2 nil))) (nth % 2)) points)
        base (if (seq zs) (reduce min zs)
                 (or (get-in element [:placement :location 2]) 0.0))
        top (case (:kind element)
              :wall (+ base (or (get-in element [:geometry :profile :height]) 0.0))
              :slab (+ base (or (get-in element [:geometry :thickness])
                                (:thickness element) 0.0))
              (if (seq zs) (reduce max zs) base))]
    [base top]))

(defn- plan-visible? [options element]
  (if-let [{:keys [top view-depth]} (:view-range options)]
    (let [[element-bottom element-top] (element-z-range element)]
      (and (<= element-bottom top) (>= element-top view-depth)))
    true))

(defn- plan-cut? [options element]
  (when-let [cut-plane (get-in options [:view-range :cut-plane])]
    (let [[bottom top] (element-z-range element)] (<= bottom cut-plane top))))

(defn- annotation-groups [annotations sx sy style]
  (mapv
   (fn [annotation]
     (case (:kind annotation)
       :dimension
       (dimension-group (mapv (fn [value transform] (transform value))
                              (:from annotation) [sx sy])
                        (mapv (fn [value transform] (transform value))
                              (:to annotation) [sx sy])
                        (or (:offset annotation) 18)
                        (or (:label annotation)
                            (str (format-2 (:value annotation)) " m")))
       :level
       (let [y (sy (second (:point annotation)))
             x (sx (first (:point annotation)))
             width (or (:width annotation) 120)]
         [:g {:class "level-annotation"}
          (shapes/line x y (+ x width) y (merge {:stroke "#334155"} style))
          (shapes/text (+ x width 4) (- y 3) (:label annotation)
                       (merge {:font-family "sans-serif" :font-size 10} style))])
       (:tag :text)
       (let [[x y] (:point annotation)]
         (shapes/text (sx x) (sy y) (:text annotation)
                      (merge {:class (if (= :tag (:kind annotation))
                                       "element-tag" "text-annotation")
                              :font-family "sans-serif" :font-size 10}
                             style (:style annotation))))
       :callout
       (let [[[min-x min-y] [max-x max-y]] (:bounds annotation)
             x (sx min-x) y (sy max-y)
             width (- (sx max-x) x) height (- (sy min-y) y)
             label (or (:label annotation) (:target-view-id annotation) "Detail")]
         [:g {:class "detail-callout" :data-target-view (:target-view-id annotation)}
          (shapes/rect x y width height
                       (merge {:fill "none" :stroke "#7c3aed" :stroke-width 1.5
                               :stroke-dasharray "6 3"} style (:style annotation)))
          (shapes/line (+ x width) y (+ x width 18) (- y 18)
                       (merge {:stroke "#7c3aed" :stroke-width 1.5} style))
          [:circle {:cx (+ x width 25) :cy (- y 25) :r 12
                    :fill "white" :stroke "#7c3aed" :stroke-width 1.5}]
          (shapes/text (+ x width 25) (- y 21) label
                       {:text-anchor "middle" :font-family "sans-serif"
                        :font-size 9 :fill "#4c1d95"})])
       :leader
       (let [points (mapv (fn [[x y]] [(sx x) (sy y)]) (:points annotation))
             [text-x text-y] (last points)]
         [:g {:class "leader-annotation" :data-annotation-id (:annotation/id annotation)}
          [:polyline (merge {:points (string/join " " (map #(string/join "," %) points))
                             :fill "none" :stroke "#0f172a" :stroke-width 1
                             :marker-start "url(#arrow)"}
                            style (:style annotation))]
          (shapes/text (+ text-x 4) (- text-y 4) (:text annotation)
                       (merge {:font-family "sans-serif" :font-size 10}
                              style (:style annotation)))])
       :revision-cloud
       (let [points (mapv (fn [[x y]] [(sx x) (sy y)]) (:points annotation))]
         [:g {:class "revision-cloud" :data-annotation-id (:annotation/id annotation)
              :data-revision (:revision annotation)}
          [:polygon (merge {:points (string/join " " (map #(string/join "," %) points))
                            :fill "none" :stroke "#dc2626" :stroke-width 2
                            :stroke-linejoin "round" :stroke-dasharray "2 3"}
                           style (:style annotation))]])
       [:g {:class "unsupported-annotation" :data-kind (name (:kind annotation))}]))
   annotations))

(defn floor-plan
  ([storey] (floor-plan storey {}))
  ([storey {:keys [scale margin] :or {scale 60 margin 40} :as options}]
   (let [walls (filter #(and (= :wall (:kind %)) (category-visible? options %)
                             (plan-visible? options %))
                       (:elements storey))
         slabs (filter #(and (= :slab (:kind %)) (category-visible? options %)
                             (plan-visible? options %))
                       (:elements storey))
         points (concat (mapcat #(get-in % [:geometry :axis]) walls)
                        (mapcat #(get-in % [:geometry :boundary]) slabs))
         xs (map first points) ys (map second points)
         min-x (if (seq xs) (reduce min xs) 0) max-x (if (seq xs) (reduce max xs) 10)
         min-y (if (seq ys) (reduce min ys) 0) max-y (if (seq ys) (reduce max ys) 10)
         width (+ (* scale (- max-x min-x)) (* 2 margin))
         height (+ (* scale (- max-y min-y)) (* 2 margin))
         sx #(+ margin (* scale (- % min-x)))
         sy #(- height margin (* scale (- % min-y)))]
     (apply svg/svg {:viewBox (str "0 0 " width " " height)}
            (concat
             [(shapes/rect 0 0 "100%" "100%" {:fill "white"})
              (shapes/text margin 24 (str (:name storey) " · Floor Plan · 1:100")
                           {:font-family "sans-serif" :font-size 16})]
             (for [slab slabs]
               [:polygon (merge {:points (string/join " " (map (fn [[x y _]] (str (sx x) "," (sy y)))
                                                                 (get-in slab [:geometry :boundary])))}
                                (category-override options slab
                                                   {:fill "#eef2f7" :stroke "#64748b"}))])
             (for [wall walls
                   :let [[[x1 y1 _] [x2 y2 _]] (get-in wall [:geometry :axis])]]
               (shapes/line (sx x1) (sy y1) (sx x2) (sy y2)
                            (category-override
                             options wall
                             {:class (if (plan-cut? options wall) "cut-element" "projected-element")
                              :stroke "#111827"
                              :stroke-width (max 2 (* scale (get-in wall [:geometry :profile :thickness])))}))))))))

(defn floor-plan-svg
  ([storey] (floor-plan-svg storey {}))
  ([storey options] (svg/render (floor-plan storey options))))

(defn documented-floor-plan
  "Annotated plan view with wall openings, element tags, overall dimensions,
  and vector metadata suitable for placement on a drawing sheet."
  ([storey] (documented-floor-plan storey {}))
  ([storey {:keys [scale margin show-tags? annotations annotation-style]
             :or {scale 60 margin 60 show-tags? true} :as options}]
   (let [walls (filter #(and (= :wall (:kind %)) (category-visible? options %)
                             (plan-visible? options %))
                       (:elements storey))
         points (mapcat #(get-in % [:geometry :axis]) walls)
         {:keys [min max]} (bounds-2d points) [min-x min-y] min [max-x max-y] max
         height (+ (* scale (- max-y min-y)) (* 2 margin))
         sx #(+ margin (* scale (- % min-x))) sy #(- height margin (* scale (- % min-y)))
         base (floor-plan storey (assoc options :scale scale :margin margin))
         defs [:defs [:marker {:id "arrow" :markerWidth 8 :markerHeight 8 :refX 4 :refY 4
                               :orient "auto-start-reverse"}
                       [:path {:d "M 0 0 L 8 4 L 0 8 z" :fill "#0f172a"}]]]
         openings
         (for [wall walls opening (:openings wall)
               :let [[[x1 y1 _] [x2 y2 _]] (get-in wall [:geometry :axis])
                     length (get-in wall [:quantities :length-m])
                     start (/ (get-in opening [:placement :offset]) length)
                     finish (/ (+ (get-in opening [:placement :offset])
                                  (get-in opening [:profile :width])) length)
                     ox1 (+ x1 (* start (- x2 x1))) oy1 (+ y1 (* start (- y2 y1)))
                     ox2 (+ x1 (* finish (- x2 x1))) oy2 (+ y1 (* finish (- y2 y1)))]]
           [:g {:class "opening" :data-opening-id (:id opening)}
            (shapes/line (sx ox1) (sy oy1) (sx ox2) (sy oy2)
                         {:stroke "white" :stroke-width
                          (+ 2 (* scale (get-in wall [:geometry :profile :thickness])))})
            (shapes/line (sx ox1) (sy oy1) (sx ox2) (sy oy2)
                         {:stroke "#64748b" :stroke-width 1})])
         tags (when show-tags? (for [wall walls
                    :let [[[x1 y1 _] [x2 y2 _]] (get-in wall [:geometry :axis])]]
                (shapes/text (sx (/ (+ x1 x2) 2.0)) (- (sy (/ (+ y1 y2) 2.0)) 8)
                             (str "W" (:id wall))
                             {:class "element-tag" :text-anchor "middle"
                              :font-family "sans-serif" :font-size 10 :fill "#334155"})))]
     (into base
           (concat [defs]
                   openings tags
                   (for [wall walls
                         :let [[[x1 y1 _] [x2 y2 _]] (get-in wall [:geometry :axis])]]
                     (dimension-group [(sx x1) (sy y1)] [(sx x2) (sy y2)] 18
                                      (str (format-2 (get-in wall [:quantities :length-m])) " m")))
                   [(dimension-group [(sx min-x) (sy min-y)] [(sx max-x) (sy min-y)] 28
                                     (str (format-2 (- max-x min-x)) " m"))
                    (dimension-group [(sx min-x) (sy min-y)] [(sx min-x) (sy max-y)] -28
                                     (str (format-2 (- max-y min-y)) " m"))]
                   (annotation-groups annotations sx sy annotation-style))))))

(defn documented-floor-plan-svg
  ([storey] (documented-floor-plan-svg storey {}))
  ([storey options] (svg/render (documented-floor-plan storey options))))

(defn- all-building-elements [building]
  (mapcat (fn [storey]
            (map #(assoc % :drawing/storey storey) (:elements storey)))
          (:storeys building)))

(defn- mesh-projection-bounds [element horizontal-index]
  (when-let [mesh (bim/element-mesh element)]
    (let [positions (:positions mesh)
          horizontal (map #(nth % horizontal-index) positions)
          vertical (map #(nth % 2) positions)
          depth-index (if (= horizontal-index 0) 1 0)
          depths (map #(nth % depth-index) positions)]
      {:horizontal [(reduce min horizontal) (reduce max horizontal)]
       :vertical [(reduce min vertical) (reduce max vertical)]
       :depth [(reduce min depths) (reduce max depths)]})))

(defn- mesh-projection-hull
  "Convex hull of an element's mesh vertices projected onto the view plane
  (horizontal-index, z). A convex hull is a conservative approximation of
  the element's true silhouette -- concave footprints (an L-shaped wall, a
  wall with an opening) are over-approximated, never under-approximated,
  so hidden-line culling against it can only hide too little, not too
  much."
  [element horizontal-index]
  (when-let [mesh (bim/element-mesh element)]
    (convex-hull-2d (map (fn [p] [(nth p horizontal-index) (nth p 2)]) (:positions mesh)))))

(defn- mostly-occluded?
  "True when `hull` is covered by at least `threshold` (area fraction) of
  its area by a single nearer hull already in `nearer-hulls`. This is a
  single-occluder test -- it does not detect a farther element that is
  fully covered only by the *union* of several nearer elements, none of
  which individually covers enough of it."
  [hull nearer-hulls threshold]
  (let [area (polygon-area-2d hull)]
    (and (pos? area)
         (some (fn [nearer]
                 (>= (/ (polygon-area-2d (sutherland-hodgman-clip hull nearer)) area) threshold))
               nearer-hulls))))

(defn- edge-plane-intersection [a b depth-index cut-position]
  (let [da (- (nth a depth-index) cut-position)
        db (- (nth b depth-index) cut-position)
        tolerance 1.0e-9]
    (cond
      (and (< (#?(:clj Math/abs :cljs js/Math.abs) da) tolerance)
           (< (#?(:clj Math/abs :cljs js/Math.abs) db) tolerance)) [a b]
      (< (#?(:clj Math/abs :cljs js/Math.abs) da) tolerance) [a]
      (< (#?(:clj Math/abs :cljs js/Math.abs) db) tolerance) [b]
      (or (and (neg? da) (pos? db)) (and (pos? da) (neg? db)))
      (let [factor (/ da (- da db))]
        [(mapv + a (mapv #(* factor %) (mapv - b a)))])
      :else [])))

(defn- mesh-section-segments
  "Intersect indexed mesh triangles with an orthographic section plane and
  return exact 2D cut segments in model coordinates."
  [mesh horizontal-index cut-position]
  (let [positions (:positions mesh)
        depth-index (if (= horizontal-index 0) 1 0)
        tolerance 1.0e-9
        project #(vector (nth % horizontal-index) (nth % 2))]
    (->> (partition 3 (:indices mesh))
         (mapcat (fn [[ia ib ic]]
                   (let [a (nth positions ia) b (nth positions ib) c (nth positions ic)
                         triangle [a b c]
                         coplanar? (every?
                                    #(< (#?(:clj Math/abs :cljs js/Math.abs)
                                         (- (nth % depth-index) cut-position)) tolerance)
                                    triangle)]
                     (if coplanar?
                       (mapv (fn [[left right]] [(project left) (project right)])
                             [[a b] [b c] [c a]])
                       (let [points (->> [[a b] [b c] [c a]]
                                         (mapcat (fn [[left right]]
                                                   (edge-plane-intersection
                                                    left right depth-index cut-position)))
                                         distinct vec)]
                         (when (<= 2 (count points))
                           [[(project (first points)) (project (second points))]]))))))
         distinct vec)))

(def ^:private occlusion-threshold
  "Fraction of a farther element's projected-hull area that must be covered
  by a single nearer element's hull before the farther element is culled
  as fully hidden -- see `mostly-occluded?`."
  0.98)

(defn orthographic-view
  "Generate a section or elevation from mesh bounds. Sections distinguish cut
  objects from projected objects; elevations emit front-view silhouettes.
  With hidden-line? true (the default), a projected or elevation element
  whose projected convex hull is almost entirely covered by a single
  nearer element's hull is dropped -- real polygon overlap in any
  orientation, not just axis-aligned bounding-box containment, so e.g. two
  overlapping rotated/diamond footprints are handled correctly where a
  bounding-box test would miss the occlusion. This is still a whole-
  element, single-occluder decision (an element is either fully kept or
  fully dropped; occlusion by the combined union of several nearer
  elements, none of which alone covers enough of it, is not detected),
  and hull silhouettes are conservative convex approximations, so concave
  footprints (an L-shaped wall, a wall with an opening) can be culled less
  than their true shape would justify but never more."
  [building {:keys [kind axis cut-position depth scale margin title hidden-line?
                    show-tags? annotations annotation-style crop view-id parent-view-id]
             :or {kind :section axis :x cut-position 0.0 depth 1000.0 scale 50
                  margin 50 hidden-line? true show-tags? true}
             :as options}]
  (let [horizontal-index (if (= axis :x) 0 1)
        entries (keep (fn [element]
                        (when (category-visible? options element)
                          (when-let [mesh (bim/element-mesh element)]
                            (when-let [bounds (mesh-projection-bounds element horizontal-index)]
                              {:element element :mesh mesh :bounds bounds
                               :hull (mesh-projection-hull element horizontal-index)}))))
                      (all-building-elements building))
        visible (filter (fn [{:keys [bounds]}]
                          (let [[near far] (:depth bounds)]
                            (if (= kind :section)
                              (and (<= near (+ cut-position depth)) (>= far cut-position))
                              (<= (#?(:clj Math/abs :cljs js/Math.abs) (- near cut-position)) depth))))
                        entries)
        visible (if crop
                  (let [[[crop-min-x crop-min-z] [crop-max-x crop-max-z]] crop]
                    (filter (fn [{:keys [bounds]}]
                              (let [[x0 x1] (:horizontal bounds)
                                    [z0 z1] (:vertical bounds)]
                                (and (<= x0 crop-max-x) (>= x1 crop-min-x)
                                     (<= z0 crop-max-z) (>= z1 crop-min-z))))
                            visible))
                  visible)
        visible (sort-by #(first (get-in % [:bounds :depth])) visible)
        cut-entry? (fn [{:keys [bounds]}]
                     (let [[near far] (:depth bounds)]
                       (and (= kind :section) (<= near cut-position) (<= cut-position far))))
        visible (if hidden-line?
                  (:kept (reduce (fn [{:keys [kept nearer-hulls]} entry]
                                   (if (and (:hull entry) (not (cut-entry? entry))
                                            (mostly-occluded? (:hull entry) nearer-hulls
                                                              occlusion-threshold))
                                     {:kept kept :nearer-hulls nearer-hulls}
                                     {:kept (conj kept entry)
                                      :nearer-hulls (cond-> nearer-hulls
                                                      (:hull entry) (conj (:hull entry)))}))
                                 {:kept [] :nearer-hulls []} visible))
                  visible)
        points (mapcat (fn [{:keys [bounds]}]
                         (let [[x0 x1] (:horizontal bounds) [z0 z1] (:vertical bounds)]
                           [[x0 z0] [x1 z1]])) visible)
        {:keys [min] maximum :max} (if crop {:min (first crop) :max (second crop)}
                                           (bounds-2d points))
        [min-x min-z] min [max-x max-z] maximum
        width (+ (* scale (- max-x min-x)) (* 2 margin))
        height (+ (* scale (- max-z min-z)) (* 2 margin))
        sx #(+ margin (* scale (- % min-x))) sz #(- height margin (* scale (- % min-z)))]
    (apply svg/svg (cond-> {:viewBox (str "0 0 " width " " height)
                            :data-view-kind (name kind)}
                     view-id (assoc :data-view-id view-id)
                     parent-view-id (assoc :data-parent-view-id parent-view-id))
           (concat
            [(shapes/rect 0 0 "100%" "100%" {:fill "white"})
             (shapes/text margin 24 (or title (str (string/capitalize (name kind)) " " (name axis)))
                          {:font-family "sans-serif" :font-size 16})]
            (for [{:keys [element mesh bounds]} visible
                  :let [[x0 x1] (:horizontal bounds) [z0 z1] (:vertical bounds)
                        [near far] (:depth bounds)
                        cut? (and (= kind :section) (<= near cut-position) (<= cut-position far))
                        cut-segments (when cut?
                                       (mesh-section-segments mesh horizontal-index cut-position))]]
              [:g {:class (if cut? "cut-element" "projected-element")
                   :data-element-id (:id element)}
               (shapes/rect (sx x0) (sz z1) (max 1 (- (sx x1) (sx x0)))
                            (max 1 (- (sz z0) (sz z1)))
                            (category-override
                             options element
                             {:fill (if cut? "#dbeafe" "none")
                              :stroke (if cut? "#0f172a" "#64748b")
                              :stroke-width (if cut? 2 1)
                              :stroke-dasharray (when (and (not cut?) (not hidden-line?))
                                                  "4 3")}))
               (when (seq cut-segments)
                 (into [:g {:class "section-cut-edges"}]
                       (map (fn [[[ax az] [bx bz]]]
                              (shapes/line (sx ax) (sz az) (sx bx) (sz bz)
                                           {:class "section-cut-edge" :stroke "#020617"
                                            :stroke-width 2.5}))
                            cut-segments)))
               (when show-tags?
                 (shapes/text (/ (+ (sx x0) (sx x1)) 2.0) (- (sz z1) 4)
                              (str (string/upper (subs (name (:kind element)) 0 1))
                                   (:id element))
                              {:class "element-tag" :text-anchor "middle" :font-size 9}))])
            (annotation-groups annotations sx sz annotation-style)))))

(defn orthographic-view-svg [building options]
  (svg/render (orthographic-view building options)))

(defn detail-view
  "Generate an enlarged, model-linked detail from a cropped section/elevation.
  The root records both its own id and its parent view for callout navigation."
  [building {:keys [id parent-view-id crop] :as options}]
  (when-not (and id parent-view-id (= 2 (count crop))
                 (every? #(and (= 2 (count %)) (every? number? %)) crop))
    (throw (ex-info "detail view requires id, parent view, and 2D crop bounds"
                    {:id id :parent-view-id parent-view-id :crop crop})))
  (let [view (orthographic-view
              building (-> options
                           (assoc :kind (or (:source-kind options) :section)
                                  :view-id id :parent-view-id parent-view-id)
                           (dissoc :id :source-kind)))]
    (update view 1 assoc :data-view-kind "detail")))

(defn detail-view-svg [building options]
  (svg/render (detail-view building options)))

(def sheet-sizes-mm {:a0 [1189 841] :a1 [841 594] :a2 [594 420] :a3 [420 297]
                     :a4 [297 210] :letter [279.4 215.9] :legal [355.6 215.9]
                     :tabloid [431.8 279.4]})

(defn drawing-sheet
  "Compose renderable SVG views into a sheet with viewport frames and title block."
  [{:keys [number name size revision viewports print-setting title-block]
    :or {number "A-001" name "Drawing Sheet" size :a1 revision "P01"}}]
  (let [paper-size (or (:print-setting/paper-size print-setting) size)
        [paper-width paper-height] (get sheet-sizes-mm paper-size (get sheet-sizes-mm :a1))
        portrait? (= :portrait (:print-setting/orientation print-setting))
        [width height] (if portrait?
                         [(min paper-width paper-height) (max paper-width paper-height)]
                         [(max paper-width paper-height) (min paper-width paper-height)])
        title-width (or (:title-block/width title-block) 250)
        title-height (or (:title-block/height title-block) 55)
        title-x (- width title-width) title-y (- height title-height)
        fields (concat
                [["Project" (or (:title-block/project title-block) name)]
                 ["Client" (:title-block/client title-block)]
                 ["Drawn" (:title-block/drawn-by title-block)]
                 ["Checked" (:title-block/checked-by title-block)]]
                (sort-by key (:title-block/custom-fields title-block)))]
    (apply svg/svg (cond-> {:viewBox (str "0 0 " width " " height)
                            :data-sheet-number number}
                     print-setting
                     (assoc :data-print-setting (:print-setting/id print-setting)
                            :data-paper-size (clojure.core/name paper-size)
                            :data-orientation (clojure.core/name
                                               (:print-setting/orientation print-setting))))
           (concat
            [(shapes/rect 0 0 width height {:fill "white" :stroke "#111827"})]
            (for [{:keys [view x y width height title scale]
                   :or {x 20 y 20 width 360 height 240 scale 100}} viewports]
              (let [[tag attrs & children] view]
                [:g {:class "viewport" :data-view-title title}
                 (into [tag (assoc attrs :x x :y y :width width :height height)] children)
                 (shapes/rect x y width height {:fill "none" :stroke "#94a3b8"})
                 (shapes/text x (+ y height 14) (str title " · 1:" scale)
                              {:font-family "sans-serif" :font-size 10})]))
            [(into
              [:g {:class "title-block"}
               (shapes/rect title-x title-y title-width title-height
                            {:fill "white" :stroke "#111827"})
               (shapes/text (+ title-x 10) (+ title-y 18)
                            (or (:title-block/organization title-block) name)
                            {:font-family "sans-serif" :font-size 14})
               (shapes/text (+ title-x 10) (+ title-y 38)
                            (str number " · " revision " · "
                                 (string/upper (clojure.core/name size)))
                            {:font-family "sans-serif" :font-size 10})]
              (map-indexed
               (fn [index [label value]]
                 (shapes/text (+ title-x 125) (+ title-y 12 (* index 10))
                              (str label ": " value)
                              {:font-family "sans-serif" :font-size 8}))
               (remove (comp nil? second) fields)))]))))

(defn drawing-sheet-svg [sheet] (svg/render (drawing-sheet sheet)))

(defn schedule-table
  "Render an element schedule contract as an SVG table for sheet placement."
  ([schedule] (schedule-table schedule {}))
  ([schedule {:keys [column-width row-height]
              :or {column-width 130 row-height 24}}]
   (let [fields (:schedule/fields schedule)
         rows (:schedule/rows schedule)
         width (* column-width (count fields))
         height (* row-height (+ 2 (count rows)))
         cell (fn [row-index column-index value header?]
                (let [x (* column-index column-width) y (* row-index row-height)]
                  [:g {:class (if header? "schedule-header" "schedule-cell")}
                   (shapes/rect x y column-width row-height
                                {:fill (if header? "#e2e8f0" "white")
                                 :stroke "#64748b" :stroke-width 0.7})
                   (shapes/text (+ x 6) (+ y 16) (str (or value ""))
                                {:font-family "sans-serif" :font-size 10})]))]
     (apply svg/svg {:viewBox (str "0 0 " width " " height)
                     :data-schedule-id (:schedule/id schedule)}
            (concat
             [(shapes/text 0 16 (:schedule/name schedule)
                           {:class "schedule-title" :font-family "sans-serif"
                            :font-size 14})]
             (map-indexed (fn [column-index field]
                            (cell 1 column-index (:heading field) true))
                          fields)
             (mapcat (fn [row-index row]
                       (map-indexed (fn [column-index field]
                                      (cell (+ row-index 2) column-index
                                            (get row (:key field)) false))
                                    fields))
                     (range) rows))))))

(defn schedule-table-svg
  ([schedule] (schedule-table-svg schedule {}))
  ([schedule options] (svg/render (schedule-table schedule options))))
