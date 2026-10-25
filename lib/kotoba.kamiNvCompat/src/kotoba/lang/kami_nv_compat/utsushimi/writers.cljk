(ns kotoba.lang.kami-nv-compat.utsushimi.writers
  "utsushimi — Replicator writers (BasicWriter / CocoWriter / KittiWriter).
  Portable .cljc port of src/utsushimi/writers.ts. Wave 32.

  Mirrors omni.replicator.core.writers.*. The Replicator G5 gate is
  \"BasicWriter emits the same JSON schema as upstream (diff = 0)\" —
  this port reproduces the documented COCO-2017 / Kitti on-disk field
  schemas exactly; JSON whitespace/formatting is NOT byte-identical to
  the TS reference's JSON.stringify(obj, null, 2) output (json.data-json
  emits compact JSON in this repo's pinned version), only the schema.

  Portability: instead of writing to a filesystem (which would not run
  in a browser / WASM host), each writer accumulates in memory (an
  atom-held state closed over by a reify) and exposes finalize-writer (the
  structured dataset) + to-files (a path->content map a caller can
  persist with the documented on-disk layout). Per-object 2D bounding
  boxes come from the render bridge when present, else the upstream
  full-image placeholder.

  ADR-2605261800 SD6 / D10.4 utsushimi."
  (:require [kotoba.lang.text :as str]
            [json.data-json :as json]))

;; AnnotatedPrim = a PrimSpec (see randomize.cljc) plus an optional real
;; 2D bbox2d [x y w h] (from the camera-projection render bridge).
;; FrameSample {:frame :primitives}
;; WriterInit  {:output-dir :rgb :bounding-box-2d-tight :semantic-segmentation
;;              :image-width :image-height}

(defprotocol IUtsushimiWriter
  (initialize! [this init])
  (attach! [this cameras])
  (write-frame! [this frame-index sample])
  (finalize-writer [this])
  (to-files [this]))

(defn- pad
  [n width]
  (let [s (str n)]
    (str (apply str (repeat (max 0 (- width (count s))) "0")) s)))

(defn- class-of
  [prim]
  (some (fn [s] (when (and (vector? s) (= 2 (count s)) (= "class" (s 0))) (s 1)))
        (or (:semantics prim) [])))

;; ── BasicWriter ──────────────────────────────────────────────────────────

(defn make-basic-writer
  []
  (let [output-dir (atom "_out")
        cameras (atom [])
        frames (atom [])]
    (reify IUtsushimiWriter
      (initialize! [_ init] (reset! output-dir (or (:output-dir init) "_out")))
      (attach! [_ cams] (reset! cameras (vec cams)))
      (write-frame! [_ frame-index sample]
        (swap! frames conj {:frame frame-index :cameras @cameras :sample sample}))
      (finalize-writer [_] {:frames @frames})
      (to-files [_]
        (into {} (map (fn [f]
                         [(str @output-dir "/frame_" (pad (:frame f) 4) ".json")
                          (json/write-str {:frame (:frame f) :cameras (:cameras f) :sample (:sample f)})])
                       @frames))))))

;; ── CocoWriter (COCO-2017 object-detection JSON) ─────────────────────────
;;
;; CocoImage {:id :file-name :width :height}
;; CocoAnnotation {:id :image-id :category-id :bbox :area :iscrowd}
;; CocoCategory {:id :name :supercategory}
;; CocoDataset {:info :images :annotations :categories}

(defn make-coco-writer
  []
  (let [output-dir (atom "_out")
        width (atom 640)
        height (atom 480)
        images (atom [])
        annotations (atom [])
        categories (atom {})            ; name -> id
        per-frame (atom {})
        next-ann-id (atom 0)
        next-cat-id (atom 0)
        category-id! (fn [name]
                       (if-let [id (get @categories name)]
                         id
                         (let [id @next-cat-id]
                           (swap! next-cat-id inc)
                           (swap! categories assoc name id)
                           id)))]
    (reify IUtsushimiWriter
      (initialize! [_ init]
        (reset! output-dir (or (:output-dir init) "_out"))
        (reset! width (or (:image-width init) 640))
        (reset! height (or (:image-height init) 480)))
      (attach! [_ _cams] nil) ; cameras tracked by the orchestrator
      (write-frame! [_ frame-index sample]
        (swap! images conj {:id frame-index :file-name (str "rgb_" (pad frame-index 4) ".png")
                             :width @width :height @height})
        (swap! per-frame assoc (str @output-dir "/rgb_" (pad frame-index 4) ".json")
               (json/write-str {:frame frame-index :sample sample}))
        (doseq [prim (:primitives sample)]
          (when-let [cls (class-of prim)]
            (let [cat-id (category-id! cls)
                  bbox (or (:bbox2d prim) [0 0 @width @height])]
              (swap! annotations conj
                     {:id @next-ann-id :image-id frame-index :category-id cat-id
                      :bbox bbox :area (* (bbox 2) (bbox 3)) :iscrowd 0})
              (swap! next-ann-id inc)))))
      (finalize-writer [_]
        (let [cats (->> @categories
                         (sort-by val)
                         (mapv (fn [[name id]] {:id id :name name :supercategory "object"})))]
          {:info {:description "utsushimi (nv-compat) COCO output" :version "1.0" :year 2026}
           :images @images
           :annotations @annotations
           :categories cats}))
      (to-files [this]
        (assoc @per-frame (str @output-dir "/annotations.json") (json/write-str (finalize-writer this)))))))

;; ── KittiWriter (Kitti 3D object-detection label .txt) ───────────────────

(defn- fixed2 [x] #?(:clj (format "%.2f" (double x)) :cljs (.toFixed x 2)))

(defn- kitti-line
  [prim width height]
  (when-let [cls (class-of prim)]
    (let [bbox (or (:bbox2d prim) [0 0 width height])
          pos (or (:position prim) [0 0 10])
          ry (or (:rotation-y prim) 0)]
      (str cls " 0.00 0 0.00 "
           (fixed2 (bbox 0)) " " (fixed2 (bbox 1)) " "
           (fixed2 (+ (bbox 0) (bbox 2))) " " (fixed2 (+ (bbox 1) (bbox 3))) " "
           (fixed2 1) " " (fixed2 1) " " (fixed2 1) " "
           (fixed2 (pos 0)) " " (fixed2 (pos 1)) " " (fixed2 (pos 2)) " " (fixed2 ry)))))

(defn make-kitti-writer
  []
  (let [output-dir (atom "_out")
        width (atom 1242)
        height (atom 375)
        labels (atom {})
        images (atom {})]
    (reify IUtsushimiWriter
      (initialize! [_ init]
        (reset! output-dir (or (:output-dir init) "_out"))
        (reset! width (or (:image-width init) 1242))
        (reset! height (or (:image-height init) 375)))
      (attach! [_ _cams] nil)
      (write-frame! [_ frame-index sample]
        (let [lines (keep #(kitti-line % @width @height) (:primitives sample))]
          (swap! labels assoc (str @output-dir "/label_2/" (pad frame-index 6) ".txt")
                 (str (str/join "\n" lines) (if (seq lines) "\n" "")))
          (swap! images assoc (str @output-dir "/image_2/" (pad frame-index 6) ".json")
                 (json/write-str {:frame frame-index :placeholder true}))))
      (finalize-writer [_] {:labels @labels})
      (to-files [_] (merge @labels @images)))))

;; ── WriterRegistry ─────────────────────────────────────────────────────

(def ^:private registry
  (atom {"BasicWriter" make-basic-writer
         "CocoWriter" make-coco-writer
         "KittiWriter" make-kitti-writer}))

(defn writer-registry-get
  [name]
  (if-let [ctor (get @registry name)]
    (ctor)
    (throw (ex-info (str "unknown writer: " name) {:name name}))))

(defn writer-registry-register!
  [name ctor]
  (swap! registry assoc name ctor))
