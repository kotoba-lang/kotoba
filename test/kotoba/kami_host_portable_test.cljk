(ns kotoba.kami-host-portable-test
  "The genuinely portable slice of kotoba.kami-game-test:
  `kami-host-core-ecs-ops` (its own `testing` blocks say so -- \"no wasm
  involved\") exercises only kotoba.kami-host's pure, portable ECS core
  (atoms, sorted-map, double math, the seeded xorshift64 stream), the exact
  :cljs canonical non-JVM runtime the namespace's own docstring names. Every
  other deftest in kami_game_test.clj drives real compiled Wasm through
  Chicory (kotoba.runtime/kotoba.wasm-exec, both .clj-only) and stays there."
  (:require #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing] :include-macros true])
            [kotoba.kami-host :as kami]))

(deftest kami-host-core-ecs-ops
  (testing "spawn/despawn/position/velocity/queries, no wasm involved"
    (let [state (kami/fresh-state 7)
          p (kami/spawn-entity! state "player")
          g (kami/spawn-entity! state "ghost")]
      (is (= 0 p))
      (is (= 1 g))
      (is (= 0 (kami/set-position! state g 30.0 40.0)))
      (is (= 1 (kami/count-tagged state "player")))
      (is (= 1 (kami/count-tagged state "ghost")))
      (is (= g (kami/nearest-tagged state "ghost" 0.0 0.0 100.0)))
      (is (= -1 (kami/nearest-tagged state "ghost" 0.0 0.0 10.0))
          "50 units away is outside a 10-unit max-dist")
      (is (= 1 (kami/move-tagged-toward! state "ghost" 0.0 0.0 5.0)))
      (kami/step! state 1.0)
      (is (< (kami/get-x state g) 30.0)
          "one integrated step moved the ghost toward the origin")
      (is (= 1 (kami/despawn-within! state "ghost" 0.0 0.0 100.0)))
      (is (= 0 (kami/count-tagged state "ghost")))
      (is (= -1 (kami/despawn-entity! state g))
          "already despawned -> -1")))
  (testing "additive 3D position/velocity ABI preserves and integrates z"
    (let [state (kami/fresh-state 7)
          e (kami/spawn-entity! state "body")]
      (is (= 0 (kami/set-position3! state e 1.0 2.0 3.0)))
      (is (= 0 (kami/set-velocity3! state e 0.0 0.0 4.0)))
      (kami/step! state 0.5)
      (is (= 5.0 (kami/get-z state e)))
      (is (= 1.0 (kami/get-x state e)))
      (is (= 2.0 (kami/get-y state e)))))
  (testing "seeded rand is deterministic and in range"
    (let [a (kami/fresh-state 7)
          b (kami/fresh-state 7)
          roll (fn [state] (vec (repeatedly 16 #(kami/rand-int! state 4))))
          rolls (roll a)]
      (is (= rolls (roll b)) "same seed, same stream")
      (is (every? #(<= 0 % 3) rolls)))))
