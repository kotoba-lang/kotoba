(ns kotobase.server.sparql-snapshot-test
  "What `graph.sparql` answered BEFORE the subset was retired, frozen.

  This was an equivalence suite: the same query text through both
  implementations, asserted equal. That is what justified the swap
  (ADR-2608039970), and every failure mode this migration turned up was of
  that kind — a bare `<:sp/name>` that meant one attribute here and a
  wildcard there, a literal that was `30` on one side and `\"30\"` on the
  other, a `visible?` predicate of the wrong shape that filtered nothing
  while looking like it did. None of those raise; they answer differently.

  With the old implementation gone the comparison would be self-referential,
  so the answers it gave are recorded here as VALUES, captured from it
  before deletion. A regression now shows up as a diff against what the
  surface used to say, not as two new implementations agreeing with each
  other about something wrong."
  (:require #?(:clj  [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing async] :include-macros true])
            [kotobase.server.handler :as h]
            ))

(defn- passthrough [x] #?(:clj x :cljs (js/Promise.resolve x)))

(defn- mem-store []
  (let [blocks (atom {}) heads (atom {})]
    {:get-fn (fn [cid] (get @blocks cid))
     :put! (fn [cid bytes] (swap! blocks assoc cid bytes))
     :head-get (fn [graph] (get @heads graph))
     :head-put! (fn [graph chain] (swap! heads assoc graph chain))
     :blind-fn passthrough
     :encrypt-fn passthrough
     :decrypt-fn passthrough}))

(defn- then* [x f] #?(:clj (f x) :cljs (.then (js/Promise.resolve x) f)))

(defn- run [steps]
  #?(:clj (doseq [s steps] (s))
     :cljs (async done
             (-> (reduce (fn [p s] (.then p (fn [_] (s)))) (js/Promise.resolve nil) steps)
                 (.then (fn [_] (done)))
                 (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(def ^:private tx
  (str "[{:db/id \"e1\" :sp/name \"alice\" :sp/age 30}"
       " {:db/id \"e2\" :sp/name \"bob\"}]"))

(def ^:private snapshot
  "query -> what the retired subset answered. Captured by running it.

  Two entries differ from the subset ON PURPOSE, and are marked; everything
  else is byte-identical to what it said."
  {"SELECT ?e WHERE { ?e <:sp/name> \"alice\" }"
   {:vars ["?e"] :rows [["e1"]]}

   "SELECT ?e ?n WHERE { ?e <:sp/name> ?n }"
   {:vars ["?e" "?n"] :rows [["e1" "alice"] ["e2" "bob"]]}

   "SELECT * WHERE { ?e <:sp/age> ?v }"
   {:vars ["?e" "?v"] :rows [["e1" "30"]]}

   "SELECT ?n WHERE { ?e <:sp/name> ?n . ?e <:sp/age> 30 }"
   {:vars ["?n"] :rows [["alice"]]}

   "SELECT ?e ?a WHERE { ?e <:sp/name> ?n . OPTIONAL { ?e <:sp/age> ?a } }"
   {:vars ["?e" "?a"] :rows [["e1" "30"] ["e2" nil]]}

   "SELECT ?e WHERE { { ?e <:sp/name> \"alice\" } UNION { ?e <:sp/name> \"bob\" } }"
   {:vars ["?e"] :rows [["e1"] ["e2"]]}

   "SELECT ?e ?n WHERE { ?e <:sp/name> ?n } ORDER BY ?n"
   {:vars ["?e" "?n"] :rows [["e1" "alice"] ["e2" "bob"]]}

   "SELECT ?e ?n WHERE { ?e <:sp/name> ?n } ORDER BY DESC(?n)"
   {:vars ["?e" "?n"] :rows [["e2" "bob"] ["e1" "alice"]]}

   "SELECT ?e ?n WHERE { ?e <:sp/name> ?n } LIMIT 1"
   {:vars ["?e" "?n"] :rows [["e1" "alice"]]}

   "SELECT (COUNT(?e) AS ?c) WHERE { ?e <:sp/name> ?n }"
   {:vars ["?c"] :rows [[2]]}

   "SELECT ?n (COUNT(?e) AS ?c) WHERE { ?e <:sp/name> ?n } GROUP BY ?n"
   {:vars ["?n" "?c"] :rows [["alice" 1] ["bob" 1]]}

   "SELECT ?e WHERE { ?e <:sp/age> ?v . FILTER(?v > 25) }"
   {:vars ["?e"] :rows [["e1"]]}

   "SELECT ?e WHERE { ?e <:sp/age> ?v . FILTER(?v < 25) }"
   {:vars ["?e"] :rows []}

   "SELECT ?e ?n WHERE { ?e <:sp/name> ?n . FILTER(?n != \"bob\") }"
   {:vars ["?e" "?n"] :rows [["e1" "alice"]]}

   ;; DIVERGENCE, deliberate. The subset refused a WHERE whose only content
   ;; is an OPTIONAL. That is legal SPARQL and it binds ?e perfectly well, so
   ;; the surface answers it now instead of rejecting it.
   "SELECT ?e WHERE { OPTIONAL { ?e <:sp/name> ?n } }"
   {:vars ["?e"] :rows [["e1"] ["e2"]]}})

(def ^:private still-refused
  "The subset refused these. So does the surface, on purpose.

  SPARQL says an unbound SELECT var is simply unbound, which would answer
  `[[nil] [nil]]` — one useless row per solution. Nobody writes `SELECT ?x`
  meaning `give me a column of nothing`; it is a typo every time, and the
  refusal is kinder than the spec-correct answer."
  ["SELECT ?x WHERE { ?e <:sp/name> ?n }"])

(defn- ordered? [q] (boolean (re-find #"(?i)ORDER\s+BY" q)))

(defn- normalize
  "Rows keyed by var name. A SET unless the query said ORDER BY — nothing
  promises order without one, so comparing vectors there would fail on a
  difference SPARQL itself says is not one."
  [ordered? {:keys [vars rows]}]
  (let [as-maps (map (fn [row] (zipmap vars row)) rows)]
    {:vars (set vars)
     :rows (if ordered? (vec as-maps) (set as-maps))}))

(deftest graph-sparql-still-answers-what-it-used-to
  (let [store (mem-store)]
    (run
     (into [(fn [] (then* (h/handle store "transact" {:graph "snap" :tx_edn tx} "did:key:ztest")
                          (fn [r] (is (:ok r)))))]
           (map (fn [[q expected]]
                  (fn []
                    (then* (h/handle store "sparql" {:graph "snap" :sparql q} nil)
                           (fn [got]
                             (testing q
                               (is (:ok got))
                               (is (= (normalize (ordered? q) expected)
                                      (normalize (ordered? q) got))))))))
                snapshot)))))

(deftest what-it-refused-it-still-refuses
  (let [store (mem-store)]
    (run
     (into [(fn [] (then* (h/handle store "transact" {:graph "snap2" :tx_edn tx} "did:key:ztest")
                          (fn [r] (is (:ok r)))))]
           (map (fn [q]
                  (fn []
                    (then* (h/handle store "sparql" {:graph "snap2" :sparql q} nil)
                           (fn [got]
                             (testing q
                               (is (false? (:ok got)))
                               (is (= "UnsupportedSparql" (:error got))))))))
                still-refused)))))

(deftest a-parse-failure-is-still-refused
  (let [store (mem-store)]
    (run
     [(fn []
        (then* (h/handle store "sparql" {:graph "snap3" :sparql "SELEC ?e WHERE"} nil)
               (fn [r]
                 (is (false? (:ok r)))
                 (is (= "UnsupportedSparql" (:error r))))))])))

(deftest ask-is-refused-rather-than-flattened
  (testing "graph.sparql returns {:vars :rows}; a boolean is not that shape,
            and answering one anyway is how a surface starts lying"
    (let [store (mem-store)]
      (run
       [(fn []
          (then* (h/handle store "sparql" {:graph "snap4" :sparql "ASK WHERE { ?e <:sp/name> ?n }"} nil)
                 (fn [r]
                   (is (false? (:ok r)))
                   (is (= "UnsupportedSparql" (:error r))))))]))))

;; ── beyond the retired subset ───────────────────────────────────────────────
;; These have no snapshot: the subset's FILTER grammar was a single
;; `?var op literal`, so && / || / ! / BOUND were rejected outright. There is
;; nothing to compare against and no equivalence to preserve — only the new
;; behaviour to state.

(deftest boolean-filters-work
  (let [store (mem-store)]
    (run
     [(fn [] (then* (h/handle store "transact" {:graph "bool" :tx_edn tx} "did:key:ztest")
                    (fn [r] (is (:ok r)))))
      (fn []
        (then* (h/handle store "sparql"
                         {:graph "bool"
                          :sparql (str "SELECT ?e WHERE { ?e <:sp/name> ?n . ?e <:sp/age> ?v . "
                                       "FILTER(?v > 25 && ?n != \"bob\") }")} nil)
               (fn [r]
                 (is (:ok r))
                 (is (= [["e1"]] (:rows r))))))
      (fn []
        (then* (h/handle store "sparql"
                         {:graph "bool"
                          :sparql (str "SELECT ?e WHERE { ?e <:sp/name> ?n . "
                                       "FILTER(?n = \"alice\" || ?n = \"bob\") }")} nil)
               (fn [r]
                 (is (:ok r))
                 (is (= #{["e1"] ["e2"]} (set (:rows r)))))))
      (fn []
        (then* (h/handle store "sparql"
                         {:graph "bool"
                          :sparql (str "SELECT ?e WHERE { ?e <:sp/name> ?n . "
                                       "FILTER(!(?n = \"bob\")) }")} nil)
               (fn [r]
                 (is (:ok r))
                 (is (= [["e1"]] (:rows r))))))])))

(deftest bound-distinguishes-an-optional-that-matched
  (testing "the reason BOUND exists: an OPTIONAL leaves the var absent, and
            only BOUND can tell that from a value"
    (let [store (mem-store)]
      (run
       [(fn [] (then* (h/handle store "transact" {:graph "bnd" :tx_edn tx} "did:key:ztest")
                      (fn [r] (is (:ok r)))))
        (fn []
          (then* (h/handle store "sparql"
                           {:graph "bnd"
                            :sparql (str "SELECT ?e WHERE { ?e <:sp/name> ?n . "
                                         "OPTIONAL { ?e <:sp/age> ?a } FILTER(BOUND(?a)) }")} nil)
                 (fn [r]
                   (is (:ok r))
                   (is (= [["e1"]] (:rows r)) "only the one with an age"))))
        (fn []
          (then* (h/handle store "sparql"
                           {:graph "bnd"
                            :sparql (str "SELECT ?e WHERE { ?e <:sp/name> ?n . "
                                         "OPTIONAL { ?e <:sp/age> ?a } FILTER(!BOUND(?a)) }")} nil)
                 (fn [r]
                   (is (:ok r))
                   (is (= [["e2"]] (:rows r)) "and the one without"))))]))))
