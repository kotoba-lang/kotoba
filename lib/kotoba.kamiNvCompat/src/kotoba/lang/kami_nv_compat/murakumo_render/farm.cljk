(ns kotoba.lang.kami-nv-compat.murakumo-render.farm
  "murakumo-render — clean-room cloud render farm (Omniverse Cloud lineage) —
  portable .cljc port of src/murakumo-render/farm.ts. Wave 27.

  The canonical KAMI implementation behind nv-compat/omni-cloud. NVIDIA
  Omniverse Cloud offers managed/streamed rendering of Omniverse scenes;
  this module reproduces a render-FARM job model — submit a render job (a
  scene + one or more cameras + settings), the farm executes it via the
  kami renderers, and frames are retrieved or streamed back.

  Charter: per ADR-2605215000 the religious-corp compute path is the
  Murakumo fleet ONLY — no commercial GPU rental / vendor cloud. This farm
  executes locally (or on the Murakumo fleet), never a third-party cloud.

  Clean-room: from-spec job queue over kami-rt / kami-rtx. No Omniverse
  Cloud source/binaries. ADR-2605261800 SD6 / D10.4 murakumo-render."
  (:require [kotoba.lang.kami-nv-compat.kami-rt.bvh :as bvh]
            [kotoba.lang.kami-nv-compat.kami-rt.pathtrace :as pt]
            [kotoba.lang.kami-nv-compat.kami-rt.index :as kami-rt]))

(defn- path-scene?
  "A RenderJobSpec's :scene is a PathScene (has :mats) or a ray Scene (no :mats)."
  [scene]
  (contains? scene :mats))

(defn make-farm
  "A new, empty render farm: {:jobs {id -> RenderJob} :seq n}."
  []
  (atom {:jobs {} :seq 0}))

(defn submit!
  "Submit a render job; returns its id. The job starts :queued.
  spec: {:scene :cameras :width :height :mode (:rtx or :pathtrace)
         :shade :path-settings :label}."
  [farm spec]
  (let [id (str "job-" (:seq @farm))]
    (swap! farm (fn [s]
                  (-> s
                      (update :seq inc)
                      (assoc-in [:jobs id]
                                {:id id :spec spec :status :queued
                                 :progress 0.0 :frames []}))))
    id))

(defn get-job [farm id] (get-in @farm [:jobs id]))
(defn job-status [farm id] (:status (get-job farm id)))

(defn job-result [farm id]
  (let [job (get-job farm id)]
    (when (= :done (:status job)) (:frames job))))

(defn pending-jobs
  "ids of all :queued jobs."
  [farm]
  (->> (:jobs @farm) vals (filter #(= :queued (:status %))) (map :id) vec))

(defn- run-frame
  "Render one frame for `cam` per `spec`'s :mode. CPU-synchronous."
  [spec cam]
  (if (= :pathtrace (:mode spec))
    (do
      (when-not (path-scene? (:scene spec))
        (throw (ex-info "pathtrace mode requires a PathScene" {})))
      (:framebuffer (kami-rt/path-trace-cpu (:scene spec) cam (:width spec) (:height spec)
                                             (or (:path-settings spec) pt/default-path-settings))))
    (do
      (when (path-scene? (:scene spec))
        (throw (ex-info "rtx mode requires a ray Scene" {})))
      (:framebuffer (kami-rt/trace-image-cpu (:scene spec) cam (:width spec) (:height spec)
                                              (or (:shade spec) bvh/default-shade))))))

(defn run-job!
  "Render one job to completion. `on-frame`, if given, is called (frame idx)
  as each frame lands. Returns the job (post-run)."
  ([farm id] (run-job! farm id nil))
  ([farm id on-frame]
   (swap! farm (fn [s] (-> s
                           (assoc-in [:jobs id :status] :running)
                           (assoc-in [:jobs id :frames] []))))
   (try
     (let [spec (:spec (get-job farm id))
           cams (:cameras spec)
           n (count cams)]
       (doseq [[i cam] (map-indexed vector cams)]
         (let [fb (run-frame spec cam)]
           (swap! farm (fn [s] (-> s
                                   (update-in [:jobs id :frames] conj fb)
                                   (assoc-in [:jobs id :progress] (/ (double (inc i)) n)))))
           (when on-frame (on-frame fb i))))
       (swap! farm assoc-in [:jobs id :status] :done))
     (catch #?(:clj Exception :cljs :default) e
       (swap! farm (fn [s] (-> s
                               (assoc-in [:jobs id :status] :error)
                               (assoc-in [:jobs id :error] (ex-message e)))))))
   (get-job farm id)))

(defn run-all!
  "Run all queued jobs (FIFO). Returns the resulting jobs."
  [farm]
  (mapv #(run-job! farm %) (pending-jobs farm)))

(defn turntable-cameras
  "Build a turntable of `n` cameras orbiting `target` at `radius`/`height` —
  one frame per camera (a common cloud-render batch). `make-camera` is
  `(fn [eye target] Camera)`."
  [make-camera target radius height n]
  (vec (for [i (range n)]
         (let [a (* (/ (double i) n) Math/PI 2.0)]
           (make-camera [(+ (target 0) (* radius (Math/cos a)))
                         (+ (target 1) height)
                         (+ (target 2) (* radius (Math/sin a)))]
                        target)))))
