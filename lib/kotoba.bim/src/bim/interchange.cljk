(ns bim.interchange
  "BIM drawing export through shared kotoba-lang DXF and ISO PDF libraries."
  (:require [kotoba.lang.text :as string]
            [bim :as bim]
            [dxf.core :as dxf]
            [bim.drawing :as drawing]
            [pdf.core :as pdf]))

(defn- storey-extents [storey]
  (let [points (concat (mapcat #(get-in % [:geometry :axis])
                               (filter (comp #{:wall} :kind) (:elements storey)))
                       (mapcat #(get-in % [:geometry :boundary])
                               (filter (comp #{:slab} :kind) (:elements storey))))
        xs (map first points) ys (map second points)]
    {:min [(if (seq xs) (reduce min xs) 0.0) (if (seq ys) (reduce min ys) 0.0)]
     :max [(if (seq xs) (reduce max xs) 10.0) (if (seq ys) (reduce max ys) 10.0)]}))

(defn- annotation-dxf-entities [annotation]
  (let [layer (case (:kind annotation) :dimension "A-DIMS" :revision-cloud "A-REVS" "A-ANNO")]
    (case (:kind annotation)
      :dimension [[:line {:layer layer :from (:from annotation) :to (:to annotation)}]
                  [:text {:layer layer :at (mapv #(/ (+ %1 %2) 2.0)
                                                 (:from annotation) (:to annotation))
                          :height 0.2 :text (or (:label annotation)
                                                (str (:value annotation) " m"))}]]
      (:tag :text :level) [[:text {:layer layer :at (:point annotation) :height 0.2
                                   :text (or (:text annotation) (:label annotation))}]]
      :leader (concat
               (map (fn [[from to]] [:line {:layer layer :from from :to to}])
                    (partition 2 1 (:points annotation)))
               [[:text {:layer layer :at (last (:points annotation)) :height 0.2
                        :text (:text annotation)}]])
      :revision-cloud [[:lwpolyline {:layer layer
                                     :points (conj (vec (:points annotation))
                                                   (first (:points annotation)))}]]
      [])))

(defn floor-plan-dxf
  "Export architectural plan geometry and tags as a valid ASCII DXF document."
  ([storey] (floor-plan-dxf storey {}))
  ([storey {:keys [annotations]}]
   (let [entities
        (concat
         (for [element (:elements storey) :when (= :wall (:kind element))
               :let [[from to] (get-in element [:geometry :axis])]]
           [:line {:layer "A-WALL" :from from :to to}])
         (for [element (:elements storey) :when (= :slab (:kind element))]
           [:lwpolyline {:layer "A-SLAB"
                         :points (mapv #(subvec (vec %) 0 2)
                                       (get-in element [:geometry :boundary]))}])
         (for [element (:elements storey)
               :let [position (or (get-in element [:placement :location])
                                  (first (get-in element [:geometry :axis])) [0 0 0])]]
           [:text {:layer "A-ANNO" :at position :height 0.2
                   :text (str (:id element) " " (:name element))}])
         (mapcat annotation-dxf-entities annotations))]
     (apply dxf/drawing entities))))

(defn- annotation-pdf-commands [annotation point]
  (let [line (fn [[from to]] (pdf/line-command {:from (point from) :to (point to) :width 0.8}))
        text (fn [at value] (let [[x y] (point at)]
                              (pdf/text-command {:x (+ x 3) :y (+ y 3) :size 8 :text value})))]
    (case (:kind annotation)
      :dimension [(line [(:from annotation) (:to annotation)])
                  (text (mapv #(/ (+ %1 %2) 2.0) (:from annotation) (:to annotation))
                        (or (:label annotation) (str (:value annotation) " m")))]
      (:tag :text :level) [(text (:point annotation)
                                      (or (:text annotation) (:label annotation)))]
      :leader (concat (map line (partition 2 1 (:points annotation)))
                      [(text (last (:points annotation)) (:text annotation))])
      :revision-cloud (map line (partition 2 1 (conj (vec (:points annotation))
                                                     (first (:points annotation)))))
      [])))

(defn- floor-plan-pdf-content [storey {:keys [scale margin page-height annotations]
                                        :or {scale 40.0 margin 30.0 page-height 595.0}}]
  (let [{lower :min} (storey-extents storey) [min-x min-y] lower
        point (fn [[x y & _]] [(+ margin (* scale (- x min-x)))
                               (- page-height margin (* scale (- y min-y)))])]
    (apply str
           (concat
            [(pdf/text-command {:x margin :y (- page-height 20)
                                :size 14 :text (str (:name storey) " Plan")})]
            (for [element (:elements storey) :when (= :wall (:kind element))
                  :let [[from to] (get-in element [:geometry :axis])]]
              (pdf/line-command {:from (point from) :to (point to) :width 2.0}))
            (for [element (:elements storey)
                  :let [position (or (first (get-in element [:geometry :axis]))
                                     (get-in element [:placement :location]) [0 0 0])
                        [x y] (point position)]]
              (pdf/text-command {:x (+ x 3) :y (+ y 3) :size 8
                                 :text (str (:id element))}))
            (mapcat #(annotation-pdf-commands % point) annotations)))))

(defn- paper-bounds
  [print-setting options]
  (let [mm->points #(* % (/ 72.0 25.4))
        paper (get drawing/sheet-sizes-mm
                   (:print-setting/paper-size print-setting) [297 210])
        portrait? (= :portrait (:print-setting/orientation print-setting))
        [paper-width paper-height]
        (if portrait? [(min (first paper) (second paper))
                       (max (first paper) (second paper))]
            [(max (first paper) (second paper))
             (min (first paper) (second paper))])]
    [(or (:width options) (mm->points paper-width))
     (or (:height options) (mm->points paper-height))]))

(defn orthographic-pdf-content
  "Project model mesh bounds into vector PDF linework for section/elevation
  semantic views. View keys support :view/axis, :view/cut-position,
  :view/depth and :view/scale."
  [storeys view {:keys [page-height margin] :or {page-height 595.0 margin 180.0}}]
  (let [kind (:view/kind view)
        axis (or (:view/axis view) :x)
        horizontal-index (if (= axis :x) 0 1)
        depth-index (if (= horizontal-index 0) 1 0)
        cut (or (:view/cut-position view) 0.0)
        depth (or (:view/depth view) 1000.0)
        scale (or (:view/scale view) 15.0)
        entries
        (keep (fn [element]
                (when-let [mesh (bim/element-mesh element)]
                  (let [positions (:positions mesh)
                        horizontal (map #(nth % horizontal-index) positions)
                        vertical (map #(nth % 2) positions)
                        depths (map #(nth % depth-index) positions)
                        bounds {:horizontal [(reduce min horizontal) (reduce max horizontal)]
                                :vertical [(reduce min vertical) (reduce max vertical)]
                                :depth [(reduce min depths) (reduce max depths)]}
                        [near far] (:depth bounds)
                        visible? (if (= kind :section)
                                   (and (<= near (+ cut depth)) (>= far cut))
                                   (<= (#?(:clj Math/abs :cljs js/Math.abs) (- near cut))
                                       depth))]
                    (when visible? {:element element :bounds bounds}))))
              (mapcat :elements storeys))
        points (mapcat (fn [{:keys [bounds]}]
                         (let [[x0 x1] (:horizontal bounds) [z0 z1] (:vertical bounds)]
                           [[x0 z0] [x1 z1]])) entries)
        min-x (if (seq points) (reduce min (map first points)) 0.0)
        min-z (if (seq points) (reduce min (map second points)) 0.0)
        point (fn [[x z]] [(+ margin (* scale (- x min-x)))
                           (- page-height margin (* scale (- z min-z)))])
        rectangle
        (fn [{:keys [bounds]}]
          (let [[x0 x1] (:horizontal bounds) [z0 z1] (:vertical bounds)
                corners [[x0 z0] [x1 z0] [x1 z1] [x0 z1] [x0 z0]]]
            (apply str (map (fn [[from to]]
                              (pdf/line-command {:from (point from) :to (point to)
                                                 :width (if (= kind :section) 1.5 0.8)}))
                            (partition 2 1 corners)))))]
    (apply str (map rectangle entries))))

(defn- semantic-sheet-content
  [sheet drawing-set {:keys [storeys annotations-by-storey] :as options} width height]
  (let [views (into {} (map (juxt :view/id identity) (:drawing/views drawing-set)))
        schedules (into {} (map (juxt :schedule/id identity) (:drawing/schedules drawing-set)))
        storeys (into {} (map (juxt :id identity) storeys))
        view-ids (vec (or (:sheet/views sheet) (map :viewport/view-id (:sheet/viewports sheet))))
        title-block (:sheet/title-block sheet)
        revision (or (:revision (last (:sheet/revisions sheet))) "-")
        line-height 13
        heading (concat
                 [(pdf/text-command {:x 30 :y (- height 24) :size 15
                                     :text (str (:sheet/number sheet) "  " (:sheet/name sheet))})
                  (pdf/text-command {:x 30 :y 20 :size 8
                                     :text (str (or (:title-block/organization title-block) "")
                                                " | " (or (:title-block/project title-block) "")
                                                " | Revision " revision)})]
                 (map-indexed
                  (fn [index view-id]
                    (let [view (views view-id) schedule (schedules view-id)]
                      (pdf/text-command
                       {:x 30 :y (- height 48 (* index line-height)) :size 10
                        :text (str (inc index) ". "
                                   (or (:view/name view) (:schedule/name schedule) view-id)
                                   (when view (str " [" (name (:view/kind view)) "]")))})))
                  view-ids))
        plan-content
        (for [view-id view-ids
              :let [view (views view-id) storey (storeys (:view/storey-id view))]
              :when (and (= :floor-plan (:view/kind view)) storey)]
          (floor-plan-pdf-content
           storey (assoc options :page-height height :scale (or (:scale options) 20.0)
                         :margin 180.0
                         :annotations (get annotations-by-storey (:id storey)))))
        orthographic-content
        (for [view-id view-ids
              :let [view (views view-id)]
              :when (#{:section :elevation} (:view/kind view))]
          (orthographic-pdf-content storeys view
                                    {:page-height height :margin 180.0}))
        schedule-content
        (for [schedule-id view-ids
              :let [schedule (schedules schedule-id)]
              :when schedule]
          (apply str
                 (map-indexed
                  (fn [index row]
                    (pdf/text-command
                     {:x (- width 210) :y (- height 48 (* index 11)) :size 7
                      :text (str (inc index) "  "
                                 (string/join " | "
                                              (map #(get row (:key %))
                                                   (:schedule/fields schedule))))}))
                  (:schedule/rows schedule))))]
    (apply str (concat heading plan-content orthographic-content schedule-content))))

(defn semantic-drawing-set-pdf
  "Publish one PDF page per semantic sheet. Sheet order, paper settings, view
  references, title-block metadata, schedules, and available floor-plan geometry
  are preserved in the issued document."
  ([drawing-set storeys] (semantic-drawing-set-pdf drawing-set storeys {}))
  ([drawing-set storeys options]
   (when-not (seq (:drawing/sheets drawing-set))
     (throw (ex-info "drawing set requires at least one sheet" {})))
   (pdf/write-document
    (mapv (fn [sheet]
            (let [print-setting (merge {:print-setting/paper-size (or (:sheet/size sheet) :a4)
                                        :print-setting/orientation :landscape}
                                       (:print-setting options)
                                       (:sheet/print-setting sheet))
                  [width height] (paper-bounds print-setting options)]
              {:width width :height height
               :content (semantic-sheet-content sheet drawing-set
                                                (assoc options :storeys storeys)
                                                width height)}))
          (:drawing/sheets drawing-set)))))

(defn drawing-set-pdf
  "Export one vector PDF page per storey, suitable for archival or issue."
  ([storeys] (drawing-set-pdf storeys {}))
  ([storeys {:keys [annotations-by-storey print-setting drawing-set] :as options}]
   (if drawing-set
     (semantic-drawing-set-pdf drawing-set storeys options)
     (let [[width height] (paper-bounds print-setting options)
         mm->points #(* % (/ 72.0 25.4))
         denominator (:print-setting/scale print-setting)
         scale (if (number? denominator) (/ (mm->points 1000.0) denominator)
                   (or (:scale options) 40.0))
         margin-mm (first (:print-setting/margins-mm print-setting))
         margin (if (number? margin-mm) (mm->points margin-mm)
                    (or (:margin options) 30.0))]
     (pdf/write-document
      (mapv (fn [storey]
              {:width width :height height
               :content (floor-plan-pdf-content
                         storey (assoc options :page-height height :scale scale :margin margin
                                       :annotations
                                       (get annotations-by-storey (:id storey))))})
            storeys))))))
