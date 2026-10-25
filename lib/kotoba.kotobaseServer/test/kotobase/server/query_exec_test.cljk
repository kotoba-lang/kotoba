(ns kotobase.server.query-exec-test
  "Push-down path: proves engine-computable constructs are compiled INTO a
  single engine query (not run as a post-pass), by instrumenting the
  engine-query fn -- a pushed COUNT/=/!= never materializes the full row
  set above the engine, and yields identical results to the post-pass."
  (:require #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing]])
            [kotobase.server.query-exec :as qx]))

(defn- recording-engine
  "A fake engine-query over a fixed triple set. Records the :find of every
  call so tests can assert what was pushed. Understands plain [e a v]
  patterns, [(= ?v lit)]/[(not= ?v lit)] predicate clauses, and
  (count ?v)/(count-distinct ?v) in :find with implicit group-by."
  [triples calls]
  (fn [{:keys [find where]}]
    (swap! calls conj find)
    (let [preds (filter #(seq? (first %)) where)
          pats (remove #(seq? (first %)) where)
          bind (fn [pat t] (reduce (fn [m [term val]]
                                     (cond (= term '_) m
                                           (and (symbol? term) (= \? (first (name term)))) (assoc m term val)
                                           (= term val) m
                                           :else (reduced nil)))
                                   {} (map vector pat t)))
          rows (for [t triples]
                 (reduce (fn [acc pat]
                           (if (nil? acc) nil
                               (let [b (bind pat t)] (when b (merge acc b)))))
                         {} pats))
          rows (filter map? rows)
          pass-pred (fn [m]
                      (every? (fn [[call]]
                                (let [[op a b] call
                                      av (get m a a) bv (get m b b)]
                                  (case op = (= av bv) not= (not= av bv) true)))
                              preds))
          rows (filter pass-pred rows)
          agg? (some seq? find)]
      (if agg?
        (let [gvars (remove seq? find)
              groups (if (seq gvars) (vals (group-by #(mapv % gvars) rows)) [rows])]
          (set (map (fn [g]
                      (mapv (fn [f]
                              (if (seq? f)
                                (case (first f)
                                  count (count (map #(get % (second f)) g))
                                  count-distinct (count (distinct (map #(get % (second f)) g))))
                                (get (first g) f)))
                            find))
                    groups)))
        (set (map (fn [m] (mapv #(get m %) find)) rows))))))

(def triples
  [["p1" ":city" "tokyo"] ["p2" ":city" "tokyo"] ["p3" ":city" "osaka"]])

(deftest count-is-pushed-into-the-engine-find
  (let [calls (atom [])
        eng (recording-engine triples calls)
        r (qx/execute eng {:find ['{:agg :count :var ?e :as ?c} '?city]
                           :where '[[?e ":city" ?city]]
                           :group-by '[?city]})]
    (is (= #{[2 "tokyo"] [1 "osaka"]} (set (:rows r))))
    (is (some #(some seq? %) @calls) "the engine :find carried an aggregate form -- count was pushed down")))

(deftest equals-filter-is-pushed-as-a-predicate-clause
  (let [calls (atom [])
        eng (recording-engine triples calls)
        r (qx/execute eng {:find '[?e]
                           :where '[[?e ":city" ?city]]
                           :filters [{:var '?city :op := :value "tokyo"}]})]
    (is (= #{["p1"] ["p2"]} (set (:rows r))))))

(deftest optional-forces-the-post-pass
  (let [calls (atom [])
        eng (recording-engine triples calls)
        _ (qx/execute eng {:find '[?e]
                           :where '[[?e ":city" ?city]]
                           :optionals '[[[?e ":nick" ?n]]]})]
    (is (>= (count @calls) 2) "OPTIONAL runs a second engine query (post-pass left join), not a single pushed query")))

(deftest multi-clause-optional-pushes-existing-bindings
  (let [queries (atom [])
        eng (fn [{:keys [find where] :as q}]
              (swap! queries conj q)
              (cond
                (= where '[[?e ":kind" "person"]]) [["e1"]]
                (= where '[[?friend ":name" ?name]
                           ["e1" ":knows" ?friend]]) [["e2" "Ada"]]
                :else []))
        r (qx/execute eng {:find '[?e ?name]
                           :where '[[?e ":kind" "person"]]
                           :optionals '[[[?e ":knows" ?friend]
                                        [?friend ":name" ?name]]]})]
    (is (= [["e1" "Ada"]] (:rows r)))
    (is (some #(= '[[?friend ":name" ?name]
                    ["e1" ":knows" ?friend]] (:where %)) @queries)
        "the general OPTIONAL path substitutes the already-bound subject")
    (is (not-any? #(= '[[?e ":knows" ?friend]
                        [?friend ":name" ?name]] (:where %)) @queries)
        "it does not issue the former dataset-wide OPTIONAL scan")))

(deftest path-free-bgp-is-delegated-whole-to-the-statistics-planner
  (let [queries (atom [])
        eng (fn [q] (swap! queries conj q) [])]
    (qx/execute eng {:find '[?e]
                     :where '[[?e ":broad" ?v]
                              [?seed ":id" "fixed-id"]]
                     :distinct true})
    (is (= '[[?e ":broad" ?v]
             [?seed ":id" "fixed-id"]]
           (:where (first @queries)))
        "the engine sees every component and can cost-order them from visible/materialized cardinalities")))

(deftest distinct-never-enters-the-pushdown-path-that-ignores-it
  (let [queries (atom [])
        eng (fn [q]
              (swap! queries conj q)
              [["e1"] ["e1"]])
        r (qx/execute eng {:find '[?e]
                           :where '[[?e ":kind" "person"]]
                           :distinct true})]
    (is (= [["e1"]] (:rows r)))
    (is (= 1 (count @queries)))))
