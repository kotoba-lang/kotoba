;; ClojureScript (nbb, no JVM) parity verification for kami-survivors — the
;; runtime-priority counterpart of test/kotoba/kami_game_test.clj: the SAME
;; kotoba.kami-host .cljc namespace (portable ECS core + :cljs
;; kami-host-imports wire layer) hosting the SAME compiled
;; test/kotoba/fixtures/kami_survivors.wasm on Node's native WebAssembly
;; engine, asserting the SAME pinned counts the Chicory suite pins
;; (seed 7: 12 ghosts at tick 240, 8 after the tick-270 nova burst, 10 at
;; 300; player at the origin; 15 entities ever spawned; x=59 axis check).
;;
;; Run from the repo root:
;;   nbb --classpath src scripts/verify_kami_survivors_nbb.cljs
(ns verify-kami-survivors-nbb
  (:require ["node:fs" :as fs]
            [kotoba.kami-host :as kami]))

(def failed (atom false))

(defn check [cond message]
  (if cond
    (println "OK:" message)
    (do (reset! failed true)
        (println "FAIL:" message))))

(def wasm-bytes (fs/readFileSync "test/kotoba/fixtures/kami_survivors.wasm"))

(defn new-game [seed]
  (let [state (kami/fresh-state seed)
        memory-box #js {}]
    (-> (js/WebAssembly.instantiate
         wasm-bytes
         #js {:kotoba (kami/kami-host-imports state memory-box)})
        (.then (fn [result]
                 (let [instance (.-instance result)]
                   (set! (.-memory memory-box) (.. instance -exports -memory))
                   {:state state
                    :run-ticks! (fn [n]
                                  (loop [i 0 last-result nil]
                                    (if (< i n)
                                      (do (kami/step! state)
                                          (recur (inc i) ((.. instance -exports -main))))
                                      last-result)))}))))))

(defn abs [x] (if (neg? x) (- x) x))

(-> (new-game 7)
    (.then
     (fn [{:keys [state run-ticks!]}]
       (check (= 12 (run-ticks! 240))
              "spawn every 20 ticks -> the 12-ghost cap is exactly reached at tick 240")
       (check (= 8 (run-ticks! 30))
              "tick-270 nova burst despawns the 4 ghosts that reached the player")
       (check (= 10 (run-ticks! 30))
              "spawning resumes after the burst: ticks 280/300 add 2")
       (check (= 1 (kami/count-tagged state "player")) "exactly one player")
       (check (= 10 (kami/count-tagged state "ghost"))
              "host state agrees with what main reported")
       (check (= 15 @(:next-id state)) "1 player + 14 ghosts ever spawned, nothing else")
       (check (< (abs (kami/get-x state 0)) 1e-6)
              "with both axes unset the player never left the origin")
       (new-game 7)))
    (.then
     (fn [{:keys [state run-ticks!]}]
       (kami/set-axis! state "MoveX" 1.0)
       (run-ticks! 60)
       (let [px (kami/get-x state 0)]
         (check (and (> px 58.9) (< px 59.1))
                (str "59 integrated steps moved the player to x=" px)))
       (check (< (abs (kami/get-y state 0)) 1e-6)
              "the unset MoveY axis left y untouched")
       (if @failed
         (js/process.exit 1)
         (println "OK: kami-survivors (.kotoba) plays the same pinned game on ClojureScript/nbb — no JVM"))))
    (.catch (fn [e]
              (println "FAIL:" (.-message e))
              (js/process.exit 1))))
