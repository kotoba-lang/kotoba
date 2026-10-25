(ns kotobase.server.trampoline-test
  "kotobase.server.trampoline tests -- ClojureScript only (js/Promise-based,
  no JVM path, matching the source's own unconditional cljs syntax)."
  (:require [cljs.test :refer-macros [deftest is testing async]]
            [kotobase.server.trampoline :as tr]))

(deftest block-miss?-distinguishes-the-trampoline-signal-from-other-errors
  (is (true? (tr/block-miss? (tr/missing-block "bafyreiX"))))
  (is (false? (tr/block-miss? (ex-info "boom" {}))))
  (is (false? (tr/block-miss? (js/Error. "plain js error")))))

(deftest with-blocks-resolves-immediately-when-f-never-misses
  (async done
    (let [fetch-calls (atom 0)
          fetch1 (fn [_cid] (swap! fetch-calls inc) (js/Promise.resolve #js []))]
      (-> (tr/with-blocks fetch1 (fn [_sync-get] 42))
          (.then (fn [v]
                   (is (= 42 v))
                   (is (= 0 @fetch-calls) "f never called sync-get, so fetch1 never runs")
                   (done)))
          (.catch (fn [e] (is false (str "unexpected: " e)) (done)))))))

(deftest with-blocks-fetches-a-missing-block-and-retries-from-scratch
  (async done
    (let [fetch-calls (atom [])
          bytes-for {"a" #js [1 2 3]}
          fetch1 (fn [cid] (swap! fetch-calls conj cid) (js/Promise.resolve (get bytes-for cid)))]
      (-> (tr/with-blocks fetch1 (fn [sync-get] (.-length (sync-get "a"))))
          (.then (fn [v]
                   (is (= 3 v) "f re-ran after the miss and read the now-cached block")
                   (is (= ["a"] @fetch-calls) "fetch1 called exactly once for the one cid f needed")
                   (done)))
          (.catch (fn [e] (is false (str "unexpected: " e)) (done)))))))

(deftest with-blocks-handles-multiple-sequential-misses-without-refetching-cached-blocks
  (async done
    (let [fetch-calls (atom [])
          bytes-for {"a" #js [1] "b" #js [2 2]}
          fetch1 (fn [cid] (swap! fetch-calls conj cid) (js/Promise.resolve (get bytes-for cid)))
          f (fn [sync-get] (+ (.-length (sync-get "a")) (.-length (sync-get "b"))))]
      (-> (tr/with-blocks fetch1 f)
          (.then (fn [v]
                   (is (= 3 v))
                   (is (= ["a" "b"] @fetch-calls)
                       "each distinct cid fetched exactly once, in miss order -- \"a\" is never refetched once cached")
                   (done)))
          (.catch (fn [e] (is false (str "unexpected: " e)) (done)))))))

(deftest with-blocks-trampolines-a-miss-thrown-inside-an-async-continuation
  (async done
    ;; Mirrors kotobase-peer's own crypto seam being Promise-returning on
    ;; cljs (ADR-2607051000): sync-get called inside a `.then`, so the miss
    ;; surfaces as a promise REJECTION, not a sync throw -- with-blocks'
    ;; docstring calls this out explicitly as a case it must also handle.
    (let [fetch-calls (atom 0)
          fetch1 (fn [_cid] (swap! fetch-calls inc) (js/Promise.resolve #js [9 9]))
          f (fn [sync-get]
              (-> (js/Promise.resolve nil)
                  (.then (fn [_] (.-length (sync-get "x"))))))]
      (-> (tr/with-blocks fetch1 f)
          (.then (fn [v]
                   (is (= 2 v))
                   (is (= 1 @fetch-calls))
                   (done)))
          (.catch (fn [e] (is false (str "unexpected: " e)) (done)))))))

(deftest with-blocks-propagates-a-non-miss-failure-without-retrying
  (async done
    (let [fetch-calls (atom 0)
          fetch1 (fn [_cid] (swap! fetch-calls inc) (js/Promise.resolve #js []))
          boom (js/Error. "not a block miss")]
      (-> (tr/with-blocks fetch1 (fn [_sync-get] (throw boom)))
          (.then (fn [_] (is false "should have rejected") (done)))
          (.catch (fn [e]
                    (is (= boom e) "the original error propagates unchanged")
                    (is (= 0 @fetch-calls) "no retry attempted for a non-miss failure")
                    (done)))))))

(deftest a-wrapped-signal-is-still-a-signal
  ;; nbb/SCI wraps a throw that crosses an async continuation: the outer error
  ;; carries `{:type :sci/error ...}` and the original sits under `:cause`.
  ;; That runtime is the only one that produces the shape, so without this
  ;; test the shadow-cljs and JVM runs stay green while the unwrapping is
  ;; removed -- and the failure it causes is silent (a retryable miss stops
  ;; being retried, a denial degrades to a generic error). Build the shape by
  ;; hand so every runtime checks it.
  (let [inner   (tr/missing-block "cid-x")
        wrapped (ex-info "block-miss" {:type :sci/error :line 77} inner)]
    (is (= {:block-miss true :cid "cid-x"} (tr/miss-data inner))
        "unwrapped: unchanged behaviour")
    (is (= {:block-miss true :cid "cid-x"} (tr/miss-data wrapped))
        "wrapped: the payload is one link down, not in the outermost ex-data")
    (is (tr/block-miss? wrapped))
    (is (nil? (tr/miss-data (ex-info "unrelated" {:type :sci/error}))))
    (is (false? (tr/block-miss? (ex-info "unrelated" {}))))))

(deftest the-cause-chain-is-bounded-and-ordered
  ;; A classifier reads this chain per failed request; an unbounded walk would
  ;; make a deep (or self-referential) cause a hang rather than an error.
  (let [deep (reduce (fn [e i] (ex-info (str "w" i) {:depth i} e))
                     (ex-info "root" {:root true})
                     (range 40))]
    (is (= 9 (count (tr/ex-data-chain deep))) "bounded")
    (is (= 39 (:depth (first (tr/ex-data-chain deep)))) "outermost first")
    (is (nil? (tr/miss-data deep)) "a root buried past the bound is not found")
    (is (= [{:root true}] (tr/ex-data-chain (ex-info "root" {:root true})))
        "one link on the JVM and under shadow-cljs")))

;; ── seeded cache (3-arity) ───────────────────────────────────────────────────
;; The observable that matters is HOW MANY TIMES `f` RAN, not whether the answer
;; is right. `f` is re-run from scratch per miss, so K uncached blocks cost K+1
;; runs of the whole handler -- that quadratic is the term that put reads at
;; 20-25 CPU-seconds in production, and a caller-side block cache cannot touch
;; it because the cache in here is private and starts empty.

(defn- counting-fetch
  "fetch1 over `bytes-for`, recording every cid it is asked for."
  [calls bytes-for]
  (fn [cid] (swap! calls conj cid) (js/Promise.resolve (get bytes-for cid))))

(def ^:private four-blocks {"a" #js [1] "b" #js [2] "c" #js [3] "d" #js [4]})

(defn- read-four [runs]
  (fn [sync-get]
    (swap! runs inc)
    (reduce + (map #(.-length (sync-get %)) ["a" "b" "c" "d"]))))

(deftest unseeded-reruns-f-once-per-miss
  (testing "the cost being removed, pinned first so the seeded case has
            something to be measured against"
    (async done
      (let [calls (atom []) runs (atom 0)]
        (-> (tr/with-blocks (counting-fetch calls four-blocks) (read-four runs))
            (.then (fn [v]
                     (is (= 4 v))
                     (is (= ["a" "b" "c" "d"] @calls))
                     (is (= 5 @runs) "K=4 misses re-run the whole handler K+1 times")
                     (done)))
            (.catch (fn [e] (is false (str "unexpected: " e)) (done))))))))

(deftest a-fully-seeded-cache-runs-f-once-and-fetches-nothing
  (testing "the guarantee: blocks the caller already resolved cost neither a
            fetch nor a re-run"
    (async done
      (let [calls (atom []) runs (atom 0)]
        (-> (tr/with-blocks (counting-fetch calls four-blocks) (read-four runs) four-blocks)
            (.then (fn [v]
                     (is (= 4 v))
                     (is (= [] @calls) "seeded blocks are never fetched again")
                     (is (= 1 @runs) "one run, not five -- this is the O(K^2) term going away")
                     (done)))
            (.catch (fn [e] (is false (str "unexpected: " e)) (done))))))))

(deftest a-partial-seed-only-pays-for-what-it-is-missing
  (testing "a stale or incomplete manifest must degrade, never break: the
            un-seeded blocks trampoline exactly as before"
    (async done
      (let [calls (atom []) runs (atom 0)]
        (-> (tr/with-blocks (counting-fetch calls four-blocks) (read-four runs)
                            {"a" #js [1] "b" #js [2]})
            (.then (fn [v]
                     (is (= 4 v))
                     (is (= ["c" "d"] @calls) "only the un-seeded cids are fetched")
                     (is (= 3 @runs) "2 misses -> 3 runs, down from 5")
                     (done)))
            (.catch (fn [e] (is false (str "unexpected: " e)) (done))))))))

(deftest nil-and-empty-seeds-behave-exactly-like-the-two-arity
  (testing "the compatibility claim in the docstring, asserted rather than
            assumed -- every existing caller passes no seed"
    (async done
      (let [c1 (atom []) r1 (atom 0) c2 (atom []) r2 (atom 0)]
        (-> (js/Promise.all
             #js [(tr/with-blocks (counting-fetch c1 four-blocks) (read-four r1) nil)
                  (tr/with-blocks (counting-fetch c2 four-blocks) (read-four r2) {})])
            (.then (fn [vs]
                     (is (= [4 4] (vec vs)))
                     (is (= ["a" "b" "c" "d"] @c1 @c2))
                     (is (= 5 @r1 @r2) "same K+1 runs the 2-arity produces")
                     (done)))
            (.catch (fn [e] (is false (str "unexpected: " e)) (done))))))))
