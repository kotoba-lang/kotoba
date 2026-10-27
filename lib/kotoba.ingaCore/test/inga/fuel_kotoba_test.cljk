(ns inga.fuel-kotoba-test
  "F2, second half: the metering arithmetic has a Kotoba implementation, and
  the two must not diverge.

  `kotoba/fuel.kotoba` is compiled to `kotoba/fuel.wasm` by
  `kotoba compile --target wasm32` and checked in, the same way
  `gftdcojp/engi` checks in `engi_settlement.wasm`. This suite instantiates
  that binary and compares it against `inga.fuel` over a matrix.

  ## Why a second implementation is worth having here and almost nowhere else

  Normally two implementations of one rule is the failure mode, not the
  safeguard — `inga.power`'s simplified quorum copies were deleted for exactly
  that reason. The difference is what a disagreement COSTS. A divergence in
  metering does not produce a wrong number that someone notices; it produces
  two replicas that stopped at different ops, committed different state, and
  each believe they are correct. Filecoin's FVM meters in the VM for the same
  reason: determinism you can argue for is worth less than determinism the
  execution substrate enforces.

  So the Kotoba module is the REFERENCE for this one decision, the cljc is the
  implementation, and this test is the thing that keeps them honest. If they
  ever disagree, the Kotoba answer is the correct one.

  ## The compiler's fuel is NOT inga's fuel, and finding that out cost a trap

  A compiled Kotoba module carries its OWN fuel budget per instance and traps
  with `unreachable` when it runs out. Measured here: 42 successful calls of
  `applied(10,1,100)` on one instance, then a trap on every call after. That is
  the compiler doing its job — it is a safety ceiling on a guest.

  It is also exactly the failure `inga.fuel`'s docstring exists to forbid:
  **a replica that throws has left the protocol.** So the two are complementary
  and must not be confused:

    inga.fuel        deterministic, committed accounting. Exhaustion is a VALUE
                     that lands in the state root, so peers can check it.
    compiler fuel    a host-side ceiling. Exhaustion is a TRAP.

  Consequence for any deployment that runs the machine as a Kotoba module:
  every replica must be given the SAME initial fuel (the CLI exposes
  `--fuel` / `--fuel-initial`), or replicas trap at different call counts and
  diverge for a reason that has nothing to do with the transactions. These
  tests therefore instantiate fresh per call — not to dodge the limit, but
  because the thing under test is the ARITHMETIC, and a depleting instance
  would make the matrix measure call count instead.

  ## Why cljs only

  Node has WebAssembly built in. The JVM does not, and reaching for Chicory to
  run 349 bytes of arithmetic would add a dependency heavier than the thing it
  checks. cljs is also the runtime this stack deploys on, so verifying there
  is verifying where it matters."
  (:require [cljs.test :refer [deftest is async testing]]
            [inga.fuel :as fuel]))

(def ^:private fs (js/require "node:fs"))
(def ^:private wasm-path "kotoba/fuel.wasm")

(def ^:private wasm-bytes (delay (.readFileSync fs wasm-path)))

(defn- instantiate
  "A FRESH instance. See the ns docstring: a compiled module's own fuel
  depletes across calls and then traps, so reusing one instance would turn a
  matrix over arithmetic into a measurement of how many calls fit."
  []
  (-> (js/WebAssembly.instantiate @wasm-bytes #js {})
      (.then #(.-exports (.-instance %)))))

(defn- with-module
  "Run `f` against a fresh instance, returning a Promise of its result."
  [f]
  (.then (instantiate) f))

(defn- cljc-applied
  "What `inga.fuel/apply-metered` does with `n` identical ops at `cost`."
  [n cost budget]
  (:applied (fuel/apply-metered {:state nil
                                 :ops (repeat n {:op :x})
                                 :budget budget
                                 :cost-fn (fuel/fixed-cost cost)
                                 :step (fn [s _] s)})))

(defn- cljc-spent [n cost budget]
  (:spent (fuel/apply-metered {:state nil
                               :ops (repeat n {:op :x})
                               :budget budget
                               :cost-fn (fuel/fixed-cost cost)
                               :step (fn [s _] s)})))

(deftest kotoba-and-cljc-agree-on-where-metering-stops
  (async done
    (let [cases (for [n [0 1 3 10 25] cost [1 2 3 7] budget [0 1 2 7 20 100]]
                  [n cost budget])]
      (-> (js/Promise.all
           (clj->js
            (map (fn [[n cost budget]]
                   (with-module
                     (fn [e]
                       #js {:n n :cost cost :budget budget
                            :applied (js/Number (.applied e (js/BigInt n) (js/BigInt cost)
                                                          (js/BigInt budget)))
                            :spent (js/Number (.spent e (js/BigInt n) (js/BigInt cost)
                                                       (js/BigInt budget)))})))
                 cases)))
          (.then (fn [results]
                   (doseq [r results]
                     (let [n (.-n r) cost (.-cost r) budget (.-budget r)
                           label (str " n=" n " cost=" cost " budget=" budget)]
                       (is (= (cljc-applied n cost budget) (.-applied r)) (str "applied" label))
                       (is (= (cljc-spent n cost budget) (.-spent r)) (str "spent" label))))
                   (done)))))))

(deftest a-module-instance-runs-out-of-its-own-fuel-and-traps
  (testing "the compiler's ceiling is real and is a TRAP, which is why inga's
            own metering exists as a value in the state instead"
    (async done
      (-> (instantiate)
          (.then (fn [e]
                   (let [outcome (loop [i 0]
                                   (if (>= i 500)
                                     :never-trapped
                                     (let [ok? (try (.applied e (js/BigInt 10) (js/BigInt 1)
                                                              (js/BigInt 100))
                                                    true
                                                    (catch :default _ false))]
                                       (if ok? (recur (inc i)) i))))]
                     (is (not= :never-trapped outcome)
                         "a single instance does deplete -- if this ever stops being
                          true, the note in this ns docstring is stale")
                     (is (pos? outcome) "and it serves some calls before it does"))
                   (done)))))))

(deftest the-boundary-case-fits-in-both
  (testing "spent + cost exactly equal to budget must be APPLIED -- charging
            before the op is what makes the budget a real ceiling, and an
            off-by-one here is a fork"
    (async done
      (-> (instantiate)
          (.then (fn [e]
                   (is (= 1 (js/Number (.fits e (js/BigInt 5) (js/BigInt 2) (js/BigInt 7)))))
                   (is (= 0 (js/Number (.fits e (js/BigInt 6) (js/BigInt 2) (js/BigInt 7)))))
                   (is (= 4 (cljc-applied 10 2 8)) "cljc agrees: 4 ops of 2 fit in 8")
                   (is (= 4 (js/Number (.applied e (js/BigInt 10) (js/BigInt 2) (js/BigInt 8)))))
                   (done)))))))

(deftest a-zero-budget-applies-nothing-in-both
  (async done
    (-> (instantiate)
        (.then (fn [e]
                 (is (= 0 (cljc-applied 5 1 0)))
                 (is (= 0 (js/Number (.applied e (js/BigInt 5) (js/BigInt 1) (js/BigInt 0)))))
                 (done))))))

(deftest a-zero-cost-op-still-terminates-in-both
  (testing "free ops are a hole metering is supposed to close, but if a caller
            supplies cost 0 the loop must still end at n rather than spin"
    (async done
      (-> (instantiate)
          (.then (fn [e]
                   (is (= 5 (cljc-applied 5 0 3)))
                   (is (= 5 (js/Number (.applied e (js/BigInt 5) (js/BigInt 0) (js/BigInt 3)))))
                   (done)))))))
