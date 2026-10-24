(ns kami.webvr.cine-bridge-test
  "Ported 1:1 from kami-engine-sdk's src/lib/webvr/cine-bridge.test.ts (7 assertions)."
  (:require [cljs.test :refer [deftest is testing async]]
            [kami.webvr.cine-bridge :as cb]))

(deftest mock-bridge-returns-a-scene-ready-shaped-result
  (async done
    (let [bridge (cb/create-mock-cine-bridge)]
      (is (true? ((:is-mock? bridge))))
      (-> ((:generate-scene bridge) {:prompt "night shift SCADA HMI alarm"})
          (.then (fn [r]
                   (is (= :mock (:status r)))
                   (is (re-find #"^run_" (:pipeline-run-id r)))
                   (is (re-find #"^mock://" (get-in r [:world-artifact :model-cid])))
                   (is (some? (get-in r [:usd-artifact :bbox-cm])))
                   (done)))))))

(deftest mock-derives-camera-hint-and-mood-palette-from-prompt
  (async done
    (let [bridge (cb/create-mock-cine-bridge)]
      (-> (js/Promise.all
            #js [((:generate-scene bridge) {:prompt "closeup of reactor tank R-12"})
                 ((:generate-scene bridge) {:prompt "critical fire runaway in chemical yard"})])
          (.then (fn [[r1 r2]]
                   (is (= "Closeup" (get-in r1 [:world-artifact :camera-hint])))
                   (is (some #{"crimson"} (get-in r2 [:world-artifact :mood-palette])))
                   (done)))))))

(deftest force-mock-overrides-endpoint
  (async done
    (let [bridge (cb/create-cine-bridge {:endpoint "https://example.test/xrpc/app.etzhayyim.mangaka.cineGenerateScene"
                                          :force-mock? true})]
      (is (true? ((:is-mock? bridge))))
      (-> ((:generate-scene bridge) {:prompt "x"})
          (.then (fn [r] (is (= :mock (:status r))) (done)))))))

(defn- fake-fetch [status body]
  (fn [_url _opts]
    (js/Promise.resolve
      #js {:ok (= status 200) :status status
           :json (fn [] (js/Promise.resolve body))})))

(deftest decodes-a-live-pod-response-shape
  (async done
    (let [body #js {:pipeline_run_id "pod_abc" :status "scene_ready"
                    :stage_records #js {:worldModel #js {:modelCid "cid1" :seed 1 :tokenCount 10
                                                          :summary "s" :moodPalette #js ["steel"]
                                                          :cameraHint "MediumShot"}
                                        :usdScene #js {:usdaCid "a" :usdcCid "b" :layerCount 1
                                                       :bboxCm #js {:minX -1 :minY 0 :minZ -1 :maxX 1 :maxY 1 :maxZ 1}}
                                        :neuralGeom #js {:assetCid "g1" :format "gaussianSplat"
                                                         :url "https://b2.example/geom.ply"}
                                        :temporalField #js {:assetCid "t1" :frameStart 1 :frameEnd 24 :fps 24}}}
          bridge (cb/create-cine-bridge {:endpoint "https://example.test/xrpc/app.etzhayyim.mangaka.cineGenerateScene"
                                         :fetch-impl (fake-fetch 200 body)})]
      (is (false? ((:is-mock? bridge))))
      (-> ((:generate-scene bridge) {:prompt "x"})
          (.then (fn [r]
                   (is (= :scene_ready (:status r)))
                   (is (= "pod_abc" (:pipeline-run-id r)))
                   (is (= "gaussianSplat" (get-in r [:geom-artifact :format])))
                   (is (= "https://b2.example/geom.ply" (get-in r [:geom-artifact :url])))
                   (is (= 24 (get-in r [:temporal-artifact :fps])))
                   (done)))))))

(deftest falls-back-to-mock-on-http-error-and-surfaces-error
  (async done
    (let [bridge (cb/create-cine-bridge {:endpoint "https://example.test/xrpc/app.etzhayyim.mangaka.cineGenerateScene"
                                         :fetch-impl (fake-fetch 500 #js {})})]
      (-> ((:generate-scene bridge) {:prompt "x"})
          (.then (fn [r]
                   (is (= :error (:status r)))
                   (is (re-find #"HTTP 500" (:error r)))
                   (done)))))))

(deftest mock-generate-panel-returns-a-mock-status-artifact-with-a-b2-stub-key
  (async done
    (let [bridge (cb/create-cine-bridge {:endpoint "https://example.test/xrpc/app.etzhayyim.mangaka.cineGenerateScene"
                                         :force-mock? true})]
      (-> ((:generate-panel bridge) {:pipeline-run-id "run_test" :panel-rkey "panel-detect" :prompt "x"})
          (.then (fn [r]
                   (is (= :mock (:status r)))
                   (is (= "run_test" (:pipeline-run-id r)))
                   (is (= "panel-detect" (:panel-rkey r)))
                   (is (re-find #"^mock://panel/" (:panel-blob-key r)))
                   (is (string? (:panel-url r)))
                   (is (> (:score-permille r) 0))
                   (done)))))))

(deftest decodes-a-live-cine-generate-panel-response-shape
  (async done
    (let [body #js {:pipeline_run_id "pod_abc"
                    :status "panels_rendered"
                    :panels #js [#js {:panel_rkey "panel-1" :panel_blob_key "blobkey"
                                      :url "https://b2.example/panels/panel-1.png" :score 0.86}]}
          bridge (cb/create-cine-bridge {:endpoint "https://example.test/xrpc/app.etzhayyim.mangaka.cineGenerateScene"
                                         :fetch-impl (fake-fetch 200 body)})]
      (-> ((:generate-panel bridge) {:pipeline-run-id "run_x" :panel-rkey "panel-1" :prompt "x"})
          (.then (fn [r]
                   (is (= :panels-rendered (:status r)))
                   (is (= "https://b2.example/panels/panel-1.png" (:panel-url r)))
                   (is (= 860 (:score-permille r)))
                   (done)))))))
