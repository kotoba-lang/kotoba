(ns inga.quorum-kotoba-test
  "The quorum thresholds have a Kotoba implementation, and the two must not
  diverge.

  Same arrangement `inga.fuel-kotoba-test` uses and for the same reason,
  applied to the other number a replica cannot be alone in believing:
  `kotoba/quorum.kotoba` is compiled to `kotoba/quorum.wasm` by
  `kotoba compile --target wasm32` and checked in, and this suite instantiates
  that binary and compares it against the live `inga.consensus` /
  `inga.quorum` / `inga.stake` functions over a matrix.

  ## Why a second implementation is worth having for THIS rule

  A disagreement about a metering budget stops two replicas at different ops.
  A disagreement about a THRESHOLD is worse in kind: a replica that computes a
  smaller quorum than its peers forms a certificate the rest of the network
  will not accept, and one that computes a larger one refuses certificates
  that are valid. At n = 6 the difference between the safe rule and the
  familiar 2f+1 shortcut is 4 versus 3, and 3 admits two DISJOINT quorums —
  which is two conflicting certificates at one height, the exact outcome
  `inga.consensus`'s docstring claims cannot happen.

  So the Kotoba module is the REFERENCE for these numbers, the cljc is the
  implementation, and this test is the thing that keeps them honest.

  ## What this suite does NOT check, because it did not cross

  Counting distinct witnesses, summing bonds, attaching a `::profile` to a
  closure, and `->predicate`'s dispatch on the runtime type of its argument
  all stay in the cljc — they are folds and dispatches, not decisions. The
  seam is visible in `stake-agrees` below: `inga.stake/total-stake` (host)
  produces the two sums, and the guest decides. That is the division being
  tested, not worked around.

  ## Why cljs only

  Node has WebAssembly built in; the JVM does not. `inga.fuel-kotoba-test`'s
  docstring makes the full argument, and cljs is the runtime this stack
  deploys on."
  (:require [cljs.test :refer [deftest is async testing]]
            [inga.consensus :as c]
            [inga.quorum :as q]
            [inga.stake :as stake]))

(def ^:private fs (js/require "node:fs"))
(def ^:private wasm-path "kotoba/quorum.wasm")
(def ^:private wasm-bytes (delay (.readFileSync fs wasm-path)))

(defn- instantiate
  "A FRESH instance. See `inga.fuel-kotoba-test`: a compiled module carries its
  own fuel budget and traps when it runs out, so reusing one instance across a
  matrix would measure call count instead of arithmetic."
  []
  (-> (js/WebAssembly.instantiate @wasm-bytes #js {})
      (.then #(.-exports (.-instance %)))))

(defn- with-module [f] (.then (instantiate) f))

(defn- call
  "Call export `nm` with i64 args, as a JS Number. `aget` rather than `.-nm`
  because every export here has a dash in its name."
  [exports nm & args]
  (js/Number (apply (aget exports nm) (map js/BigInt args))))

(defn- each-case
  "Run `f` against a fresh instance per case, then `done`. Mirrors the shape
  `inga.fuel-kotoba-test` uses for its matrix.

  Each case is guarded individually rather than letting one rejection collapse
  the whole `Promise.all`: a throw inside a `.then` is reported by `cljs.test`
  against whichever test is CURRENT, not the one that threw, so a single bad
  case otherwise shows up as a failure in an unrelated deftest further down.
  Measured while writing this suite — it cost a wrong diagnosis once."
  [cases f done]
  (-> (js/Promise.all
       (clj->js (map (fn [cs]
                       (with-module
                         (fn [e]
                           (try (f e cs)
                                (catch :default err
                                  (is false (str "threw on " (pr-str cs) ": " err)))))))
                     cases)))
      (.then (fn [_] (done)))))

;; ── the set sizes that matter ───────────────────────────────────────────────
;;
;; n = 3f+1 exactly (4, 7, 10, 13, 16), one below each (3, 6, 9, 12, 15), one
;; above (5, 8, 11), f = 0 (1, 2, 3), and the degenerate 0. Off the 3f+1 grid
;; is where 2f+1 stops being safe, so a matrix that only walks the grid would
;; agree with a rule that is wrong everywhere else.
(def ^:private set-sizes
  [0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 20 31 100 1000])

(deftest kotoba-and-cljc-agree-on-every-threshold-derived-from-n
  (async done
    (each-case
     set-sizes
     (fn [e n]
       (is (= (c/byzantine-tolerance n) (call e "byzantine-tolerance" n))
           (str "byzantine-tolerance n=" n))
       (is (= (c/quorum-size n) (call e "quorum-size" n))
           (str "quorum-size n=" n))
       (is (= (q/one-honest n) (call e "one-honest" n))
           (str "one-honest n=" n)))
     done)))

(deftest the-safe-quorum-is-not-two-f-plus-one-off-the-grid
  (testing "n=6 is the case that makes this rule worth a second implementation:
            2f+1 would be 3, and two disjoint 3-subsets of 6 are two
            conflicting certificates at one height"
    (async done
      (-> (instantiate)
          (.then (fn [e]
                   (is (= 4 (call e "quorum-size" 6)))
                   (is (= 4 (c/quorum-size 6)) "and the cljc says so too")
                   (is (= 3 (+ (* 2 (c/byzantine-tolerance 6)) 1))
                       "while 2f+1 on the same n is 3 -- the number NOT used")
                   (is (= 4 (call e "quorum-size" 5)))
                   (is (= 3 (call e "quorum-size" 4)) "on the 3f+1 grid the two agree")
                   (done)))))))

(deftest a-degenerate-set-size-agrees-rather-than-being-avoided
  (testing "n=0 is reachable from `(count witnesses)` on an empty set, and the
            cljc's answer there is 1 -- see the note in kotoba/quorum.kotoba.
            Whatever it is, both implementations must say the same thing."
    (async done
      (-> (instantiate)
          (.then (fn [e]
                   (is (= (c/quorum-size 0) (call e "quorum-size" 0)))
                   (is (= 1 (c/quorum-size 0))
                       "recorded, not endorsed: zero witnesses yield a quorum of one")
                   (is (= (c/byzantine-tolerance 0) (call e "byzantine-tolerance" 0)))
                   (is (= 0 (call e "byzantine-tolerance" 0))
                       "`quot` truncates toward zero on both sides, so (quot -1 3) is 0")
                   (done)))))))

;; ── head count ──────────────────────────────────────────────────────────────

(defn- witnesses-of-size [k] (set (range k)))

(deftest kotoba-and-cljc-agree-on-at-least
  (testing "the body of the closure `inga.quorum/at-least` returns"
    (async done
      (each-case
       (for [threshold [0 1 2 3 4 7] votes [0 1 2 3 4 7 8]] [threshold votes])
       (fn [e [threshold votes]]
         (is (= (boolean ((q/at-least threshold) (witnesses-of-size votes)))
                (= 1 (call e "at-least-met" votes threshold)))
             (str "at-least threshold=" threshold " votes=" votes)))
       done))))

(deftest kotoba-and-cljc-agree-on-for-set-size
  (testing "`at-least` takes a THRESHOLD and `for-set-size` takes n; the two
            differ by three votes versus four on the same numeral, which is
            why they are named apart in the cljc"
    (async done
      (each-case
       (for [n set-sizes votes [0 1 2 3 4 5 6 7 8 20 100 1000]] [n votes])
       (fn [e [n votes]]
         (is (= (boolean ((q/for-set-size n) (witnesses-of-size votes)))
                (= 1 (call e "for-set-size-met" votes n)))
             (str "for-set-size n=" n " votes=" votes)))
       done))))

(deftest the-two-head-count-entry-points-differ-on-the-same-numeral
  (async done
    (-> (instantiate)
        (.then (fn [e]
                 (is (= 1 (call e "at-least-met" 4 4)) "at-least 4 needs four")
                 (is (= 0 (call e "at-least-met" 3 4)))
                 (is (= 1 (call e "for-set-size-met" 3 4)) "for-set-size 4 needs three")
                 (done))))))

;; ── stake weight ────────────────────────────────────────────────────────────
;;
;; The fold stays host-side by design, so the fixtures are real bond maps and
;; `inga.stake/total-stake` produces the sums the guest decides on. `sybils`
;; is the case the whole stake-weighted rule exists for: forty identities
;; splitting forty units of a sixteen-thousand-unit total.

(def ^:private honest-bonds
  {"big-1" {:amount 4000} "big-2" {:amount 4000}
   "big-3" {:amount 4000} "big-4" {:amount 4000}})
(def ^:private sybil-bonds
  (into {} (map (fn [i] [(str "sybil-" i) {:amount 1}])) (range 40)))
(def ^:private bonds (merge honest-bonds sybil-bonds))
(def ^:private witness-set (set (keys bonds)))
(def ^:private sybils (set (keys sybil-bonds)))

(def ^:private stake-cases
  "[voted witnesses bonds] triples, chosen for the boundaries rather than the
  happy path. `thirds` is exactly two thirds, which must NOT be a quorum --
  strictly-greater is what makes two quorums share more than a third."
  (let [thirds {"a" {:amount 1} "b" {:amount 1} "c" {:amount 1}}]
    [[#{"big-1"} witness-set bonds]
     [#{"big-1" "big-2"} witness-set bonds]
     [#{"big-1" "big-2" "big-3"} witness-set bonds]
     [#{"big-1" "big-2" "big-3" "big-4"} witness-set bonds]
     [sybils witness-set bonds]
     [(into #{"big-1" "big-2"} sybils) witness-set bonds]
     [(into #{"big-1" "big-2" "big-3"} sybils) witness-set bonds]
     [#{} witness-set bonds]
     [#{"a" "b"} #{"a" "b" "c"} thirds]
     [#{"a" "b" "c"} #{"a" "b" "c"} thirds]
     [#{"a"} #{"a" "b" "c"} thirds]
     ;; nobody bonded: total stake is zero, and the stake rule must say no
     ;; rather than divide by nothing
     [#{"a" "b"} #{"a" "b" "c"} {}]
     [#{"a" "b" "c"} #{"a" "b" "c"} {}]
     ;; one holder with everything
     [#{"a"} #{"a" "b"} {"a" {:amount 10}}]
     [#{"b"} #{"a" "b"} {"a" {:amount 10}}]]))

(deftest kotoba-and-cljc-agree-on-stake-weighted-quorum
  (async done
    (each-case
     stake-cases
     (fn [e [voted ws bs]]
       (let [total (stake/total-stake bs ws)
             voted-stake (stake/total-stake bs (filter (set voted) ws))
             label (str " voted-stake=" voted-stake " total=" total)]
         (is (= (boolean (stake/stake-quorum-met? voted bs ws))
                (= 1 (call e "stake-met" voted-stake total)))
             (str "stake-quorum-met?" label))))
     done)))

(deftest exactly-two-thirds-is-not-a-quorum-in-either
  (testing "strictly greater, not at least -- an off-by-one here is the
            difference between two quorums that must intersect and two that
            merely might"
    (async done
      (-> (instantiate)
          (.then (fn [e]
                   (is (= 0 (call e "stake-met" 2 3)) "2 of 3 is exactly two thirds")
                   (is (= 1 (call e "stake-met" 3 3)))
                   (is (= 0 (call e "stake-met" 200 300)))
                   (is (= 1 (call e "stake-met" 201 300)))
                   (is (= 0 (call e "stake-met" 0 0)) "and no stake is no quorum")
                   (is (= 0 (call e "counted-unbonded-met" 2 3)))
                   (is (= 1 (call e "counted-unbonded-met" 3 3)))
                   (is (= 0 (call e "counted-unbonded-met" 0 0)))
                   (done)))))))

;; NOT FIXED HERE, recorded: `inga.stake/quorum-met?` THROWS when `witnesses`
;; is a set. It calls `(distinct witnesses)`, and `clojure.core/distinct`
;; destructures its argument with `[f :as xs]` before calling `seq` on it, so
;; the destructuring does `nth` on the set:
;;
;;     (distinct #{1 2 3})  =>  nth not supported on this type: PersistentHashSet
;;
;; Measured on Clojure 1.12.5 and reproduced under cljs. Its sibling
;; `stake-quorum-met?` takes the same argument and does NOT throw (it uses
;; `map`/`filter`, never `distinct`), and `inga.quorum/stake-weighted` hands a
;; set — `witness-set` — straight through. So the two quorum entry points in
;; `inga.stake` disagree about what a witness collection may be, and the one
;; that refuses a set is the one that reports the security basis. Nothing in
;; the existing suite calls `quorum-met?` with a set, which is why it has not
;; surfaced. Out of scope for this port; the roster is passed as a vector below
;; so that this suite tests the arithmetic rather than that bug.
(def ^:private roster-cases
  (mapv (fn [[voted ws bs]] [voted (vec ws) bs]) stake-cases))

(deftest kotoba-and-cljc-agree-on-the-composite-and-on-which-basis-is-in-force
  (testing "`inga.stake/quorum-met?` returns the security basis in-band
            precisely so a caller cannot read :met? true and believe it got
            Byzantine security when nobody has bonded anything -- so WHICH
            branch was taken is itself a decision replicas must share"
    (async done
      (each-case
       roster-cases
       (fn [e [voted ws bs]]
         (let [roster (distinct ws)
               total (stake/total-stake bs roster)
               voted-stake (stake/total-stake bs (filter (set voted) roster))
               n (count roster)
               n-voted (count (filter (set voted) roster))
               actual (stake/quorum-met? voted bs ws)
               label (str " voted-stake=" voted-stake " total=" total
                          " n-voted=" n-voted " n=" n)]
           (is (= (boolean (:met? actual))
                  (= 1 (call e "quorum-met" voted-stake total n-voted n)))
               (str "quorum-met?" label))
           (is (= (if (= :stake-weighted (:basis actual)) 1 0)
                  (call e "stake-basis" total))
               (str "basis" label))))
       done))))

(deftest the-unbonded-fallback-is-a-head-count-and-both-say-so
  (testing "a liveness arrangement over an enumerated roster, not BFT -- ported
            because replicas must agree on it, not because it is a good rule"
    (async done
      (-> (instantiate)
          (.then (fn [e]
                   (let [ws ["a" "b" "c"]   ; vector: see the note above roster-cases
                         r (stake/quorum-met? #{"a" "b" "c"} {} ws)]
                     (is (= :counted-unbonded (:basis r)))
                     (is (= 0 (call e "stake-basis" 0)))
                     (is (= (boolean (:met? r))
                            (= 1 (call e "counted-unbonded-met" 3 3)))))
                   (done)))))))
