(ns lg-curpus2skill.smoke-test
  "Smoke tests for the lg-curpus2skill clj port — clojure.test analogue of the
  Python `tests/test_smoke.py`, plus extraction-behaviour tests the original
  could not run offline (the RisingWave-backed handler is an injectable store
  seam here, so the corpus→skill transform verifies under bb with stubs)."
  (:require [clojure.test :refer [deftest is testing]]
            [langgraph.graph :as g]
            [lg-curpus2skill.audit :as audit]
            [lg-curpus2skill.server :as server]
            [lg-curpus2skill.store :as store]
            [lg-curpus2skill.graphs.health :as health]
            [lg-curpus2skill.graphs.extract-evidence :as ee]))

(def expected-graphs #{"health" "extractEvidence"})

(def expected-nsid-map
  {"com.etzhayyim.apps.curpus2skill.health"          "health"
   "com.etzhayyim.apps.curpus2skill.extractEvidence" "extractEvidence"})

;; ── server registry parity (mirrors test_smoke.py) ──────────────────────────

(deftest graphs-match-expected-set
  (is (= expected-graphs (set (keys server/GRAPHS)))))

(deftest nsid-map-completeness
  (is (= expected-nsid-map server/NSID-TO-ASSISTANT)))

(deftest nsid-map-references-known-graphs
  (doseq [[nsid gname] server/NSID-TO-ASSISTANT]
    (is (contains? server/GRAPHS gname) (str nsid " → " gname " not in GRAPHS"))))

(deftest all-graphs-invocable
  (doseq [[nm graph] server/GRAPHS]
    (is (some? graph) (str "GRAPHS[" nm "] nil"))))

;; ── dispatch surface (/ok, /health, /runs, /xrpc) ───────────────────────────

(deftest ok-endpoint
  (let [r (server/handler {:request-method :get :uri "/ok"})]
    (is (= 200 (:status r)))))

(deftest health-endpoint
  (let [r (server/health)]
    (is (= 200 (:status r)))
    (is (= "ok" (get-in r [:body :status])))
    (is (= "lg-curpus2skill" (get-in r [:body :service])))))

(deftest unknown-assistant-404
  (is (= 404 (:status (server/runs {"assistant_id" "nope" "input" {}})))))

(deftest unknown-nsid-501
  ;; Python raises 501 for an unmapped NSID (Not Implemented).
  (is (= 501 (:status (server/xrpc-post "com.etzhayyim.apps.curpus2skill.unknownMethod" {})))))

;; ── health graph end-to-end ─────────────────────────────────────────────────

(deftest health-graph-invokes
  (is (= "ok" (get-in (g/invoke health/GRAPH {}) [:result :status]))))

;; ── extractEvidence graph: Python `_node` contract (result / error) ─────────

(deftest extract-evidence-runs-envelope
  ;; default handler with the store DISABLED → scanned 0, extracted 0 (the
  ;; unconfigured Python path), wrapped in {:output ... :elapsed_s ...}.
  (store/reset-store!
   )
  (let [r (server/runs {"assistant_id" "extractEvidence" "input" {}})]
    (is (= 200 (:status r)))
    (is (contains? (:body r) :elapsed_s))
    (is (some? (get-in r [:body :output])))))

(deftest extract-evidence-node-result-shape
  (let [out (g/invoke ee/GRAPH {:input {}})]
    (is (map? (:result out)))
    (is (= "legal-corpus" (get-in out [:result :source])))
    (is (= 0 (get-in out [:result :scanned])) "disabled store scans nothing")))

(deftest extract-evidence-node-error-clipped
  ;; a throwing handler → {:error <=300 chars}, exactly like the Python _node.
  (binding [ee/*handler* (fn [_] (throw (ex-info (apply str (repeat 500 "x")) {})))]
    (let [out (g/invoke ee/GRAPH {:input {}})]
      (is (nil? (:result out)))
      (is (= 300 (count (:error out))) "error clipped to 300 chars"))))

;; ── store seam: corpus→skill extraction via stubs (offline-verifiable) ──────

(def ^:private sample-docs
  [{:doc-id "d1" :candidates [{:skill "drafting"  :score 0.99}
                              {:skill "review"    :score 0.985}
                              {:skill "filing"    :score 0.5}]}      ; below minScore
   {:doc-id "d2" :candidates [{:skill "drafting"  :score 0.98}        ; dup skill
                              {:skill "negotiate" :score 0.971}]}])

(deftest extract-pure-filters-and-dedups
  (let [skills (store/extract sample-docs {:minScore 0.97 :topK 5 :skillLimit 2000})]
    (is (= ["drafting" "review" "negotiate"]
           (mapv :skill skills)) "score-filtered, deduped by skill, sorted desc")
    (is (= 0.99 (-> skills first :score)))))

(deftest extract-pure-respects-topk-and-skilllimit
  (is (= 1 (count (store/extract sample-docs {:minScore 0.97 :topK 1 :skillLimit 2000})))
      "topK=1 keeps top skill per doc (both 'drafting') → dedup collapses to 1")
  (is (= 2 (count (store/extract sample-docs {:minScore 0.97 :topK 5 :skillLimit 2}))))
  (is (empty? (store/extract sample-docs {:minScore 1.0 :topK 5 :skillLimit 2000}))
      "minScore=1.0 filters everything"))

(deftest extract-evidence-happy-path-stubbed
  (binding [store/*query-corpus*  (fn [_source _limit] sample-docs)
            store/*persist-skills* (fn [skills] {:persisted (count skills)})]
    (let [res (store/extract-evidence {:source "legal-corpus" :limit 10
                                       :skillLimit 2000 :minScore 0.97
                                       :topK 5 :dryRun false})]
      (is (= "legal-corpus" (:source res)))
      (is (= 2 (:scanned res)))
      (is (= 3 (:extracted res)))
      (is (= 3 (:persisted res)) "persisted == extracted when not dryRun")
      (is (false? (:dryRun res))))))

(deftest extract-evidence-dryrun-skips-persist
  (binding [store/*query-corpus*  (fn [_ _] sample-docs)
            store/*persist-skills* (fn [_] (throw (AssertionError. "must not persist on dryRun")))]
    (let [res (store/extract-evidence {:dryRun true})]
      (is (= 3 (:extracted res)))
      (is (= 0 (:persisted res)) "dryRun persists nothing")
      (is (true? (:dryRun res))))))

(deftest store-enabled-gate
  (testing "inert by default → no corpus rows"
    (store/reset-store!)
    (is (= [] (store/query-corpus "legal-corpus" 10))))
  (testing "host binding enables the in-process seam"
    (store/reset-store!)
    (store/seed-corpus! "legal-corpus" sample-docs)
    (binding [store/*enabled?* true]
      (is (= 2 (count (store/query-corpus "legal-corpus" 10)))))))

(deftest audit-default-is-network-incapable
  (is (true? (audit/audit-disabled?)))
  (let [called (atom false)]
    (binding [audit/*post!* (fn [& _] (reset! called true))]
      (is (nil? (audit/emit-audit! {:activity "test"})))
      (is (false? @called)))))

(deftest audit-host-capability-is-purpose-bound
  (let [request (atom nil)]
    (binding [audit/*config* {:disabled? false
                              :dispatcher-url "https://audit.test/"
                              :internal-secret "secret"
                              :timeout-ms 25}
              audit/*post!* (fn [url opts] (reset! request [url opts]))]
      (is (nil? (audit/emit-audit! {:actor "a" :activity "extract"})))
      (is (= "https://audit.test/xrpc/com.etzhayyim.generic.audit.emit"
             (first @request)))
      (is (= "secret" (get-in @request [1 :headers "x-internal-trust"])))
      (is (= 25 (get-in @request [1 :timeout]))))))

(deftest server-start-requires-explicit-capability
  (is (thrown-with-msg? clojure.lang.ExceptionInfo
                        #"explicit HTTP server capability required"
                        (server/start! nil {:port 0}))))
