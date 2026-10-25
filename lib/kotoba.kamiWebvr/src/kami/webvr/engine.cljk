(ns kami.webvr.engine
  "The choice-scenario reactive engine (ported from kami-engine-sdk's
   src/lib/webvr/createIncidentVrEngine.svelte.ts). Svelte 5 runes ($state)
   become a plain atom -- same shape, no framework dependency.

   `on-scene` (SceneDescriptor -> any) is called synchronously and immediately
   on every `publish!` (construction, every `select!`, every `reset!`) with
   the base scene (no cine/panel resolved yet), then again 0-2 more times
   asynchronously as cine/panel artifacts resolve, each time with a freshly
   rebuilt COMPLETE SceneDescriptor (never a partial diff) -- this exact
   multi-call cascade timing is preserved 1:1 from the original, since a
   caller may depend on receiving the first callback synchronously before any
   microtask tick."
  (:require [kami.webvr.types :as t]
            [kami.webvr.incident-pregel :as p]))

(defn- now-iso [] (.toISOString (js/Date.)))

(defn create-incident-vr-engine
  "opts: {:scenario :on-scene :on-oplog :cine-bridge}. Returns
   {:state (fn []) :scene (fn []) :history (fn []) :reset! (fn []) :select! (fn [choice-id])}."
  [{:keys [scenario on-scene on-oplog cine-bridge]}]
  (let [!state (atom (p/initial-state scenario))
        !scene (atom nil)
        cine-cache (atom {})
        panel-cache (atom {})

        build-scene
        (fn [& [{:keys [cine panel]}]]
          (let [state @!state
                n (or (get-in scenario [:nodes (:current state)])
                      (throw (ex-info (str "webvr: unknown node \"" (:current state) "\"") {})))]
            {:location (:location n) :camera-hint (:camera-hint n)
             :choices (mapv #(select-keys % [:id :label :hint]) (:choices n))
             :briefing (:briefing n) :severity (:severity n) :stage (:stage n)
             :terminal (:terminal n)
             :cine (or cine (get @cine-cache (:id n)))
             :cine-panel (or panel (get @panel-cache (:id n)))
             :effects (:effects n) :node-id (:id n)}))

        resolve-cine
        (fn []
          (let [n (get-in scenario [:nodes (:current @!state)])]
            (if (or (not (:cine n)) (not cine-bridge))
              (js/Promise.resolve nil)
              (if-let [cached (get @cine-cache (:id n))]
                (js/Promise.resolve cached)
                (-> ((:generate-scene cine-bridge)
                     {:prompt (get-in n [:cine :prompt]) :style (get-in n [:cine :style])
                      :frame-start 1 :frame-end (or (get-in n [:cine :frames]) 1)
                      :fps 24 :dry-run? true})
                    (.then (fn [artifacts] (swap! cine-cache assoc (:id n) artifacts) artifacts))
                    (.catch (fn [e] (js/console.warn "webvr cine resolve failed:" e) nil)))))))

        resolve-panel
        (fn [cine]
          (let [n (get-in scenario [:nodes (:current @!state)])]
            (if (or (not (:cine n)) (not cine-bridge))
              (js/Promise.resolve nil)
              (if-let [cached (get @panel-cache (:id n))]
                (js/Promise.resolve cached)
                (-> ((:generate-panel cine-bridge)
                     {:pipeline-run-id (:pipeline-run-id cine) :panel-rkey (str "panel-" (:id n))
                      :framing (get-in cine [:world-artifact :camera-hint])
                      :prompt (get-in n [:cine :prompt])
                      :mood-palette (get-in cine [:world-artifact :mood-palette])})
                    (.then (fn [artifact] (swap! panel-cache assoc (:id n) artifact) artifact))
                    (.catch (fn [e] (js/console.warn "webvr panel resolve failed:" e) nil)))))))

        publish!
        (fn []
          (let [scene (build-scene)]
            (reset! !scene scene)
            (when on-scene (on-scene scene))
            (when on-oplog
              (on-oplog {:op (if (:done @!state) :terminate :enter)
                         :node-id (:current @!state) :kpi (:kpi @!state) :at (now-iso)}))
            (-> (resolve-cine)
                (.then (fn [cine]
                         (when cine
                           (let [scene (build-scene {:cine cine})]
                             (reset! !scene scene)
                             (when on-scene (on-scene scene)))
                           (-> (resolve-panel cine)
                               (.then (fn [panel]
                                        (when panel
                                          (let [scene (build-scene {:cine cine :panel panel})]
                                            (reset! !scene scene)
                                            (when on-scene (on-scene scene)))))))))))))]

    (publish!)

    {:state (fn [] @!state)
     :scene (fn [] @!scene)
     :history (fn [] (:history @!state))

     :select!
     (fn [choice-id]
       (when-not (:done @!state)
         (let [next (p/apply-selection scenario @!state choice-id)]
           (reset! !state next)
           (when (and on-oplog (seq (:history next)))
             (let [last-decision (peek (:history next))]
               (on-oplog {:op :choose :node-id (:node-id last-decision)
                         :choice-id (:choice-id last-decision)
                         :kpi (:kpi-after last-decision) :at (:taken-at last-decision)})))
           (publish!))))

     :reset!
     (fn []
       (reset! !state (p/initial-state scenario))
       (publish!))}))
