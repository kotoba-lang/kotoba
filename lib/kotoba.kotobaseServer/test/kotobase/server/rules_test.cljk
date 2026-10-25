(ns kotobase.server.rules-test
  "Recursive rules — reasoning — over the index-backed read path.

  `datomic.q`'s Datalog form is the only method whose cost is not merely a
  latency question: `:rules` runs a least fixpoint, so whatever one clause
  costs is paid again every round. It used to pay that against a freshly
  hydrated database. These tests pin the three things that had to be true
  before it could stop: the answers are the same as the hydrated path's, a
  prefetch that walks EVERY rule definition is what makes them the same, and
  the row-shaped visibility predicate is applied somewhere rows exist."
  (:require #?(:clj  [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing async] :include-macros true])
            [kotobase.server.handler :as h]))

(defn- passthrough [x] #?(:clj x :cljs (js/Promise.resolve x)))
(defn- then* [x f] #?(:clj (f x) :cljs (.then (js/Promise.resolve x) f)))

(defn- mem-store
  "`reads` counts block fetches, which is the unit ADR-2608021000 settled on:
  a wall-clock number taken on this workstation says more about the other
  agents running on it than about the query."
  ([] (mem-store {}))
  ([{:keys [visible?]}]
   (let [blocks (atom {}) heads (atom {}) reads (atom 0)]
     (cond-> {:get-fn (fn [cid] (swap! reads inc) (get @blocks cid))
              :put! (fn [cid bytes] (swap! blocks assoc cid bytes))
              :head-get (fn [graph] (get @heads graph))
              :head-put! (fn [graph chain] (swap! heads assoc graph chain))
              :blind-fn passthrough
              :encrypt-fn passthrough
              :decrypt-fn passthrough
              ::reads reads}
       visible? (assoc :visible? visible?)))))

(defn- run [steps]
  #?(:clj (doseq [s steps] (s))
     :cljs (async done
             (-> (reduce (fn [p s] (.then p (fn [_] (s))))
                         (js/Promise.resolve nil) steps)
                 (.then (fn [_] (done)))
                 (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

;; A four-level class hierarchy and one individual. Four levels, not two:
;; a two-level hierarchy is answered by the base case alone, so it cannot
;; tell a working fixpoint from a rule that never recursed.
(def ^:private ontology-tx
  (str "[{:db/id \"Cat\"    :rdfs/subClassOf \"Mammal\"}"
       " {:db/id \"Mammal\" :rdfs/subClassOf \"Animal\"}"
       " {:db/id \"Animal\" :rdfs/subClassOf \"Thing\"}"
       " {:db/id \"Felix\"  :rdf/type \"Cat\" :secret \"unlisted\"}]"))

(def ^:private sub-rules
  "`sub` is transitive `rdfs:subClassOf`; `typ` is `rdf:type` closed under it
  — RDFS rules 9 and 11, the two an ontology is actually asked for."
  (str "[[(sub ?a ?b) [?a :rdfs/subClassOf ?b]]"
       " [(sub ?a ?b) [?a :rdfs/subClassOf ?z] (sub ?z ?b)]"
       " [(typ ?i ?c) [?i :rdf/type ?c]]"
       " [(typ ?i ?c) [?i :rdf/type ?d] (sub ?d ?c)]]"))

(defn- q
  "`datomic.q`, as a set of rows. `extra` carries `with_edn`, which is how a
  caller reaches the hydrated path — an empty speculative transaction is the
  same database, so the two paths answer the same question."
  ([store query] (q store query {}))
  ([store query extra]
   (then* (h/do-q store (merge {:graph "g" :query_edn query} extra))
          (fn [resp] (is (:ok resp) (str "query failed: " (pr-str resp)))
            (set (:rows resp))))))

(defn- transact [store] (h/handle store "transact" {:graph "g" :tx_edn ontology-tx} "did:key:ztest"))

(deftest recursive-rules-answer-over-the-index-path
  (testing "a transitive closure and a type closure, four levels deep"
    (let [store (mem-store)]
      (run
       [(fn [] (then* (transact store) (fn [resp] (is (:ok resp)))))
        (fn []
          (then* (q store (str "{:find [?b] :where [(sub \"Cat\" ?b)] :rules " sub-rules "}"))
                 (fn [rows]
                   ;; Mammal is the base case; Animal and Thing exist only if
                   ;; the fixpoint ran more than one round.
                   (is (= #{["Mammal"] ["Animal"] ["Thing"]} rows)))))
        (fn []
          (then* (q store (str "{:find [?c] :where [(typ \"Felix\" ?c)] :rules " sub-rules "}"))
                 (fn [rows]
                   (is (= #{["Cat"] ["Mammal"] ["Animal"] ["Thing"]} rows)
                       "rdf:type closed over the subClassOf closure"))))]))))

(deftest the-index-path-and-the-hydrated-path-agree
  (testing "same query, both paths — the property the switch depends on"
    (let [store (mem-store)
          rules-q (str "{:find [?c] :where [(typ \"Felix\" ?c)] :rules " sub-rules "}")
          join-q "{:find [?a ?b] :where [[?a :rdfs/subClassOf ?b]]}"]
      (run
       [(fn [] (transact store))
        (fn []
          (then* (q store rules-q)
                 (fn [indexed]
                   (then* (q store rules-q {:with_edn "[]"})
                          (fn [hydrated]
                            (is (= indexed hydrated))
                            (is (seq indexed) "and neither is empty, which would agree vacuously"))))))
        (fn []
          (then* (q store join-q)
                 (fn [indexed]
                   (then* (q store join-q {:with_edn "[]"})
                          (fn [hydrated]
                            (is (= indexed hydrated))
                            (is (= 3 (count indexed))))))))]))))

(deftest a-rule-reached-only-through-another-rule-is-still-prefetched
  (testing "walking :where's reachable rules would under-read, and answer FEWER rows"
    ;; `typ`'s body names :rdf/type; `sub`'s names :rdfs/subClassOf. A prefetch
    ;; that stopped at the rules this :where mentions by name would fetch
    ;; :rdf/type only, and the fixpoint would then find no subClassOf edge --
    ;; reporting ["Cat"] alone, which is a well-formed answer and a wrong one.
    (is (= [[nil ":rdf/type" nil] [nil ":rdfs/subClassOf" nil]]
           (sort-by second
                    (h/datalog-source-patterns
                     {:where '[(typ "Felix" ?c)]
                      :rules '[[(sub ?a ?b) [?a ":rdfs/subClassOf" ?b]]
                               [(sub ?a ?b) [?a ":rdfs/subClassOf" ?z] (sub ?z ?b)]
                               [(typ ?i ?c) [?i ":rdf/type" ?c]]
                               [(typ ?i ?c) [?i ":rdf/type" ?d] (sub ?d ?c)]]})))))

  (testing "a bound argument does not narrow the prefetch"
    ;; `(sub "Cat" ?b)` binds the rule's first parameter, so the body probes
    ;; ["Cat" attr nil] and then, one fixpoint round later, ["Mammal" attr nil].
    ;; Prefetching the first would make the second answer nothing.
    (is (= [[nil ":rdfs/subClassOf" nil]]
           (h/datalog-source-patterns
            {:where '[(sub "Cat" ?b)]
             :rules '[[(sub ?a ?b) [?a ":rdfs/subClassOf" ?b]]
                      [(sub ?a ?b) [?a ":rdfs/subClassOf" ?z] (sub ?z ?b)]]}))))

  (testing "negated, or-ed and and-ed clauses contribute their patterns"
    ;; The negated clause keeps its object literal. That is narrower, and it
    ;; is still safe in the direction that matters: the engine probes
    ;; `[<bound-e> \":b\" \"x\"]`, which this covers. Widening a LITERAL would
    ;; only read more; widening a VARIABLE is what correctness needs.
    (is (= #{[nil ":a" nil] [nil ":b" "x"] [nil ":c" nil] [nil ":d" nil]}
           (set (h/datalog-source-patterns
                 {:where '[[?e ":a" ?v]
                           (not [?e ":b" "x"])
                           (or [?e ":c" ?w] (and [?e ":d" ?u]))
                           [(> ?v 3)]]})))
        "and the predicate clause contributes none, having no attribute"))

  (testing "a variable attribute widens to the full scan it will actually be"
    (is (= [[nil nil nil]]
           (h/datalog-source-patterns {:where '[[?e ?a ?v]]})))))

(deftest the-row-predicate-hides-rows-on-the-datalog-form
  (testing "visible? is applied where rows exist, not to quads that have no :a"
    ;; The hydrated path handed this row-shaped predicate to the engine, which
    ;; applies visible? to {:s :p :o}. `(:a {:s .. :p .. :o ..})` is nil, so
    ;; every row was decided on nil -- this predicate would have returned true
    ;; for all of them and published :secret.
    (let [store (mem-store {:visible? (fn [{:keys [a]}] (not= a ":secret"))})]
      (run
       [(fn [] (transact store))
        (fn []
          (then* (q store "{:find [?v] :where [[\"Felix\" :secret ?v]]}")
                 (fn [rows] (is (= #{} rows) "the redacted attribute is not readable"))))
        (fn []
          (then* (q store "{:find [?v] :where [[\"Felix\" :rdf/type ?v]]}")
                 (fn [rows] (is (= #{["Cat"]} rows)
                                "and the predicate has not hidden everything either"))))]))))

(defn- noise-tx
  "`n` entities with nothing to do with the ontology -- the database the
  query does not ask about."
  [n]
  (str "[" (apply str (for [i (range n)]
                        (str "{:db/id \"n" i "\" :label \"L" i
                             "\" :note \"x" i "\" :extra \"e" i "\"}")))
       "]"))

(deftest the-indexed-read-count-does-not-follow-the-database
  (testing "flat in the graph, where hydrating is linear in it"
    ;; Measured 2026-08-23, block reads for the SAME rules query, after fold:
    ;;
    ;;   datoms      4    804   3,204   12,004
    ;;   indexed     6      8       8        8
    ;;   hydrated    3      7      14       44
    ;;
    ;; Two things that have to be said together. The indexed path is FLAT --
    ;; it reads the two predicate ranges the rules name and nothing else, so
    ;; a 3,000x larger database costs it nothing. And below roughly 800
    ;; datoms it is DEARER, because one read is issued per planned pattern
    ;; while hydrating a graph that small is a couple of blocks either way.
    ;; A test that asserted `indexed < hydrated` unconditionally would be
    ;; asserting something false at the small end, and it did -- this is
    ;; what it was changed to after it failed at 6 vs 3. The two graphs
    ;; compared below are therefore both ABOVE the crossover (400 and 1,600
    ;; noise entities, a 4x difference in the database); the 4-datom column
    ;; is stated here rather than asserted, because what it shows is where
    ;; this stops being worth doing, not where it works.
    (let [small (mem-store) large (mem-store)   ;; 400 and 1,600 noise entities
          rules-q (str "{:find [?c] :where [(typ \"Felix\" ?c)] :rules " sub-rules "}")
          measured (atom {})]
      (run
       [(fn [] (transact small))
        (fn [] (h/handle small "transact" {:graph "g" :tx_edn (noise-tx 400)} "did:key:ztest"))
        (fn [] (h/handle small "fold" {:graph "g"} "did:key:ztest"))
        (fn [] (transact large))
        (fn [] (h/handle large "transact" {:graph "g" :tx_edn (noise-tx 1600)} "did:key:ztest"))
        (fn [] (h/handle large "fold" {:graph "g"} "did:key:ztest"))
        (fn []
          (reset! (::reads small) 0)
          (then* (q small rules-q)
                 (fn [rows]
                   (swap! measured assoc :small-indexed @(::reads small) :small-rows rows)
                   (reset! (::reads small) 0)
                   (then* (q small rules-q {:with_edn "[]"})
                          (fn [_] (swap! measured assoc :small-hydrated @(::reads small)))))))
        (fn []
          (reset! (::reads large) 0)
          (then* (q large rules-q)
                 (fn [rows]
                   (swap! measured assoc :large-indexed @(::reads large) :large-rows rows)
                   (reset! (::reads large) 0)
                   (then* (q large rules-q {:with_edn "[]"})
                          (fn [_] (swap! measured assoc :large-hydrated @(::reads large)))))))
        (fn []
          (let [{:keys [small-indexed large-indexed small-hydrated large-hydrated
                        small-rows large-rows]} @measured]
            (is (= small-rows large-rows)
                "the answer does not depend on what else the graph holds")
            (is (seq small-rows) "and it is not empty, which would agree vacuously")
            (is (= small-indexed large-indexed)
                (str "indexed reads must not follow the database: "
                     small-indexed " -> " large-indexed))
            (is (> large-hydrated small-hydrated)
                (str "and the control has to move, or this measured nothing: "
                     small-hydrated " -> " large-hydrated))
            (is (< large-indexed large-hydrated)
                (str "which is what makes the switch worth making at size: indexed="
                     large-indexed " hydrated=" large-hydrated))))]))))
