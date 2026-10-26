(ns kotoba.kami-ecs
  "The JS-facing adapter for kotoba.kami-host (the VENDORED portable .cljc
  under src-cljs/vendor/ — kotoba-lang/kotoba's deterministic game-engine
  ECS behind the kami-* host imports). Authored in ClojureScript and
  compiled once via shadow-cljs.edn's :kami-ecs build to `src/kami-ecs.js`
  (:target :esm), replacing the earlier hand-JS port of the same module —
  per the monorepo-wide runtime priority (kotoba wasm > clojurewasm >
  ClojureScript > nbb, JVM last resort), the ONE .cljc now serves the JVM
  compat suite, the nbb parity script, and this browser/Node ESM, instead
  of a hand-maintained JS duplicate that could drift.

  The exported API is unchanged from the hand-JS version —
  `createKamiEcs(seed)` (a plain JS object of methods) and
  `kamiHostImports(ecs, memoryBox)` — so examples/kami-survivors and
  test/verify-kami-survivors.mjs consume it as before."
  (:require [kotoba.kami-host :as kami]))

(defn create-kami-ecs
  ([] (create-kami-ecs 7))
  ([seed]
   (let [state (kami/fresh-state seed)]
     #js {:_state state
          :spawnEntity (fn [tag] (kami/spawn-entity! state tag))
          :despawnEntity (fn [id] (kami/despawn-entity! state id))
          :setPosition (fn [id x y] (kami/set-position! state id x y))
          :setVelocity (fn [id vx vy] (kami/set-velocity! state id vx vy))
          :getX (fn [id] (kami/get-x state id))
          :getY (fn [id] (kami/get-y state id))
          :countTagged (fn [tag] (kami/count-tagged state tag))
          :nearestTagged (fn [tag x y max-dist] (kami/nearest-tagged state tag x y max-dist))
          :moveTaggedToward (fn [tag x y speed] (kami/move-tagged-toward! state tag x y speed))
          :despawnWithin (fn [tag x y radius] (kami/despawn-within! state tag x y radius))
          :setAxis (fn [name v] (kami/set-axis! state name v))
          :axis (fn [name] (kami/axis state name))
          :tickN (fn [] (kami/tick-n state))
          :randInt (fn [n] (kami/rand-int! state n))
          :step (fn [dt] (kami/step! state (if (number? dt) dt kami/default-dt)))
          :entityCount (fn [] (count @(:entities state)))
          :totalSpawned (fn [] @(:next-id state))
          :entries (fn []
                     (into-array
                      (map (fn [[id e]]
                             #js [id #js {:tag (:tag e) :x (:x e) :y (:y e)
                                          :vx (:vx e) :vy (:vy e)}])
                           @(:entities state))))})))

(defn kami-host-imports [ecs memory-box]
  (kami/kami-host-imports (.-_state ^js ecs) memory-box))
