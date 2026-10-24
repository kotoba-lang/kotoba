(ns datalog.async-test
  (:require [cljs.test :refer [deftest is async]]
            [datalog.core :as d]
            [datalog.index :as index]
            [datom.source :as source]))

(def ^:private everything (constantly true))

(defn- db-of [quads]
  (reduce #(index/assert-quad %1 %2 (constantly false))
          (index/empty-db)
          quads))

(defn- matches? [{:keys [s p o]} [want-s want-p want-o]]
  (and (or (nil? want-s) (= want-s s))
       (or (nil? want-p) (= want-p p))
       (or (nil? want-o) (= want-o o))))

(defn- async-source [quads calls]
  (reify source/IAsyncPatternSource
    (-scan-async [_ pattern]
      (swap! calls conj pattern)
      (js/Promise.resolve (into #{} (filter #(matches? % pattern)) quads)))))

(deftest q-async-matches-q-across-the-query-language
  (async done
    (let [quads [{:s "alice" :p "parent" :o "bob"}
                 {:s "bob" :p "parent" :o "carol"}
                 {:s "carol" :p "parent" :o "dave"}
                 {:s "alice" :p "score" :o 10}
                 {:s "bob" :p "score" :o 20}
                 {:s "carol" :p "score" :o 30}
                 {:s "alice" :p "active" :o true}
                 {:s "carol" :p "active" :o true}]
          db (db-of quads)
          calls (atom [])
          src (async-source quads calls)
          rules '[[(ancestor ?x ?y) [?x "parent" ?y]]
                  [(ancestor ?x ?y) [?x "parent" ?z] (ancestor ?z ?y)]]
          queries [{:find '[?person ?score]
                    :where '[[?person "score" ?score]
                             (not [?person "active" false])]
                    :order-by '[[?score :desc]]
                    :limit 2}
                   {:find '[?descendant]
                    :where '[(ancestor "alice" ?descendant)]
                    :rules rules}
                   {:find '[(count ?person) (sum ?score)]
                    :where '[[?person "score" ?score]]}
                   {:find '[?person ?score]
                    :where '[[?person "score" ?score]
                             [(>= ?score 15)]
                             [(< ?score 35)]]}
                   {:find '[?person]
                    :where '[(or [?person "active" true]
                                 [?person "score" 20])]}
                   ;; A predicate clause with NO result binding, over two
                   ;; variables. The `[(>= ?score 15)]` case above never reaches
                   ;; the generic predicate path -- a range comparison against a
                   ;; literal is fused into the scan -- so until this query
                   ;; existed, `q-async` had a branch no test entered. That
                   ;; branch spelled its filter `#(eval-fn-call db binding …)`,
                   ;; where `binding` is free and resolves to the
                   ;; `clojure.core/binding` MACRO; the synchronous twin spells
                   ;; it `(fn [binding] …)` and is correct. shadow-cljs compiles
                   ;; the broken form with a warning rather than an error, and
                   ;; nbb refuses to load the namespace at all, which is how it
                   ;; survived (2026-09-05, ADR-2609051700).
                   {:find '[?p ?q]
                    :where '[[?p "score" ?ps]
                             [?q "score" ?qs]
                             [(not= ?p ?q)]]}]]
      (-> (js/Promise.all
           (into-array (map #(d/q-async src % everything) queries)))
          (.then (fn [actuals]
                   (doseq [[query actual] (map vector queries (js->clj actuals))]
                     (is (= (d/q db query everything) actual)))
                   (is (seq @calls) "the async source was actually scanned")
                   (done)))
          (.catch (fn [e]
                    (is false (str "q-async threw: " (or (.-stack e) e)))
                    (done)))))))

(deftest q-async-rejects-unsafe-input-as-a-promise
  (async done
    (let [src (async-source [] (atom []))]
      (-> (d/q-async src
                     {:find '[?x]
                      :where '[(not [?x "secret" true])]}
                     everything)
          (.then (fn [_]
                   (is false "unsafe negation must not resolve")
                   (done)))
          (.catch (fn [e]
                    (is (re-find #"unsafe negation" (.-message e)))
                    (done)))))))

(deftest keyed-join-scans-run-concurrently-with-a-hard-bound
  (async done
    (let [entities (mapv #(str "e" %) (range 12))
          quads (into (mapv (fn [e] {:s e :p "kind" :o "common"}) entities)
                      (mapv (fn [e] {:s e :p "score" :o 1}) entities))
          active (atom 0)
          peak (atom 0)
          source
          (reify source/IAsyncPatternSource
            (-scan-async [_ pattern]
              (if (= "score" (second pattern))
                (js/Promise.
                 (fn [resolve _reject]
                   (let [now (swap! active inc)]
                     (swap! peak max now)
                     (js/setTimeout
                      (fn []
                        (swap! active dec)
                        (resolve (into #{} (filter #(matches? % pattern)) quads)))
                      5))))
                (js/Promise.resolve
                 (into #{} (filter #(matches? % pattern)) quads)))))]
      (-> (d/q-async source
                     {:find '[?e ?score]
                      :where '[[?e "kind" "common"]
                               [?e "score" ?score]]}
                     everything)
          (.then (fn [rows]
                   (is (= 12 (count rows)))
                   (is (> @peak 1) "independent keyed scans overlap")
                   (is (<= @peak 8) "join fan-out is capped at eight scans")
                   (done)))
          (.catch (fn [e]
                    (is false (str "parallel q-async threw: " (or (.-stack e) e)))
                    (done)))))))

(deftest keyed-scan-failure-rejects-the-query
  (async done
    (let [quads [{:s "ok" :p "kind" :o "common"}
                 {:s "bad" :p "kind" :o "common"}]
          source
          (reify source/IAsyncPatternSource
            (-scan-async [_ pattern]
              (if (= ["bad" "score" nil] pattern)
                (js/Promise.reject (js/Error. "provider failed"))
                (js/Promise.resolve
                 (into #{} (filter #(matches? % pattern)) quads)))))]
      (-> (d/q-async source
                     {:find '[?e ?score]
                      :where '[[?e "kind" "common"]
                               [?e "score" ?score]]}
                     everything)
          (.then (fn [_]
                   (is false "a failed keyed scan must reject the whole query")
                   (done)))
          (.catch (fn [e]
                    (is (= "provider failed" (.-message e)))
                    (done)))))))
