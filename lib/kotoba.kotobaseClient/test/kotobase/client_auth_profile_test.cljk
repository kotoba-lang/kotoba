(ns kotobase.client-auth-profile-test
  "Locks the :auth-profile CACAO shapes at the byte/field level.

  The kotobase.net apex (net-kotobase clj-edge validate-cacao, cf-wasm
  verify-cacao) rejects the pre-cutover mint — live-probed 2026-07-09, every
  stock caller got 401 {\"ok\":false,\"error\":\"Unauthorized\"} — because it
  requires (1) the kotoba://can/kotobase:pin capability and (2) a
  kotoba://graph/ scope equal to the ISSUER DID, plus (3) the x-kotoba-did
  header and (4) a fresh nonce per request (B2 nonce-replay record). These
  tests decode the actual cacao_b64 each request carries (DAG-CBOR, the same
  decode the edge does), pin the resource list for both profiles, re-run the
  edge's two capability/scope predicates locally, verify the Ed25519
  signature, and prove nonce freshness across requests AND retry attempts."
  (:require [cljs.test :refer-macros [deftest is testing async]]
            [kotoba.lang.text :as str]
            ["@noble/curves/ed25519.js" :refer [ed25519]]
            ["@ipld/dag-cbor" :as dag-cbor]
            [kotobase.cid :as cid]
            [kotobase.cacao :as cacao]
            [kotobase.client :as kc]))

(def seed (js/Uint8Array.from (clj->js (range 32))))
(def did (cid/did-key-from-ed25519-pub (.getPublicKey ed25519 seed)))
(def op-did "did:web:kotobase.net")
(def endpoint "https://kotobase.net")
(def db-name "yoro-social")
(def graph-cid (cid/canonical-graph did db-name))

;; ── captured-request helpers ─────────────────────────────────────────────────

(defn- capturing-fetch
  "Canned-200 fetch; conjes every {:url :opts} onto `sink` (a vector atom)."
  [sink]
  (fn [url opts]
    (swap! sink conj {:url url :opts (or opts #js {})})
    (js/Promise.resolve
     #js {:ok true :status 200
          :text (fn [] (js/Promise.resolve "{\"ok\":true,\"datoms\":[]}"))})))

(defn- body-of [req]
  (js->clj (js/JSON.parse (.-body (:opts req))) :keywordize-keys true))
(defn- header-of [req k] (aget (.-headers (:opts req)) k))

(defn- decode-cacao
  "body's cacao_b64 → decoded DAG-CBOR envelope (the edge's own first step)."
  [req]
  (.decode dag-cbor (cacao/base64->bytes (:cacao_b64 (body-of req)))))

(defn- payload [^js env] (.-p env))
(defn- resources-of [env] (vec (.-resources ^js (payload env))))
(defn- nonce-of [env] (.-nonce ^js (payload env)))

;; ── the edge's capability/scope predicates (clj-edge validate-cacao) ─────────

(defn- edge-accepts-capability?
  "clj-edge: (some #(or (= % \"kotoba://can/kotobase:pin\")
                        (= % \"kotoba://op/kotobase:pin\")) resources)"
  [env]
  (boolean (some #{"kotoba://can/kotobase:pin" "kotoba://op/kotobase:pin"}
                 (resources-of env))))

(defn- edge-accepts-graph-scope?
  "clj-edge: when any kotoba://graph/ scope is present, SOME scope must equal
  the issuer DID."
  [env]
  (let [iss (.-iss (payload env))
        scopes (->> (resources-of env)
                    (filter #(str/starts-with? % "kotoba://graph/"))
                    (map #(subs % (count "kotoba://graph/"))))]
    (or (empty? scopes) (boolean (some #(= % iss) scopes)))))

(defn- signature-verifies?
  "Recompute the SIWE message from the decoded payload and check the Ed25519
  signature under the issuer key — verifyWorkerB2Cacao's check, run locally."
  [^js env pub]
  (let [^js p (payload env)
        msg (cacao/cacao-siwe-message
             {:domain (.-domain p) :iss (.-iss p) :aud (.-aud p)
              :version (.-version p) :nonce (.-nonce p) :iat (.-iat p)
              :exp (.-exp p) :statement (.-statement p)
              :resources (resources-of env)})
        sig (cacao/base64url->bytes (.. env -s -s))]
    (true? (.verify ed25519 sig (cid/text->bytes msg) pub))))

(defn- client [profile sink]
  (kc/make-client (cond-> {:endpoint endpoint :secret-key seed :operator-did op-did
                           :fetch-fn (capturing-fetch sink)}
                    profile (assoc :auth-profile profile))))

;; ── apex (default) write shape ───────────────────────────────────────────────

(deftest apex-transact-cacao-shape
  (async done
    (let [sink (atom [])
          c (client nil sink)]                                  ; DEFAULT profile
      (is (= :apex (:auth-profile c)) "apex is the default")
      (-> (kc/transact c db-name "[{:db/id -1 :probe/k \"v\"}]")
          (.then (fn [_]
                   (let [req (first @sink)
                         env (decode-cacao req)
                         p (payload env)]
                     (testing "resource list, exactly (order included)"
                       (is (= ["kotoba://can/kotobase:pin"
                               "kotoba://can/datom:transact"
                               "kotoba://can/tx:create"
                               (str "kotoba://graph/" did)]
                              (resources-of env))))
                     (testing "graph scope is the ISSUER DID, not the graph CID"
                       (is (= did (.-iss p)))
                       (is (not-any? #(str/includes? % graph-cid) (resources-of env))))
                     (testing "the edge's own predicates accept it"
                       (is (edge-accepts-capability? env))
                       (is (edge-accepts-graph-scope? env)))
                     (testing "signature verifies under the issuer key"
                       (is (signature-verifies? env (.getPublicKey ed25519 seed))))
                     (testing "envelope + headers"
                       (is (= "caip122" (.. env -h -t)))
                       (is (= "EdDSA" (.. env -s -t)))
                       (is (= op-did (.-aud p)))
                       (is (= (str "CACAO " (:cacao_b64 (body-of req)))
                              (header-of req "authorization")))
                       (is (= did (header-of req "x-kotoba-did"))))
                     (done))))))))

;; ── apex read shape (body addressing unchanged) ──────────────────────────────
;; Exercised via `q` (not `datoms`): the PDS test bundle globally stubs
;; kotobase.client/datoms with a canned-result double (same caveat as
;; client-request-test's retry tests). `q` shares read-cacao verbatim.

(deftest apex-read-cacao-shape
  (async done
    (let [sink (atom [])
          c (client :apex sink)]
      (-> (kc/q c db-name "{:find [?e] :where [[?e :probe/k _]]}")
          (.then (fn [_]
                   (let [req (first @sink)
                         env (decode-cacao req)]
                     ;; BOTH read vocabularies, and the second one is not
                     ;; decoration. The XRPC edge checks `datom:read`; since
                     ;; ADR-2607279500 it bridges datomic.* to
                     ;; kotobase-storage-d1, whose gate checks the literal
                     ;; `graph:query`. A CACAO carrying only the XRPC
                     ;; vocabulary reaches D1 and is rejected as
                     ;; `Unauthenticated` -- that is what took every
                     ;; cloud-itonami-marketplace-* read down on 2026-07-27,
                     ;; the moment production set KOTOBASE_D1_*.
                     ;;
                     ;; So this assertion is a regression guard, not a
                     ;; snapshot: dropping `graph:query` to make the list
                     ;; tidier reopens a production outage.
                     (is (= ["kotoba://can/kotobase:pin"
                             "kotoba://can/datom:read"
                             "kotoba://can/graph:query"
                             (str "kotoba://graph/" did)]
                            (resources-of env)))
                     (is (edge-accepts-capability? env))
                     (is (edge-accepts-graph-scope? env))
                     (testing "request ADDRESSING still names the graph CID —
                               only the CACAO scope moved to the issuer DID"
                       (is (= graph-cid (:graph (body-of req)))))
                     (done))))))))

;; ── :legacy keeps the pre-cutover byte shape ─────────────────────────────────

(deftest legacy-profile-keeps-precutover-shape
  (async done
    (let [sink (atom [])
          c (client :legacy sink)]
      (-> (kc/transact c db-name "[{:db/id -1 :probe/k \"v\"}]")
          (.then (fn [_] (kc/q c db-name "{:find [?e] :where [[?e :probe/k _]]}")))
          (.then (fn [_]
                   (let [[w r] (map decode-cacao @sink)]
                     (is (= ["kotoba://can/datom:transact"
                             "kotoba://can/tx:create"
                             (str "kotoba://graph/" graph-cid)]
                            (resources-of w)))
                     ;; `:legacy` keeps the pre-cutover CAPABILITY SCOPE (graph
                     ;; CID, not issuer DID) -- that is what this test pins.
                     ;; It does not opt out of the dual read vocabulary, which
                     ;; `read-cacao` applies on every profile because the
                     ;; bridge that needs it sits below the profile choice.
                     (is (= ["kotoba://can/datom:read"
                             "kotoba://can/graph:query"
                             (str "kotoba://graph/" graph-cid)]
                            (resources-of r)))
                     (testing "and this is exactly the shape the apex 401s"
                       (is (not (edge-accepts-capability? w)))
                       (is (not (edge-accepts-graph-scope? w))))
                     (is (signature-verifies? w (.getPublicKey ed25519 seed)))
                     (done))))))))

;; ── nonce freshness: per request AND per retry attempt ───────────────────────

(deftest fresh-nonce-per-request
  (async done
    (let [sink (atom [])
          c (client :apex sink)]
      (-> (kc/transact c db-name "[]")
          (.then (fn [_] (kc/transact c db-name "[]")))
          (.then (fn [_]
                   (let [[a b] (map (comp nonce-of decode-cacao) @sink)]
                     (is (and (string? a) (string? b)))
                     (is (not= a b) "the apex records nonces — reuse 401s")
                     (done))))))))

(deftest fresh-nonce-per-retry-attempt
  ;; with-retry re-runs the whole thunk; the mint must live INSIDE it so a
  ;; retried attempt is not replay-rejected for reusing the failed attempt's
  ;; nonce.
  (async done
    (let [sink (atom [])
          calls (atom 0)
          c (kc/make-client
             {:endpoint endpoint :secret-key seed :operator-did op-did
              :fetch-fn (fn [url opts]
                          (swap! sink conj {:url url :opts opts})
                          (if (= 1 (swap! calls inc))
                            (js/Promise.resolve
                             #js {:ok false :status 500
                                  :text (fn [] (js/Promise.resolve "boom"))})
                            (js/Promise.resolve
                             #js {:ok true :status 200
                                  :text (fn [] (js/Promise.resolve "{\"ok\":true}"))})))})]
      (-> (kc/transact c db-name "[{:db/id \"k/1\" :a 1}]" {:retry? true})
          (.then (fn [_]
                   (let [nonces (map (comp nonce-of decode-cacao) @sink)]
                     (is (= 2 (count nonces)) "one failed attempt + one retry")
                     (is (apply distinct? nonces) "each attempt minted fresh")
                     (done))))
          (.catch (fn [e] (is false (str "retry should succeed: " e)) (done)))))))

;; ── request-cacao (public mint for custom callers) ───────────────────────────

(deftest request-cacao-mints-per-profile
  (let [apex (kc/make-client {:endpoint endpoint :secret-key seed :operator-did op-did})
        legacy (kc/make-client {:endpoint endpoint :secret-key seed :operator-did op-did
                                :auth-profile :legacy})
        dec* (fn [b64] (.decode dag-cbor (cacao/base64->bytes b64)))]
    (is (= ["kotoba://can/kotobase:pin"
            "kotoba://can/datom:transact"
            "kotoba://can/tx:create"
            (str "kotoba://graph/" did)]
           (resources-of (dec* (kc/request-cacao apex ["datom:transact" "tx:create"] graph-cid)))))
    (is (= ["kotoba://can/datom:transact"
            "kotoba://can/tx:create"
            (str "kotoba://graph/" graph-cid)]
           (resources-of (dec* (kc/request-cacao legacy ["datom:transact" "tx:create"] graph-cid)))))
    (testing "nil without a signing key (unauthenticated caller)"
      (let [ro (kc/make-client {:endpoint endpoint :did did :operator-did op-did
                                :public-reads? true})]
        (is (nil? (kc/request-cacao ro ["datom:read"] graph-cid)))))))
