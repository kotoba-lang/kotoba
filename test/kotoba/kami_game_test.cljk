(ns kotoba.kami-game-test
  "The first GAME authored directly in a `.kotoba` file
  (src/kami_survivors.kotoba, docs/DEMONSTRATIONS.md's \"natural next
  demonstration\"): proves the kami-* game-engine ECS host imports
  (kotoba-core-contracts \"kami/engine\") compile through `kotoba wasm
  emit`'s real emitter and drive a genuinely playable survivors-style core
  loop on Chicory via kotoba.kami-host — same parity-by-pinned-counts
  method kotoba-lang/wasm-webcomponent's verify-kami-engine-host.mjs uses
  for netsurvivors (seeded rand + fixed-step integration = the same run
  every time, so exact entity counts are assertable, not flaky).

  `kami-host-core-ecs-ops` (the one deftest that touched no Wasm/Chicory at
  all) has moved to kotoba.kami-host-portable-test (.cljc), registered on
  both hosts -- kotoba.kami-host's own docstring names ClojureScript/nbb as
  its canonical non-JVM runtime, and that deftest's own `testing` strings
  already said \"no wasm involved\"."
  (:require [clojure.edn :as edn]
            [clojure.test :refer [deftest is testing]]
            [kotoba.kami-host :as kami]
            [kotoba.launcher :as launcher]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- compiled-game []
  (let [forms (runtime/read-file "src/kami_survivors.kotoba" :kotoba)
        policy (edn/read-string (slurp "src/kami_survivors_policy.edn"))
        wasm (runtime/wasm-binary forms policy)]
    {:forms forms :policy policy :wasm wasm}))

(defn- run-ticks!
  "Drive INSTANCE/STATE for N ticks (host integrates + advances tick, THEN
  the guest's main decides — the now-days loop ordering) and return the
  ghost count main reported on the last tick."
  [state instance n]
  (last (for [_ (range n)]
          (do (kami/step! state)
              (wasm-exec/call-main instance)))))

(deftest kami-survivors-fixture-binary-is-in-sync
  (testing "test/kotoba/fixtures/kami_survivors.wasm (the checked-in binary the
            ClojureScript/nbb parity script and wasm-webcomponent's example
            host) is byte-identical to a fresh emit of the source"
    (let [{:keys [wasm]} (compiled-game)
          fixture (java.nio.file.Files/readAllBytes
                   (.toPath (java.io.File. "test/kotoba/fixtures/kami_survivors.wasm")))]
      (is (java.util.Arrays/equals ^bytes fixture ^bytes (:kotoba.wasm/binary wasm))
          "re-emit with: bin/kotoba-clj wasm emit src/kami_survivors.kotoba --policy src/kami_survivors_policy.edn --package-lock kotoba.lock.edn -o test/kotoba/fixtures/kami_survivors.wasm"))))

(deftest kami-survivors-compiles-under-its-policy
  (let [{:keys [forms policy wasm]} (compiled-game)
        checked (runtime/check (launcher/safe-analyzer-fact-classification)
                               (launcher/source-plan "src/kami_survivors.kotoba")
                               forms policy)]
    (is (:kotoba.runtime/ok? checked)
        "static capability check admits :kami/engine")
    (is (:kotoba.wasm/ok? wasm))
    (is (= #{"kami/engine"} (set (runtime/required-capabilities forms)))
        "the game needs exactly the one shared kami/engine capability")
    (testing "without the grant, static admission refuses the same source"
      (is (some #(= :capability-not-granted (:kotoba.runtime/problem %))
                (runtime/source-problems (launcher/safe-analyzer-fact-classification)
                                         forms
                                         {:kotoba.policy/capabilities #{}}))))))

(deftest kotoba-3d-surface-lowers-to-additive-kami-abi
  (let [forms (runtime/read-forms
               "(defn main [] (let [e (spawn-entity \"body\")
                                    _p (set-position! e (f32 1.0) (f32 2.0) (f32 3.0))
                                    _v (set-velocity! e (f32 0.0) (f32 0.0) (f32 4.0))]
                                0))"
               :kotoba)
        lowered (pr-str (runtime/lower-language-forms forms))]
    (is (re-find #"kami-set-position3!" lowered))
    (is (re-find #"kami-set-velocity3!" lowered))
    (is (not (re-find #"kami-set-position!.*3\.0" lowered))
        "the z component is routed to the 3D ABI, never discarded into 2D")))

(deftest kotoba-3d-abi-executes-through-wasm-host
  (let [forms (runtime/read-forms
               "(defn main [] (let [e (spawn-entity \"body\")
                                    _p (set-position! e (f32 1.0) (f32 2.0) (f32 3.0))
                                    _v (set-velocity! e (f32 0.0) (f32 0.0) (f32 4.0))]
                                0))"
               :kotoba)
        policy {:kotoba.policy/capabilities #{:kami/engine}}
        wasm (runtime/wasm-binary forms policy)
        state (kami/fresh-state 7)
        instance (wasm-exec/instantiate (:kotoba.wasm/binary wasm)
                                        (kami/kami-host-functions state policy)
                                        policy)]
    (is (:kotoba.wasm/ok? wasm))
    (is (= 0 (wasm-exec/call-main instance)))
    (is (= 3.0 (kami/get-z state 0)))
    (kami/step! state 0.5)
    (is (= 5.0 (kami/get-z state 0)))))

(deftest kami-survivors-plays-deterministically-through-real-chicory
  (testing "300 ticks of the survivors loop on Chicory, exact pinned counts
            (seed 7, dt 1/60): ghosts spawn every 20 ticks to the 12 cap,
            chase the player, and the tick-270 nova burst kills the 4 that
            have closed the 120-unit ring"
    (let [{:keys [policy wasm]} (compiled-game)
          state (kami/fresh-state 7)
          instance (wasm-exec/instantiate (:kotoba.wasm/binary wasm)
                                          (kami/kami-host-functions state policy)
                                          policy)]
      (is (= 12 (run-ticks! state instance 240))
          "spawn every 20 ticks -> the 12-ghost cap is exactly reached at tick 240")
      (is (= 8 (run-ticks! state instance 30))
          "tick-270 burst despawns the 4 ghosts (spawned by tick 80) that reached the player")
      (is (= 10 (run-ticks! state instance 30))
          "spawning resumes after the burst: ticks 280/300 add 2")
      (is (= 1 (kami/count-tagged state "player")))
      (is (= 10 (kami/count-tagged state "ghost"))
          "host state agrees with what main reported")
      (is (= 15 @(:next-id state))
          "1 player + 14 ghosts ever spawned, nothing else")
      (is (< (Math/abs (kami/get-x state 0)) 1e-6)
          "with both axes unset the player never left the origin"))))

(deftest kami-survivors-player-follows-the-input-axes
  (testing "the host-owned MoveX axis really steers the player (guest reads
            it via kami-axis and scales it to 60 units/second = 1 unit/tick)"
    (let [{:keys [policy wasm]} (compiled-game)
          state (kami/fresh-state 7)
          instance (wasm-exec/instantiate (:kotoba.wasm/binary wasm)
                                          (kami/kami-host-functions state policy)
                                          policy)]
      (kami/set-axis! state "MoveX" 1.0)
      (run-ticks! state instance 60)
      (is (< 58.9 (kami/get-x state 0) 59.1)
          "59 integrated steps after the first main call set the velocity")
      (is (< (Math/abs (kami/get-y state 0)) 1e-6)))))

(deftest kami-ops-are-denied-without-the-capability
  (testing "runtime guard (not just static admission) fails closed: a policy
            without :kami/engine denies the very first host call"
    (let [{:keys [wasm]} (compiled-game)
          state (kami/fresh-state 7)
          no-grant {:kotoba.policy/capabilities #{}}
          instance (wasm-exec/instantiate (:kotoba.wasm/binary wasm)
                                          (kami/kami-host-functions state no-grant)
                                          no-grant)]
      (kami/step! state)
      (is (thrown-with-msg? clojure.lang.ExceptionInfo
                            #"denied by capability guard"
                            (wasm-exec/call-main instance)))
      (is (zero? @(:next-id state))
          "nothing was spawned before the denial"))))
