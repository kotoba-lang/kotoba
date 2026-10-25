(ns kotobase.server.admission-test
  "The gate, and the two things a gate has to prove: that it refuses what it
  claims to refuse, and that it still runs everything else."
  (:require #?(:clj  [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing async] :include-macros true])
            [kotobase.server.admission :as adm]
            [kotobase.server.handler :as h]))

(defn- reasons [q] (set (map :reason (:refusals (adm/admit q)))))
(defn- admitted? [q] (:admitted? (adm/admit q)))

;; ── what is refused, and it is exactly the plan's two unbounded rows ──

(deftest a-pattern-binding-neither-subject-nor-attribute-is-refused
  (testing "[_ _ _] and [_ _ o] -- datom-plan's own two `:components []` rows"
    ;; `[?s ?p ?o]` reports :variable-attribute rather than :unbounded-pattern,
    ;; and that is the more useful of the two true things to say: the author
    ;; wrote a variable where an attribute goes. The refusal is the same.
    (is (= #{:variable-attribute} (reasons '{:find [?s] :where [[?s ?p ?o]]})))
    (is (= #{:unbounded-pattern} (reasons '{:find [?s] :where [[?s _ "admin"]]}))
        "an object literal does not narrow it -- :vaet covers refs, not literals")))

(deftest a-variable-attribute-is-refused-only-when-the-subject-is-unbound-too
  (testing "because [s _ _] is an entity prefix, and refusing it would be this gate inventing a rule"
    (is (= #{:variable-attribute} (reasons '{:find [?v] :where [[?e ?attr ?v]]})))
    (is (admitted? '{:find [?v] :in [?attr] :where [["e1" ?attr ?v]]})
        "subject bound -> :eavt [s], a bounded read whatever the attribute is")))

(deftest a-rule-body-counts-and-that-is-the-point
  (testing "owl.rules/triple-rules' base case is literally [?s ?p ?o]"
    (let [q '{:find [?o]
              :where [(owl-triple "Wheel" "partOf" ?o)]
              :rules [[(owl-triple ?s ?p ?o) [?s ?p ?o]]]}]
      (is (not (admitted? q)))
      (is (= #{:variable-attribute} (reasons q)))
      (is (= [[:rules 'owl-triple]] (map :where (:refusals (adm/admit q))))
          "and the refusal names the rule, not a clause the caller has to go find")))

  (testing "a bounded ruleset -- the hierarchy half -- runs"
    (is (admitted? '{:find [?c]
                     :where [(owl-type "Felix" ?c)]
                     :rules [[(owl-subclass ?a ?b) [?a ":rdfs/subClassOf" ?b]]
                             [(owl-subclass ?a ?b) [?a ":rdfs/subClassOf" ?z] (owl-subclass ?z ?b)]
                             [(owl-type ?i ?c) [?i ":rdf/type" ?c]]
                             [(owl-type ?i ?c) (owl-type ?i ?d) (owl-subclass ?d ?c)]]}))))

(deftest the-shapes-that-read-nothing-are-not-refused
  (testing "a predicate clause names no attribute, and neither does a rule invocation"
    (is (admitted? '{:find [?e] :where [[?e ":age" ?n] [(> ?n 18)]]}))
    (is (admitted? '{:find [?e]
                     :where [[?e ":a" ?v] (not [?e ":flag" "x"])
                             (or [?e ":b" ?w] (and [?e ":c" ?u]))]}))))

(deftest a-clause-shape-the-gate-does-not-know-is-refused-not-passed
  (testing "unknown must not answer the same as bounded"
    (is (= #{:unrecognised-clause} (reasons {:find '[?e] :where [{:weird :map}]})))
    (is (= #{:unrecognised-clause} (reasons {:find '[?e] :where ["a bare string"]})))))

(deftest a-query-with-no-pattern-at-all-is-refused
  (testing "it would run against an empty source and answer vacuously"
    (is (= #{:no-readable-pattern} (reasons '{:find [?e] :where []})))))

(deftest the-budget-is-a-number-and-it-refuses-above-it
  (let [policy {:max-source-datoms 10 :allow-unbounded-patterns? false}]
    (is (nil? (adm/over-budget 10 policy)) "at the cap is not over it")
    (is (= :source-over-budget (:reason (adm/over-budget 11 policy))))
    (is (nil? (adm/over-budget 200000 adm/default-policy))
        "and the stated default admits what this fleet actually holds")))

(deftest the-refusal-says-every-reason-not-the-first
  (testing "fixing one and rediscovering the next is the same round trip twice"
    (let [resp (adm/refusal-response (:refusals (adm/admit '{:find [?a] :where [[?a ?b ?c] [?d ?e ?f]]})))]
      (is (false? (:ok resp)))
      (is (= "QueryRefused" (:error resp)))
      (is (= 2 (count (:refusals resp))))
      (is (every? string? (map :clause (:refusals resp)))
          "and the wire shape carries no symbols a JSON encoder would mangle"))))

;; ── the same decision, through the handler ────────────────────────────

(defn- passthrough [x] #?(:clj x :cljs (js/Promise.resolve x)))
(defn- then* [x f] #?(:clj (f x) :cljs (.then (js/Promise.resolve x) f)))

(defn- mem-store []
  (let [blocks (atom {}) heads (atom {}) reads (atom 0)]
    {:get-fn (fn [cid] (swap! reads inc) (get @blocks cid))
     :put! (fn [cid bytes] (swap! blocks assoc cid bytes))
     :head-get (fn [g] (get @heads g))
     :head-put! (fn [g c] (swap! heads assoc g c))
     :blind-fn passthrough :encrypt-fn passthrough :decrypt-fn passthrough
     ::reads reads}))

(defn- run [steps]
  #?(:clj (doseq [s steps] (s))
     :cljs (async done
             (-> (reduce (fn [p s] (.then p (fn [_] (s)))) (js/Promise.resolve nil) steps)
                 (.then (fn [_] (done)))
                 (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(def ^:private tx
  "[{:db/id \"Cat\" :rdfs/subClassOf \"Mammal\"} {:db/id \"Felix\" :rdf/type \"Cat\"}]")

(deftest the-handler-refuses-a-whole-graph-query-without-reading-anything
  (let [store (mem-store) reads (::reads store)]
    (run
     [(fn [] (h/handle store "transact" {:graph "g" :tx_edn tx} "did:key:ztest"))
      (fn []
        (reset! reads 0)
        (then* (h/do-q store {:graph "g" :query_edn "{:find [?s ?p ?o] :where [[?s ?p ?o]]}"})
               (fn [resp]
                 (is (false? (:ok resp)))
                 (is (= "QueryRefused" (:error resp)))
                 (is (zero? @reads)
                     "refused BEFORE the read; a gate that reads first has not saved anything"))))
      (fn []
        (then* (h/do-q store {:graph "g" :query_edn "[nil nil nil]"})
               (fn [resp]
                 (is (false? (:ok resp)))
                 (is (= "QueryRefused" (:error resp))
                     "and the [s p o] vector form cannot be used to walk around it"))))
      (fn []
        (then* (h/do-q store {:graph "g" :query_edn "{:find [?c] :where [[\"Felix\" :rdf/type ?c]]}"})
               (fn [resp]
                 (is (:ok resp))
                 (is (= [["Cat"]] (:rows resp))
                     "and a bounded query still answers, which is the half a gate usually breaks"))))])))

(deftest the-deployed-sparql-surface-refuses-select-star
  (testing "graph.sparql reaches sparql-protocol/do-sparql, NOT the compiled path"
    ;; This gap shipped once: `kotobase.server.admission` landed gating
    ;; `do-q` and `run-indexed-compiled-graph-query`, and the surface that
    ;; actually answers `graph.sparql` went through neither.
    ;; `verify-unbounded-query-paths` reported the file for requiring
    ;; `pattern-source` and never mentioning `admission`, which is how this
    ;; test came to exist.
    (let [store (mem-store) reads (::reads store) measured (atom {})]
      (run
       [(fn [] (h/handle store "transact" {:graph "g" :tx_edn tx} "did:key:ztest"))
        (fn []
          (reset! reads 0)
          (then* (h/handle store "sparql"
                           {:graph "g" :sparql "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"} nil)
                 (fn [resp]
                   (swap! measured assoc :refused-reads @reads)
                   (is (false? (:ok resp)))
                   (is (= "QueryRefused" (:error resp))
                       (str "SELECT * is the whole-graph read: " (pr-str resp))))))
        (fn []
          (reset! reads 0)
          (then* (h/handle store "sparql"
                           {:graph "g" :sparql "SELECT ?c WHERE { ?s <:rdf/type> ?c }"} nil)
                 (fn [resp]
                   (swap! measured assoc :admitted-reads @reads)
                   (is (:ok resp)
                       (str "a bound predicate still answers: " (pr-str resp))))))
        (fn []
          (let [{:keys [refused-reads admitted-reads]} @measured]
            ;; NOT `zero?`: `handle` resolves the request's visibility policy
            ;; before dispatching, and that read happens either way. What the
            ;; gate saves is the QUERY's read, which is the difference.
            (is (< refused-reads admitted-reads)
                (str "refused=" refused-reads " admitted=" admitted-reads))))]))))
