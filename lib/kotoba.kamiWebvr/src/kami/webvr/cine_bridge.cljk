(ns kami.webvr.cine-bridge
  "Thin client for the 'kami-cine' pipeline (ported from kami-engine-sdk's
   src/lib/webvr/cine-bridge.ts): stages 1-4 (worldModel -> usdScene ->
   neuralGeom -> temporalField) via a remote LangGraph pod, or a deterministic
   offline mock. AT-lexicon float discipline: bbox is integer cm, frame range
   is integer frames, fps is integer.

   `:fetch-impl` is always explicit (never a bare `js/fetch` reference inside
   the request functions) so tests can inject a fake implementation without
   any network -- same injectable-fetch pattern this org already uses for
   testability elsewhere (e.g. kotoba.turn.credential's reader-conditional
   split)."
  (:require [kotoba.lang.text :as str]))

;; --- pure helpers -------------------------------------------------------

(defn- hash32
  "FNV-1a 32-bit hash of a string -- deterministic per prompt so mock retries
   are stable."
  [s]
  (let [len (count s)]
    (loop [i 0 h 0x811c9dc5]
      (if (>= i len)
        (unsigned-bit-shift-right h 0)
        (recur (inc i) (js/Math.imul (bit-xor h (.charCodeAt s i)) 0x01000193))))))

(defn- default-bbox []
  {:min-x -400 :min-y 0 :min-z -400 :max-x 400 :max-y 300 :max-z 400})

(defn- camera-hint-for [prompt]
  (cond
    (re-find #"(?i)closeup|details|reactor|tank" prompt) "Closeup"
    (re-find #"(?i)overview|panorama|wide|yard" prompt) "FullShot"
    (re-find #"(?i)shoulder|operator|console" prompt) "OverShoulder"
    :else "MediumShot"))

(defn- mood-palette-for [prompt]
  (cond
    (re-find #"(?i)critical|fire|explosion|runaway" prompt) ["ember" "crimson" "amber"]
    (re-find #"(?i)press|coverup|fail" prompt) ["crimson" "charcoal" "ash"]
    (re-find #"(?i)recover|success|board" prompt) ["oak" "cream" "sage"]
    (re-find #"(?i)night|02:14|shift" prompt) ["indigo" "steel" "cyan"]
    :else ["steel" "cream" "cyan"]))

(defn- new-run-id []
  (str "run_" (.toString (.getTime (js/Date.)) 36) "_"
       (.toString (js/Math.floor (* (js/Math.random) 0xffffff)) 36)))

(defn- mock-result [{:keys [prompt pipeline-run-id extents-cm]}]
  (let [run-id (or pipeline-run-id (new-run-id))
        seed (hash32 prompt)
        camera (camera-hint-for prompt)
        palette (mood-palette-for prompt)]
    {:pipeline-run-id run-id
     :status :mock
     :world-artifact {:model-cid (str "mock://world/" run-id ".json")
                      :seed seed :token-count 256
                      :summary (str "mock summary — " (subs prompt 0 (min 64 (count prompt))) "…")
                      :mood-palette palette :camera-hint camera}
     :usd-artifact {:usda-cid (str "mock://usd/" run-id ".usda")
                    :usdc-cid (str "mock://usd/" run-id ".usdc")
                    :layer-count 3
                    :bbox-cm (or extents-cm (default-bbox))}}))

(def ^:private palette-hex
  {"ember" "#e0623a" "crimson" "#a4242e" "amber" "#d4a73a" "indigo" "#3b4574"
   "steel" "#5c6675" "cyan" "#4dc1ff" "cream" "#f0ead6" "oak" "#8b6a3f"
   "sage" "#a8b59a" "charcoal" "#26303d" "ash" "#9aa3b2"})

(defn- palette->hex [token] (get palette-hex token "#888888"))

(defn- mock-panel [{:keys [pipeline-run-id panel-rkey framing prompt mood-palette severity-tint]}]
  ;; Canvas-based PNG synthesis only runs where `js/document` exists; falls
  ;; back to an empty data URL otherwise (matches the original TS's graceful
  ;; jsdom-without-canvas-backend behavior).
  (let [data-url
        (if (exists? js/document)
          (try
            (let [cv (.createElement js/document "canvas")]
              (set! (.-width cv) 1024) (set! (.-height cv) 576)
              (let [ctx (.getContext cv "2d")
                    [c1 c2 c3] (or (seq mood-palette) ["steel" "cream" "cyan"])
                    grad (.createLinearGradient ctx 0 0 1024 576)]
                (.addColorStop grad 0 (palette->hex c1))
                (.addColorStop grad 0.5 (palette->hex (or c2 c1)))
                (.addColorStop grad 1 (palette->hex (or c3 c1)))
                (set! (.-fillStyle ctx) grad)
                (.fillRect ctx 0 0 1024 576)
                (set! (.-fillStyle ctx) (or severity-tint "#e07b1c"))
                (.fillRect ctx 16 16 260 28)
                (set! (.-fillStyle ctx) "#fff")
                (.fillText ctx (str "STAGE 6 · " (or framing "MediumShot")) 22 36)
                (set! (.-fillStyle ctx) "#fff")
                (.fillText ctx (or prompt "") 16 560))
              (.toDataURL cv "image/png"))
            (catch :default _ ""))
          "")]
    {:pipeline-run-id pipeline-run-id :panel-rkey panel-rkey
     :panel-blob-key (str "mock://panel/" pipeline-run-id "/" panel-rkey ".png")
     :panel-url data-url
     :score-permille 820
     :status :mock}))

(defn- decode-bbox [js-bbox fallback]
  (if js-bbox
    {:min-x (.-minX js-bbox) :min-y (.-minY js-bbox) :min-z (.-minZ js-bbox)
     :max-x (.-maxX js-bbox) :max-y (.-maxY js-bbox) :max-z (.-maxZ js-bbox)}
    fallback))

(defn- decode-world-artifact [w]
  (when w
    {:model-cid (.-modelCid w) :seed (.-seed w) :token-count (.-tokenCount w)
     :summary (.-summary w) :mood-palette (vec (.-moodPalette w)) :camera-hint (.-cameraHint w)}))

(defn- decode-usd-artifact [u input]
  (when u
    {:usda-cid (.-usdaCid u) :usdc-cid (.-usdcCid u) :layer-count (.-layerCount u)
     :bbox-cm (decode-bbox (.-bboxCm u) (or (:extents-cm input) (default-bbox)))}))

(defn- decode-geom-artifact [g]
  (when g
    {:asset-cid (.-assetCid g) :format (or (.-format g) "gaussianSplat")
     :point-count (.-pointCount g) :url (.-url g)}))

(defn- decode-temporal-artifact [tm input]
  (when tm
    {:asset-cid (.-assetCid tm) :format (or (.-format tm) "gaussian4d")
     :frame-start (or (.-frameStart tm) (:frame-start input) 1)
     :frame-end (or (.-frameEnd tm) (:frame-end input) 1)
     :fps (or (.-fps tm) (:fps input) 24)}))

(defn- decode-pod-scene-response [body input]
  (let [stage-records (or (.-stage_records body) #js {})
        world (.-worldModel stage-records)
        usd (.-usdScene stage-records)
        geom (or (.-neuralGeom stage-records) (.-geom stage-records))
        temporal (.-temporalField stage-records)]
    (cond-> {:pipeline-run-id (str (or (.-pipeline_run_id body) (:pipeline-run-id input)))
             :status (keyword (.-status body))}
      world (assoc :world-artifact (decode-world-artifact world))
      usd (assoc :usd-artifact (decode-usd-artifact usd input))
      geom (assoc :geom-artifact (decode-geom-artifact geom))
      temporal (assoc :temporal-artifact (decode-temporal-artifact temporal input)))))

;; --- bridge construction --------------------------------------------------

(defn create-cine-bridge
  "opts: {:endpoint :token :force-mock? :timeout-ms :fetch-impl}. Returns
   {:generate-scene (fn [input]) :generate-panel (fn [input]) :is-mock? (fn [])},
   each returning a JS Promise of a plain Clojure map (matching the original
   async API's shape, just EDN instead of a JS object)."
  [{:keys [endpoint token force-mock? timeout-ms fetch-impl]
    :or {timeout-ms 8000}}]
  (let [fetch-impl (or fetch-impl (when (exists? js/fetch) js/fetch))
        use-mock? (boolean (or force-mock? (not endpoint) (not fetch-impl)))
        panel-endpoint (when endpoint (str/replace endpoint #"cineGenerateScene$" "cineGeneratePanel"))]
    {:is-mock? (fn [] use-mock?)

     :generate-scene
     (fn [{:keys [prompt style pipeline-run-id extents-cm frame-start frame-end fps dry-run?] :as input}]
       (if use-mock?
         (js/Promise.resolve (mock-result input))
         (-> (fetch-impl endpoint
                #js {:method "POST"
                     :headers (let [h #js {"content-type" "application/json"}]
                                (when token (aset h "authorization" (str "Bearer " token)))
                                h)
                     :body (js/JSON.stringify
                             #js {:prompt prompt :style (or style "") :world_kind "threeD"
                                  :extents_cm (clj->js extents-cm) :frame_start (or frame-start 1)
                                  :frame_end (or frame-end 1) :fps (or fps 24)
                                  :dry_run (if (some? dry-run?) dry-run? true)
                                  :pipeline_run_id pipeline-run-id})})
             (.then (fn [res]
                      (if-not (.-ok res)
                        {:pipeline-run-id (or pipeline-run-id (new-run-id))
                         :status :error :error (str "HTTP " (.-status res))}
                        (.then (.json res) (fn [body] (decode-pod-scene-response body input))))))
             (.catch (fn [e] (assoc (mock-result input) :error (.-message e)))))))

     :generate-panel
     (fn [{:keys [pipeline-run-id panel-rkey framing prompt mood-palette] :as input}]
       (if (or use-mock? (not panel-endpoint))
         (js/Promise.resolve (mock-panel input))
         (-> (fetch-impl panel-endpoint
                #js {:method "POST"
                     :headers #js {"content-type" "application/json"}
                     :body (js/JSON.stringify
                             #js {:pipeline_run_id pipeline-run-id :page_rkey panel-rkey
                                  :panels #js [#js {:panel_rkey panel-rkey
                                                     :framing (or framing "MediumShot")
                                                     :prompt prompt
                                                     :mood_palette (clj->js (or mood-palette []))}]})})
             (.then (fn [res]
                      (if-not (.-ok res)
                        {:pipeline-run-id pipeline-run-id :panel-rkey panel-rkey
                         :panel-blob-key "" :panel-url "" :score-permille 0 :status :error
                         :error (str "HTTP " (.-status res))}
                        (.then (.json res)
                               (fn [body]
                                 (let [p (or (first (.-panels body)) #js {})]
                                   {:pipeline-run-id (str (or (.-pipeline_run_id body) pipeline-run-id))
                                    :panel-rkey (str (or (.-panel_rkey p) panel-rkey))
                                    :panel-blob-key (str (or (.-panel_blob_key p) ""))
                                    :panel-url (str (or (.-url p) (.-panel_url p) ""))
                                    :score-permille (js/Math.round (* (or (.-score p) 0) 1000))
                                    :status :panels-rendered}))))))
             (.catch (fn [e] (assoc (mock-panel input) :error (.-message e)))))))}))

(defn create-mock-cine-bridge []
  (create-cine-bridge {:force-mock? true}))
