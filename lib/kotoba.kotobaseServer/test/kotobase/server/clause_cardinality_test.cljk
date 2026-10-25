(ns kotobase.server.clause-cardinality-test
  "The hint that lets a join stop asking once per binding.

  `datalog.core` has had a hash-join path since 2026-08-02 and it only fires
  when the caller supplies `:clause-cardinality`. This server never did, so
  every join it ran was index-nested-loop against a source it had ALREADY
  fetched into memory -- N keyed scans of resident data where one broad scan
  would do.

  The number that matters is ASKS, not milliseconds: this workstation runs
  many concurrent agent sessions, and ADR-2608021000 settled the same question
  the same way. Every test here also asserts the ANSWER is unchanged, because
  a path that asks less by answering less is not cheaper."
  (:require #?(:clj  [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing async] :include-macros true])
            [datom.source :as ds]
            [arrangement.datalog :as datalog]
            [kotobase.server.handler :as h]
            [kotobase.server.pattern-source :as ps]))

(defn- passthrough [x] #?(:clj x :cljs (js/Promise.resolve x)))
(defn- then* [x f] #?(:clj (f x) :cljs (.then (js/Promise.resolve x) f)))

(defn- mem-store []
  (let [blocks (atom {}) heads (atom {})]
    {:get-fn (fn [cid] (get @blocks cid))
     :put! (fn [cid bytes] (swap! blocks assoc cid bytes))
     :head-get (fn [g] (get @heads g))
     :head-put! (fn [g c] (swap! heads assoc g c))
     :blind-fn passthrough :encrypt-fn passthrough :decrypt-fn passthrough}))

(defn- run [steps]
  #?(:clj (doseq [s steps] (s))
     :cljs (async done
             (-> (reduce (fn [p s] (.then p (fn [_] (s)))) (js/Promise.resolve nil) steps)
                 (.then (fn [_] (done)))
                 (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(def ^:private tx
  (str "[" (apply str (for [i (range 40)]
                        (str "{:db/id \"p" i "\" :knows \"p" (mod (inc i) 40) "\""
                             " :age \"" (+ 20 (mod i 30)) "\""
                             " :city \"c" (mod i 4) "\"}")))
       "]"))

(defn- asks-and-rows
  "Run `q` over a freshly counted view of `source`, with and without the hint.
  Returns `{:plain {:asks :rows} :hinted {:asks :rows}}`."
  [source q]
  (let [one (fn [query]
              (let [counted (ds/counting source)
                    rows (datalog/q counted query (constantly true))]
                {:asks (:scans (ds/counts counted)) :rows (set rows)}))]
    {:plain (one q)
     :hinted (one (assoc q :clause-cardinality (ps/clause-cardinality source q)))}))

(defn- with-source [store q f]
  (then* (ps/source-for store ((:head-get store) "g")
                        (h/datalog-source-patterns q) (constantly true))
         (fn [source] (f (asks-and-rows source q)))))

(deftest a-two-clause-join-stops-asking-once-per-binding
  (let [store (mem-store)
        q '{:find [?a] :where [[?p ":city" "c0"] [?p ":age" ?a]]}]
    (run
     [(fn [] (h/handle store "transact" {:graph "g" :tx_edn tx} "did:key:ztest"))
      (fn []
        (with-source store q
          (fn [{:keys [plain hinted]}]
            (is (= (:rows plain) (:rows hinted))
                "the hint changes the asking, not the answer")
            (is (seq (:rows plain)) "and the answer is not empty, which would agree vacuously")
            (is (< (:asks hinted) (:asks plain))
                (str "asks " (:asks plain) " -> " (:asks hinted)))
            (is (= 2 (:asks hinted))
                "one broad scan per clause is the floor for a two-clause join"))))])))

(deftest a-three-clause-join-does-not-multiply
  (let [store (mem-store)
        q '{:find [?a] :where [[?p ":knows" ?o] [?p ":city" "c0"] [?p ":age" ?a]]}]
    (run
     [(fn [] (h/handle store "transact" {:graph "g" :tx_edn tx} "did:key:ztest"))
      (fn []
        (with-source store q
          (fn [{:keys [plain hinted]}]
            (is (= (:rows plain) (:rows hinted)))
            (is (seq (:rows plain)))
            (is (= 3 (:asks hinted))
                (str "three clauses, three scans (was " (:asks plain) ")")))))])))

(deftest the-hint-covers-clauses-a-caller-did-not-write-flat
  (testing "negation, or-branches and rule bodies are all clauses the executor joins"
    (let [source (ds/of-quads #{{:s "a" :p ":r" :o "b"} {:s "b" :p ":r" :o "c"}})
          card (ps/clause-cardinality
                source
                '{:where [[?x ":r" ?y] (not [?x ":flag" "z"]) (or [?x ":q" ?w])]
                  :rules [[(reach ?a ?b) [?a ":r" ?b]]
                          [(reach ?a ?b) [?a ":r" ?z] (reach ?z ?b)]]})]
      (is (= 2 (get card '[?x ":r" ?y])) "the :where clause")
      (is (= 0 (get card '[?x ":flag" "z"])) "inside a not")
      (is (= 0 (get card '[?x ":q" ?w])) "inside an or")
      (is (= 2 (get card '[?a ":r" ?b])) "a rule body")
      (is (= 2 (get card '[?a ":r" ?z])) "and the recursive rule's own body"))))

(deftest a-cardinality-is-counted-for-the-pattern-the-executor-will-scan
  (testing "a hint about a different relation is a hint about the wrong thing"
    (let [source (ds/of-quads #{{:s "a" :p ":r" :o "b"} {:s "a" :p ":r" :o "c"}
                                {:s "d" :p ":r" :o "e"}})]
      ;; The literal subject stays; only variables widen. `["a" :r ?y]` is 2,
      ;; not the 3 of the whole `:r` relation.
      (is (= 2 (get (ps/clause-cardinality source '{:where [["a" ":r" ?y]]})
                    '["a" ":r" ?y])))
      (is (= 3 (get (ps/clause-cardinality source '{:where [[?x ":r" ?y]]})
                    '[?x ":r" ?y]))))))
