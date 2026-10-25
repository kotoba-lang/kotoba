(ns kotobase.datom-source-test
  "The claim under test is the PLAN: that every pattern shape the conformance
  corpus exercises is pushed to an index read that actually returns the datoms
  that pattern needs.

  So the fake `datoms-fn` here is deliberately strict — it serves the corpus
  the way `kotobase-server`'s `do-datoms` does, honouring `index` and
  `components` exactly. A plan that names the wrong index, or puts components
  in the wrong order, returns the wrong rows and the conformance suite catches
  it. A permissive fake that ignored its arguments would prove nothing."
  (:require [cljs.test :refer-macros [deftest is testing async]]
            [datom.source :as src]
            [datom.source.conformance :as conf]
            [kotobase.datom-source :as ds]))

;; ── a fake do-datoms ────────────────────────────────────────────────────────

(defn- index-key
  "The positions `index` orders by, in order — the prefix `components` binds."
  [index]
  (case index
    "eavt" [:s :p :o]
    "aevt" [:p :s :o]
    "avet" [:p :o :s]
    (throw (js/Error. (str "fake do-datoms: unsupported index " index)))))

(defn- serve
  "`quads` filtered by `components` as a PREFIX of `index`'s key order —
  which is the only thing a real index read can do."
  [quads index components]
  (let [ks (index-key index)]
    (when (> (count components) (count ks))
      (throw (js/Error. "fake do-datoms: more components than the index has positions")))
    (->> quads
         (filter (fn [q] (every? true?
                                 (map (fn [k c] (= (get q k) c)) ks components))))
         ;; `pr-str`: a real row reports v_edn, the ENCODING of the stored
         ;; value. A fake that reported the value itself would let a missing
         ;; decode pass.
         (map (fn [q] #js {:e (:s q) :a (:p q) :v_edn (pr-str (:o q)) :added true})))))

(defn- fake-datoms-fn [quads calls]
  (fn [index components]
    (swap! calls conj [index (vec components)])
    (js/Promise.resolve (clj->js (serve quads index components)))))

;; ── conformance ─────────────────────────────────────────────────────────────

(deftest conforms-over-every-pattern-shape
  (testing "each conformance case is planned as an index read, and the union of
            those reads answers exactly what of-quads answers"
    (async done
      (let [patterns (map second conf/cases)
            calls (atom [])]
        (-> (ds/prefetch (fake-datoms-fn conf/corpus calls) patterns)
            (.then (fn [source]
                     (let [failures (conf/check (constantly source))]
                       (is (empty? failures) (conf/report failures))
                       (done))))
            (.catch (fn [e] (is false (str "prefetch threw: " (.-message e))) (done))))))))

;; ── the plan itself ─────────────────────────────────────────────────────────

(deftest bound-positions-are-pushed-into-the-index
  (is (= {:index "eavt" :components ["alice"] :post-filter [nil nil nil]}
         (ds/plan ["alice" nil nil])))
  (is (= {:index "eavt" :components ["alice" "likes"] :post-filter [nil nil nil]}
         (ds/plan ["alice" "likes" nil])))
  (is (= {:index "aevt" :components ["knows"] :post-filter [nil nil nil]}
         (ds/plan [nil "knows" nil])))
  (is (= {:index "avet" :components ["likes" "tea"] :post-filter [nil nil nil]}
         (ds/plan [nil "likes" "tea"]))
      "predicate+object is the selective one — both bound, straight to avet"))

(deftest an-object-only-pattern-is-an-honest-full-scan
  (testing ":vaet covers ref-valued attributes only, so a literal object is not
            reachable through it — the read degrades and says so rather than
            naming an index that cannot answer"
    (let [{:keys [index components post-filter]} (ds/plan [nil nil "30"])]
      (is (= "eavt" index))
      (is (= [] components))
      (is (= [nil nil "30"] post-filter)
          "the object position is left to the caller's filter, not claimed"))))

(deftest patterns-that-share-a-read-are-fetched-once
  (async done
    (let [calls (atom [])]
      ;; both plan to (eavt ["alice"]) — the second differs only in a position
      ;; eavt's prefix cannot bind from that shape.
      (-> (ds/prefetch (fake-datoms-fn conf/corpus calls)
                       [["alice" nil nil] ["alice" nil "bob"]])
          (.then (fn [_]
                   (is (= [["eavt" ["alice"]]] @calls)
                       "one read, not two")
                   (done)))))))

(deftest a-scan-is-scoped-to-what-was-prefetched-not-to-the-database
  (async done
    (let [calls (atom [])]
      (-> (ds/prefetch (fake-datoms-fn conf/corpus calls) [[nil "knows" nil]])
          (.then (fn [source]
                   (is (= [["aevt" ["knows"]]] @calls)
                       "one index range, not the graph")
                   (is (= #{{:s "alice" :p "knows" :o "bob"}
                            {:s "bob" :p "knows" :o "carol"}}
                          (src/scan-set source [nil "knows" nil])))
                   (done)))))))

;; ── row decoding ────────────────────────────────────────────────────────────

(deftest retractions-are-dropped-and-the-object-is-decoded
  (let [rows #js [#js {:e "alice" :a "age" :v_edn "\"30\"" :added true}
                  #js {:e "alice" :a "age" :v_edn "\"29\"" :added false}]]
    (is (= #{{:s "alice" :p "age" :o "30"}} (ds/rows->quads rows))
        "a scan answers what is currently asserted, as STORED values — the
         row's v_edn is their encoding, and a consumer cannot filter on that")))

(deftest no-rows-is-an-empty-source-not-a-failure
  (is (= #{} (ds/rows->quads nil)))
  (is (= #{} (ds/rows->quads #js []))))
