(ns hello-scene
  "Minimal end-to-end shape of a kami-engine-sdk-clj app (ARCHITECTURE.md §12).
  This is illustrative wiring against the stubbed API — it does not run yet.

  Two halves, one .cljc file:
    - AUTHORING (JVM): define a scene as tx-data, transact to Datomic, snapshot.
    - RUNTIME (browser): load snapshot, register a system, run the loop."
  (:require [kami.scene :as scene]
            [kami.sim   :as sim :refer [defsystem]]
            [kami.ecs   :as ecs]
            #?(:clj [kami.db :as db])
            #?(:cljs [kami.backend.browser :as browser])))

;; --- assets + scene as plain tx-data (the Datomic source of truth) ----------

(def assets
  [{:asset/id "mesh/conifer" :asset/kind :mesh     :asset/uri "b2://kami/meshes/conifer.kmesh"}
   {:asset/id "mat/bark"     :asset/kind :material :asset/uri "b2://kami/mats/bark.kmat"}])

(defn forest-tx
  "A tiny forest + a camera, as a tx. `n` trees placed by the caller's layout fn."
  [tree-positions]
  (into [{:kami/eid (random-uuid) :kami/name "main-cam"
          :camera/fov 60.0 :camera/near 0.1 :camera/far 1000.0 :camera/active? true
          :transform/translation [0.0 4.0 12.0]
          :transform/rotation    [0.0 0.0 0.0 1.0]}]
        (for [[x z] tree-positions]
          {:kami/eid (random-uuid) :kami/name "tree"
           :transform/translation [(double x) 0.0 (double z)]
           :transform/rotation    [0.0 0.0 0.0 1.0]
           :transform/scale       [1.0 1.0 1.0]
           :mesh/asset     [:asset/id "mesh/conifer"]
           :material/asset [:asset/id "mat/bark"]
           :script/systems [:hello-scene/sway]})))

;; --- a gameplay system (pure over the ECS world) ----------------------------

(defsystem sway {:order 10} [world dt]
  "Gently rotate every tree — runs each fixed step in the browser."
  (reduce (fn [w e] (ecs/set-component w e :transform/rotation (comment "…dt-driven quat…")))
          world
          (ecs/query world #{:transform/rotation :mesh/asset})))

;; --- authoring entry (JVM) --------------------------------------------------

#?(:clj
   (defn build! [uri tree-positions]
     "Transact schema + assets + scene, then return a portable snapshot to serve."
     (let [conn (db/connect uri)]
       @(db/transact! conn scene/schema)
       @(db/transact! conn assets)
       @(db/transact! conn (forest-tx tree-positions))
       (scene/snapshot (db/db conn)))))

;; --- runtime entry (browser) ------------------------------------------------

#?(:cljs
   (defn ^:export start [canvas-id snapshot wasm]
     "Boot the runtime: snapshot (fetched over the wire) → ECS → RAF loop → WebGPU."
     (sim/run! {:canvas   canvas-id
                :snapshot snapshot
                :backend  (browser/make {:canvas canvas-id :wasm wasm})
                :systems  [:hello-scene/sway]
                :hz       30})))
