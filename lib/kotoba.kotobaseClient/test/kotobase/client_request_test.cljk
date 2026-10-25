(ns kotobase.client-request-test
  "Locks the wire envelope the client sends to kotobase.net: URL, method,
  headers (CACAO / x-kotoba-did), and JSON body for q/datoms/pull/transact.
  A fake fetch captures the request; no network. Complements cacao-test (which
  proves the signature) by pinning the request shape the edge dispatches on."
  (:require [cljs.test :refer-macros [deftest is testing async]]
            [kotoba.lang.text :as str]
            ["@noble/curves/ed25519.js" :refer [ed25519]]
            [kotobase.cid :as cid]
            [kotobase.client :as kc]))

(def seed (js/Uint8Array.from (clj->js (range 32))))
(def op-did (cid/did-key-from-ed25519-pub (.getPublicKey ed25519 seed)))

;; fake fetch returning a canned 200 JSON; records the last (url, opts).
(defn- capturing-fetch [sink]
  (fn [url opts]
    (reset! sink {:url url :opts (or opts #js {})})
    (js/Promise.resolve
     #js {:ok true :status 200
          :text (fn [] (js/Promise.resolve "{\"ok\":true,\"datoms\":[]}"))})))

(defn- body-of [sink]
  (js->clj (js/JSON.parse (or (some-> @sink :opts .-body) "{}"))
           :keywordize-keys true))
(defn- header-of [sink k] (aget (.-headers (:opts @sink)) k))
(defn- url-of [sink] (:url @sink))

(def endpoint "https://kotobase.net")

(deftest transact-request-envelope
  (async done
    (let [sink (atom nil)
          c (kc/make-client {:endpoint endpoint :secret-key seed :operator-did op-did
                             :fetch-fn (capturing-fetch sink)})]
      (-> (kc/transact c "yoro-social" "[{:db/id -1 :yoro.post/uri \"at://x\"}]")
          (.then (fn [_]
                   (let [b (body-of sink)]
                     (is (= (str endpoint "/xrpc/ai.gftd.apps.kotobase.datomic.transact") (url-of sink)))
                     (is (= "POST" (.-method (:opts @sink))))
                     (is (= "yoro-social" (:db_name b)))
                     (is (= "[{:db/id -1 :yoro.post/uri \"at://x\"}]" (:tx_edn b)))
                     (is (string? (:cacao_b64 b)) "write carries a CACAO in the body")
                     (is (str/starts-with? (header-of sink "authorization") "CACAO "))
                     (is (= (:did c) (header-of sink "x-kotoba-did")))
                     (done))))))))

(deftest q-and-pull-request-envelopes
  (async done
    (let [sink (atom nil)
          c (kc/make-client {:endpoint endpoint :did op-did :operator-did op-did
                             :public-reads? true :fetch-fn (capturing-fetch sink)})]
      (-> (kc/q c "yoro-social" "{:find [?u] :where [[?e :yoro.post/uri ?u]]}")
          (.then (fn [_]
                   (let [b (body-of sink)]
                     (is (str/ends-with? (url-of sink) "datomic.q"))
                     (is (= "{:find [?u] :where [[?e :yoro.post/uri ?u]]}" (:query_edn b)))
                     (is (= (cid/canonical-graph op-did "yoro-social") (:graph b))))))
          (.then (fn [_] (kc/pull c "yoro-social" "123" "[:db/id :yoro.post/text]")))
          (.then (fn [_]
                   (let [b (body-of sink)]
                     (is (str/ends-with? (url-of sink) "datomic.pull"))
                     (is (= "123" (:entity b)))
                     (is (= "[:db/id :yoro.post/text]" (:pattern_edn b)))
                     (done))))))))

(deftest transact-requires-write-client
  ;; a public/read-only client (no :secret-key) must refuse to transact.
  (let [c (kc/make-client {:endpoint endpoint :did op-did :operator-did op-did :public-reads? true})]
    (is (thrown? js/Error (kc/transact c "yoro-social" "[]")))))

(deftest promise-istore-adapter-projects-wire-envelopes
  (async done
    (let [calls (atom [])
          responses (atom ["{\"ok\":true,\"val\":{\"x\":1}}"
                           "{\"ok\":true,\"val\":{\"x\":1}}"
                           "{\"ok\":true,\"keys\":[\"k\"]}"
                           "{\"ok\":true,\"event\":{\"x\":2,\"seq\":1}}"
                           "{\"ok\":true,\"events\":[{\"x\":2,\"seq\":1}]}"])
          fetch-fn (fn [url opts]
                     (swap! calls conj {:url url :opts opts})
                     (let [body (first @responses)]
                       (swap! responses subvec 1)
                       (js/Promise.resolve
                        #js {:ok true :status 200
                             :text (fn [] (js/Promise.resolve body))})))
          client (kc/make-client {:endpoint endpoint :secret-key seed
                                  :operator-did op-did :fetch-fn fetch-fn})
          xrpc (kc/store-xrpc client)]
      (-> (xrpc :put {:coll "c" :key "k" :val {:x 1}})
          (.then (fn [value] (is (= {:x 1} value))
                   (xrpc :get {:coll "c" :key "k"})))
          (.then (fn [value] (is (= {:x 1} value))
                   (xrpc :list {:coll "c"})))
          (.then (fn [keys] (is (= ["k"] keys))
                   (xrpc :append {:stream "s" :event {:x 2}})))
          (.then (fn [event] (is (= {:x 2 :seq 1} event))
                   (xrpc :read {:stream "s" :since 0})))
          (.then (fn [events]
                   (is (= [{:x 2 :seq 1}] events))
                   (is (every? #(str/includes? (:url %) "/xrpc/net.kotobase.store.") @calls))
                   (is (every? #(str/starts-with?
                                 (aget (.-headers (:opts %)) "authorization") "CACAO ")
                               @calls))
                   (done)))
          (.catch (fn [error] (is false (str error)) (done)))))))

;; ── transient-5xx retry (kotoba-wasm "Invalid array buffer length" flake) ─────
;; Exercised via `q` (not `datoms`): the PDS test bundle globally stubs
;; kotobase.client/datoms with a canned-result double, which would shadow the
;; real retry path here. `q`/`transact` are un-stubbed and share the same
;; with-retry wrapper, so they pin the behavior faithfully.

(defn- flaky-fetch
  "Fetch that returns HTTP 500 for the first `fail-n` calls, then 200. `calls`
  counts total invocations."
  [calls fail-n body-json]
  (fn [_url _opts]
    (let [n (swap! calls inc)]
      (if (<= n fail-n)
        (js/Promise.resolve
         #js {:ok false :status 500
              :text (fn [] (js/Promise.resolve "{\"ok\":false,\"error\":\"Invalid array buffer length\"}"))})
        (js/Promise.resolve
         #js {:ok true :status 200 :text (fn [] (js/Promise.resolve body-json))})))))

(defn- read-client [fetch-fn]
  (kc/make-client {:endpoint endpoint :did op-did :operator-did op-did
                   :public-reads? true :fetch-fn fetch-fn}))

(deftest read-retries-transient-5xx
  (async done
    (let [calls (atom 0)
          c (read-client (flaky-fetch calls 2 "{\"rows_edn\":[[\"x\"]]}"))]
      ;; 2 transient 500s then success — within the 3-attempt budget.
      (-> (kc/q c "yoro-social" "{:find [?u]}")
          (.then (fn [^js resp]
                   (is (= 3 @calls) "retried 2× then succeeded on the 3rd call")
                   (is (= 1 (.-length (.-rows_edn resp))) "returns the eventual success body")
                   (done)))
          (.catch (fn [e] (is false (str "should have retried through the flake: " e)) (done)))))))

(deftest read-gives-up-after-max-retries
  (async done
    (let [calls (atom 0)
          c (read-client (flaky-fetch calls 99 ""))]     ; always 500
      (-> (kc/q c "yoro-social" "{:find [?u]}")
          (.then (fn [_] (is false "a persistent 500 must eventually reject") (done)))
          (.catch (fn [^js e]
                    (is (= 500 (.-status e)) "surfaces the 5xx after exhausting retries")
                    (is (<= @calls 4) "bounded retry budget (≤4 attempts)")
                    (done)))))))

(deftest read-does-not-retry-404
  (async done
    ;; 404 = empty graph (never written) → empty result, NOT a retry storm.
    (let [calls (atom 0)
          c (read-client (fn [_ _]
                           (swap! calls inc)
                           (js/Promise.resolve
                            #js {:ok false :status 404
                                 :text (fn [] (js/Promise.resolve "not found"))})))]
      (-> (kc/q c "yoro-social" "{:find [?u]}")
          (.then (fn [^js resp]
                   (is (= 1 @calls) "404 is not retried")
                   (is (= 0 (.-length (.-rows_edn resp))) "404 → empty rows")
                   (done)))
          (.catch (fn [e] (is false (str "404 should map to empty, not reject: " e)) (done)))))))

(deftest transact-rejects-on-2xx-body-ok-false
  ;; The bug this locks: a kotobase XRPC handler can report a LOGICAL failure
  ;; (e.g. run-transact's ConcurrentWriteConflict after exhausting its head-CAS
  ;; retries) over an ordinary HTTP 200 — the request itself was handled fine.
  ;; A caller checking only res.ok/HTTP status sees success; confirmed live
  ;; 2026-07-03, a masked failure like this let aozora.pds.repo/create-record
  ;; report a fabricated uri/cid to its OWN caller while the write had
  ;; actually failed and said so in its own body.
  (async done
    (let [calls (atom 0)
          c (kc/make-client
             {:endpoint endpoint :secret-key seed :operator-did op-did
              :fetch-fn (fn [_url _opts]
                          (swap! calls inc)
                          (js/Promise.resolve
                           #js {:ok true :status 200
                                :text (fn [] (js/Promise.resolve
                                             "{\"ok\":false,\"error\":\"ConcurrentWriteConflict\",\"message\":\"head CAS lost the race 8 times\"}"))}))})]
      (-> (kc/transact c "yoro-social" "[{:db/id \"k/1\" :a 1}]")
          (.then (fn [_] (is false "a 200 with body ok:false must reject, not resolve") (done)))
          (.catch (fn [^js e]
                    (is (= 1 @calls))
                    (is (= 200 (.-status e)) "HTTP status the request actually got")
                    (is (str/includes? (.-message e) "ConcurrentWriteConflict"))
                    (is (str/includes? (.-message e) "head CAS lost the race 8 times"))
                    (is (false? (.-ok (.-body e))) "the parsed body is attached for callers that want it")
                    (done)))))))

(deftest datoms-with-ok-true-body-resolves-normally
  ;; Sanity: the fix must not reject a perfectly normal ok:true response.
  (async done
    (let [c (kc/make-client {:endpoint endpoint :did op-did :operator-did op-did
                             :public-reads? true
                             :fetch-fn (fn [_ _]
                                         (js/Promise.resolve
                                          #js {:ok true :status 200
                                               :text (fn [] (js/Promise.resolve "{\"ok\":true,\"datoms\":[]}"))}))})]
      (-> (kc/datoms c "yoro-social" ":eavt")
          (.then (fn [^js resp] (is (= 0 (.-length (.-datoms resp)))) (done)))
          (.catch (fn [e] (is false (str "ok:true must resolve: " e)) (done)))))))

(deftest public-datoms-selects-only-the-exact-graph
  (async done
    (let [sink (atom nil)
          c (kc/make-client {:endpoint endpoint :did op-did :operator-did op-did
                             :public-reads? true :fetch-fn (capturing-fetch sink)})]
      (-> (kc/datoms c "relay-bsky" ":eavt")
          (.then (fn [_]
                   (let [b (body-of sink)]
                     (is (= (cid/canonical-graph op-did "relay-bsky") (:graph b)))
                     (is (nil? (:db_name b))
                         "anonymous reads cannot name a tenant database")
                     (is (nil? (header-of sink "authorization")))
                     (done))))
          (.catch (fn [e] (is false (str "public datoms rejected: " e)) (done)))))))

;; ── fold (D1 maintenance op, ADR-2607032430) ──────────────────────────────────
;; No prior coverage at all — transact/q/pull/datoms are covered above, fold
;; never was.

(deftest fold-request-envelope
  (async done
    (let [sink (atom nil)
          c (kc/make-client {:endpoint endpoint :secret-key seed :operator-did op-did
                             :fetch-fn (capturing-fetch sink)})]
      (-> (kc/fold c "yoro-social")
          (.then (fn [_]
                   (let [b (body-of sink)]
                     (is (str/ends-with? (url-of sink) "datomic.fold"))
                     (is (= "POST" (.-method (:opts @sink))))
                     (is (= (cid/canonical-graph op-did "yoro-social") (:graph b))
                         "fold names the graph directly, unlike transact's server-derived graph")
                     (is (nil? (:db_name b)) "fold's body carries :graph only, no :db_name")
                     (is (string? (:cacao_b64 b)) "fold is head-mutating, so it carries a CACAO like transact")
                     (is (str/starts-with? (header-of sink "authorization") "CACAO "))
                     (is (= (:did c) (header-of sink "x-kotoba-did")))
                     (done))))))))

(deftest fold-requires-write-client
  ;; a public/read-only client (no :secret-key) must refuse to fold, same as transact.
  (let [c (kc/make-client {:endpoint endpoint :did op-did :operator-did op-did :public-reads? true})]
    (is (thrown? js/Error (kc/fold c "yoro-social")))))

(deftest fold-max-novelty-request-envelope
  ;; gftdcojp/app-aozora#78 / kotobase-peer#16: an ops/cron caller passes
  ;; :max-novelty to bound the fold, threaded through as body :max_novelty.
  (async done
    (let [sink (atom nil)
          c (kc/make-client {:endpoint endpoint :secret-key seed :operator-did op-did
                             :fetch-fn (capturing-fetch sink)})]
      (-> (kc/fold c "yoro-social" {:max-novelty 50})
          (.then (fn [_]
                   (let [b (body-of sink)]
                     (is (= 50 (:max_novelty b))
                         "max-novelty threads through as :max_novelty in the POST body"))
                   (done)))))))

(deftest fold-without-max-novelty-omits-it-from-the-body
  ;; unbounded (the default) must not send a :max_novelty key at all --
  ;; the worker's do-fold treats a missing/nil value as unbounded.
  (async done
    (let [sink (atom nil)
          c (kc/make-client {:endpoint endpoint :secret-key seed :operator-did op-did
                             :fetch-fn (capturing-fetch sink)})]
      (-> (kc/fold c "yoro-social")
          (.then (fn [_]
                   (is (not (contains? (body-of sink) :max_novelty)))
                   (done)))))))

(deftest fold-rejects-on-2xx-body-ok-false
  ;; fold shares `post`'s ok:false handling — pins that a logical failure
  ;; (e.g. the D1 fold op itself reporting a lost race) is not swallowed.
  (async done
    (let [c (kc/make-client
             {:endpoint endpoint :secret-key seed :operator-did op-did
              :fetch-fn (fn [_url _opts]
                          (js/Promise.resolve
                           #js {:ok true :status 200
                                :text (fn [] (js/Promise.resolve
                                             "{\"ok\":false,\"error\":\"FoldConflict\"}"))}))})]
      (-> (kc/fold c "yoro-social")
          (.then (fn [_] (is false "a 200 with body ok:false must reject, not resolve") (done)))
          (.catch (fn [^js e]
                    (is (= 200 (.-status e)))
                    (is (str/includes? (.-message e) "FoldConflict"))
                    (done)))))))

(deftest fold-does-not-retry-transient-5xx
  ;; Unlike transact, fold has no :retry? opt-in at all -- a single attempt,
  ;; always. A transient 5xx must reject immediately (the caller's cron
  ;; schedule is the retry mechanism, not fold itself).
  (async done
    (let [calls (atom 0)
          c (kc/make-client {:endpoint endpoint :secret-key seed :operator-did op-did
                             :fetch-fn (flaky-fetch calls 2 "{\"ok\":true}")})]
      (-> (kc/fold c "yoro-social")
          (.then (fn [_] (is false "fold must not retry a transient 5xx") (done)))
          (.catch (fn [^js e]
                    (is (= 500 (.-status e)))
                    (is (= 1 @calls) "single attempt, no retry")
                    (done)))))))

(deftest transact-retries-only-when-opted-in
  (async done
    (let [calls (atom 0)
          c (kc/make-client {:endpoint endpoint :secret-key seed :operator-did op-did
                             :fetch-fn (flaky-fetch calls 2 "{\"ok\":true}")})]
      ;; default: no retry → the first 500 rejects.
      (-> (kc/transact c "yoro-social" "[{:db/id \"k/1\" :a 1}]")
          (.then (fn [_] (is false "default transact must not retry") (done)))
          (.catch (fn [^js e]
                    (is (= 500 (.-status e)))
                    (is (= 1 @calls) "single attempt without :retry?")
                    ;; opt-in: idempotent keyed re-assert retries through the flake.
                    (reset! calls 0)
                    (-> (kc/transact c "yoro-social" "[{:db/id \"k/1\" :a 1}]" {:retry? true})
                        (.then (fn [_]
                                 (is (= 3 @calls) "2 transient 500s then commit")
                                 (done)))
                        (.catch (fn [e2] (is false (str "opt-in transact should retry: " e2)) (done))))))))))

;; ── Biscuit auth-profile (ADR-2608291500) ────────────────────────────────────
;; A :biscuit-fn client sends `Authorization: Biscuit <t>` (never CACAO), passes
;; NO cacao_b64 in the body, and hands the fn the exact db_name it is writing so
;; the token can be scoped to kotobase/db/<tenant>/<db_name>. The default CACAO
;; path is untouched (proved by every other test in this file).
(deftest biscuit-transact-envelope
  (async done
    (let [sink (atom nil)
          seen-db (atom :unset)
          bfn (fn [db] (reset! seen-db db) (js/Promise.resolve "TESTBISCUITTOKEN"))
          c (kc/make-client {:endpoint endpoint :biscuit-fn bfn
                             :fetch-fn (capturing-fetch sink)})]
      (-> (kc/transact c "yoro-social-v2" "[{:db/id \"k/1\" :a 1}]")
          (.then (fn [_]
                   (is (= "Biscuit TESTBISCUITTOKEN" (header-of sink "authorization")))
                   (is (nil? (:cacao_b64 (body-of sink))) "no CACAO in a Biscuit request body")
                   (is (= "yoro-social-v2" (:db_name (body-of sink))) "db_name still sent for edge graph derivation")
                   (is (= "yoro-social-v2" @seen-db) "biscuit-fn is told the target db_name")
                   (done)))
          (.catch (fn [e] (is false (str "biscuit transact failed: " e)) (done)))))))

(deftest biscuit-client-needs-no-secret-key
  ;; The datom plane is Biscuit-required; a Biscuit client authenticates by
  ;; header, so make-client must accept it with neither :secret-key nor :did.
  (is (some? (kc/make-client {:endpoint endpoint
                              :biscuit-fn (fn [_] (js/Promise.resolve "t"))
                              :fetch-fn (capturing-fetch (atom nil))}))))
