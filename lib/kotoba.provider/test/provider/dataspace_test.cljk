(ns provider.dataspace-test
  "Direct host tests for the dataspace reference provider.

  KIR grant-deny stays in amu (compiler injects this host). This suite proves
  the host contract itself: isolation, facet retract, non-document fail-closed,
  and that dataspace is in the provider-conformance inventory (closed set of
  10 application capabilities in amu; this inventory is the larger host set)."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.test :refer [deftest is]]
            [kotoba.kir.value :as value]
            [provider.conformance :as conformance]
            [provider.dataspace :as dataspace]
            [provider.dataspace-kgraph :as kgraph-store]
            [provider.dataspace-store :as store]))

(defn- invoke [p request]
  ((:invoke p) request))

(defn- edn-doc [form]
  (value/document-edn-read (if (string? form) form (pr-str form))))

(defn- doc-edn [doc]
  (edn/read-string (value/document-edn-print doc)))

(defn- assert-req [edn facet]
  [dataspace/request-type :assert [dataspace/assert-type (edn-doc edn) facet]])

(defn- observe-req [edn facet]
  [dataspace/request-type :observe [dataspace/observe-type (edn-doc edn) facet]])

(defn- retract-req [edn facet]
  [dataspace/request-type :retract [dataspace/retract-type (edn-doc edn) facet]])

(defn- matches-bindings [result]
  (doc-edn (nth (nth result 2) 1)))

(defn- matches-notices [result]
  (doc-edn (nth (nth result 2) 2)))

(defn- assert-notice [assertion bindings]
  {:kind :assert :assertion assertion :bindings bindings})

(defn- retract-notice [assertion bindings]
  {:kind :retract :assertion assertion :bindings bindings})

(deftest abi-assertions-are-documents-not-edn-strings
  (is (= :document (second (first (nth dataspace/assert-type 2)))))
  (is (= :document (second (first (nth dataspace/observe-type 2)))))
  (is (= :document (second (second (nth dataspace/asserted-type 2)))))
  (is (= :document (second (first (nth dataspace/matches-type 2)))))
  (is (= :document (second (second (nth dataspace/matches-type 2))))))

(deftest observe-pattern-binds-and-fires-on-matching-assert
  (let [p (dataspace/provider)
        observed (invoke p (observe-req "[:temperature :room/a ?t]" 0))
        asserted (invoke p (assert-req "[:temperature :room/a 21]" 0))]
    (is (= :matches (second observed)))
    (is (= [] (matches-bindings observed)))
    (is (= [] (matches-notices observed)))
    (is (= :asserted (second asserted)))
    (is (= [{'?t 21}] (doc-edn (last (nth asserted 2)))))
    (let [again (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
      (is (= [{'?t 21}] (matches-bindings again)))
      (is (= [{:kind :assert :assertion [:temperature :room/a 21] :bindings {'?t 21}}]
             (matches-notices again))))))

(deftest matching-assert-delivers-document-notice-to-observer
  (let [p (dataspace/provider)]
    (invoke p (observe-req "[:temperature :room/a ?t]" 0))
    (invoke p (assert-req "[:temperature :room/a 21]" 0))
    (let [delivered (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
      (is (= :matches (second delivered)))
      (is (= [{:kind :assert :assertion [:temperature :room/a 21] :bindings {'?t 21}}]
             (matches-notices delivered)))
      (is (= [] (matches-notices
                 (invoke p (observe-req "[:temperature :room/a ?t]" 0))))))))

(deftest facet-leave-drops-undelivered-observer-notices
  (let [p (dataspace/provider)
        entered (invoke p [dataspace/request-type :facet-enter true])
        fid (last (nth entered 2))]
    (invoke p (observe-req "[:temperature :room/a ?t]" fid))
    (invoke p (observe-req "[:temperature :room/a ?t]" 0))
    (invoke p (assert-req "[:temperature :room/a 21]" 0))
    (let [left (invoke p [dataspace/request-type :facet-leave fid])
          root (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
      (is (= :retracted (second left)))
      (is (= 0 (last (nth left 2))))
      (is (= [{'?t 21}] (matches-bindings root)))
      (is (= [{:kind :assert :assertion [:temperature :room/a 21] :bindings {'?t 21}}]
             (matches-notices root))))))

(deftest facet-exit-retracts-owned-assertions-and-drops-observations
  (let [p (dataspace/provider)
        entered (invoke p [dataspace/request-type :facet-enter true])
        fid (last (nth entered 2))]
    (is (= :facet (second entered)))
    (invoke p (observe-req "[:temperature :room/a ?t]" fid))
    (invoke p (assert-req "[:temperature :room/a 21]" fid))
    (let [left (invoke p [dataspace/request-type :facet-leave fid])
          remaining (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
      (is (= :retracted (second left)))
      (is (= 1 (last (nth left 2))))
      (is (= [] (matches-bindings remaining)))
      (is (= [] (matches-notices remaining))))))

(deftest equal-assertions-have-distinct-facet-ownership
  (let [p (dataspace/provider)
        left-id (last (nth (invoke p [dataspace/request-type :facet-enter true]) 2))
        right-id (last (nth (invoke p [dataspace/request-type :facet-enter true]) 2))
        assertion "[:temperature :room/a 21]"]
    (invoke p (assert-req assertion left-id))
    (invoke p (assert-req assertion right-id))
    (let [before (invoke p (observe-req "[:temperature :room/a ?t]" 0))
          left (invoke p [dataspace/request-type :facet-leave left-id])
          after (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
      (is (= [{'?t 21} {'?t 21}] (matches-bindings before)))
      (is (= 1 (last (nth left 2))))
      (is (= [{'?t 21}] (matches-bindings after)))
      (is (= 1 (last (nth (invoke p [dataspace/request-type
                                      :facet-leave right-id]) 2)))))))

(deftest retract-is-confined-to-the-requested-facet
  (let [p (dataspace/provider)
        owner-id (last (nth (invoke p [dataspace/request-type :facet-enter true]) 2))
        other-id (last (nth (invoke p [dataspace/request-type :facet-enter true]) 2))
        assertion "[:temperature :room/a 21]"]
    (invoke p (assert-req assertion owner-id))
    (is (= 0 (last (nth (invoke p (retract-req assertion other-id)) 2))))
    (is (= 0 (last (nth (invoke p (retract-req assertion 0)) 2))))
    (is (= [{'?t 21}]
           (matches-bindings (invoke p (observe-req
                                        "[:temperature :room/a ?t]" 0)))))
    (is (= 1 (last (nth (invoke p (retract-req assertion owner-id)) 2))))
    (is (= 0 (last (nth (invoke p [dataspace/request-type
                                    :facet-leave owner-id]) 2))))))

(deftest copied-assertion-document-does-not-grant-observe
  (let [left (dataspace/provider)
        right (dataspace/provider)
        assertion (edn-doc "[:temperature :room/a 21]")]
    (invoke left (assert-req "[:temperature :room/a 21]" 0))
    (let [other (invoke right (observe-req assertion 0))]
      (is (= [:temperature :room/a 21] (doc-edn assertion)))
      (is (= [] (matches-bindings other)))
      (is (= [] (matches-notices other))))))

(deftest non-document-assertion-is-rejected
  (let [p (dataspace/provider)
        tagged (invoke p [dataspace/request-type :assert
                          [dataspace/assert-type "#cap \"dataspace\"" 0]])
        observed (invoke p [dataspace/request-type :observe
                            [dataspace/observe-type "#cap-ref \"dataspace\"" 0]])]
    (is (= :dataspace/document-invalid (second (nth tagged 2))))
    (is (= :dataspace/document-invalid (second (nth observed 2))))))

(deftest document-edn-read-rejects-tagged-cap
  (is (thrown-with-msg?
       clojure.lang.ExceptionInfo #"document-edn-read"
       (value/document-edn-read "#cap \"dataspace\"")))
  (is (thrown-with-msg?
       clojure.lang.ExceptionInfo #"document-edn-read"
       (value/document-edn-read "#cap-ref \"dataspace\""))))

(deftest forged-facet-handle-is-rejected
  (let [p (dataspace/provider)
        forged (invoke p [dataspace/request-type :facet-leave 99])
        asserted (invoke p (assert-req "[:temperature :room/a 21]" 7))]
    (is (= :dataspace/unknown-facet (second (nth forged 2))))
    (is (= :dataspace/unknown-facet (second (nth asserted 2))))))

(deftest cap-shaped-map-is-inert-data-not-a-grant
  (let [p (dataspace/provider)
        forged-map "{:cap/kind :dataspace/transact :cap/resource \"ds\" :cap/provenance []}"
        stored (invoke p (assert-req forged-map 0))
        seen (invoke p (observe-req "{:cap/kind :dataspace/transact}" 0))]
    (is (= :asserted (second stored)))
    (is (= [{}] (matches-bindings seen)))
    (is (= [{:kind :assert
             :assertion {:cap/kind :dataspace/transact
                         :cap/resource "ds"
                         :cap/provenance []}
             :bindings {}}]
           (matches-notices seen))
        "cap-shaped EDN is inert current-set data; encoding must not emit #:cap dispatch")))

(deftest instances-are-isolated
  (let [left (dataspace/provider)
        right (dataspace/provider)]
    (invoke left (assert-req "[:temperature :room/a 21]" 0))
    (is (= [{'?t 21}]
           (matches-bindings (invoke left (observe-req "[:temperature :room/a ?t]" 0)))))
    (is (= []
           (matches-bindings (invoke right (observe-req "[:temperature :room/a ?t]" 0)))))))

(deftest contract-mismatch-is-refused
  (let [p (dataspace/provider)]
    (is (thrown-with-msg?
         clojure.lang.ExceptionInfo #"dataspace request contract mismatch"
         (invoke p [[:record :wrong/type [[:x :i64]]] 0])))))

(deftest dataspace-is-in-provider-conformance-inventory
  (let [p (dataspace/provider)
        receipt (conformance/validate-suite!
                 {:dataspace/transact dataspace/capability-id}
                 [{:name :dataspace/transact :id dataspace/capability-id
                   :provider p}])
        inventory (edn/read-string
                   (slurp (io/resource
                           "kotoba/lang/provider-conformance-v1.edn")))
        names (set (map :name (:kits inventory)))
        kit (edn/read-string
             (slurp (io/resource
                     "kotoba/lang/capability-kits/dataspace-v1.edn")))]
    (is (= 24 dataspace/capability-id))
    (is (= 1 (:capability-count receipt)))
    (is (= [{:name :dataspace/transact :id 24}] (:capabilities receipt)))
    (is (contains? names :dataspace)
        "dataspace is in provider-conformance inventory")
    (is (= :document (get-in kit [:limits :assertion])))
    (is (= :host-owned-in-process-notice-delivery
           (get-in kit [:semantics :observe-model])))
    (is (= :replay-matching-assertions-as-document-notices-at-observe-time
           (get-in kit [:semantics :observe-current-set])))
    (is (= :document-notice-on-matching-retract
           (get-in kit [:semantics :observe-retract])))
    (is (= :document
           (second (first (nth (second (first (nth (:request kit) 2))) 2)))))
    (let [matches-case (some #(when (= :matches (first %)) %)
                             (nth (:result kit) 2))
          fields (nth (second matches-case) 2)]
      (is (= [:bindings :document] (first fields)))
      (is (= [:notices :document] (second fields))))))

(deftest leftover-observer-notices-do-not-leak-after-facet-leave
  (let [p (dataspace/provider)
        entered (invoke p [dataspace/request-type :facet-enter true])
        fid (last (nth entered 2))]
    (invoke p (observe-req "[:temperature :room/a ?t]" fid))
    (invoke p (assert-req "[:temperature :room/a 21]" 0))
    (invoke p [dataspace/request-type :facet-leave fid])
    (let [root (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
      (is (= [{'?t 21}] (matches-bindings root)))
      (is (= [{:kind :assert :assertion [:temperature :room/a 21] :bindings {'?t 21}}]
             (matches-notices root))
          "new observer replays the live current-set once; dead mailbox must not duplicate it"))))

(deftest observe-replays-current-matching-assertions-as-document-notices
  (let [p (dataspace/provider)]
    (invoke p (assert-req "[:temperature :room/a 21]" 0))
    (invoke p (assert-req "[:temperature :room/a 22]" 0))
    (let [first-obs (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
      (is (= [{'?t 21} {'?t 22}] (matches-bindings first-obs)))
      (is (= [{:kind :assert :assertion [:temperature :room/a 21] :bindings {'?t 21}}
              {:kind :assert :assertion [:temperature :room/a 22] :bindings {'?t 22}}]
             (matches-notices first-obs))
          "first observe delivers already-present matches as :document notices"))
    (is (= [] (matches-notices
               (invoke p (observe-req "[:temperature :room/a ?t]" 0))))
        "current-set replay is not re-enqueued; re-observe drains empty mailbox")
    (is (= [] (matches-notices
               (invoke p (observe-req "[:humidity :room/a ?h]" 0))))
        "non-matching pattern does not replay")))

(deftest matching-retract-delivers-document-notice-to-observer
  (let [p (dataspace/provider)]
    (invoke p (observe-req "[:temperature :room/a ?t]" 0))
    (invoke p (assert-req "[:temperature :room/a 21]" 0))
    (is (= [(assert-notice [:temperature :room/a 21] {'?t 21})]
           (matches-notices (invoke p (observe-req "[:temperature :room/a ?t]" 0)))))
    (invoke p (retract-req "[:temperature :room/a 21]" 0))
    (let [delivered (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
      (is (= [] (matches-bindings delivered)))
      (is (= [(retract-notice [:temperature :room/a 21] {'?t 21})]
             (matches-notices delivered))
          "retract of a matching assertion enqueues a :retract notice")
      (is (= [] (matches-notices
                 (invoke p (observe-req "[:temperature :room/a ?t]" 0))))
          "next observe drains the retraction notice"))))

(deftest retract-and-assert-share-one-mailbox
  (let [p (dataspace/provider)]
    (invoke p (observe-req "[:temperature :room/a ?t]" 0))
    (invoke p (assert-req "[:temperature :room/a 21]" 0))
    (invoke p (retract-req "[:temperature :room/a 21]" 0))
    (is (= [(assert-notice [:temperature :room/a 21] {'?t 21})
            (retract-notice [:temperature :room/a 21] {'?t 21})]
           (matches-notices (invoke p (observe-req "[:temperature :room/a ?t]" 0))))
        "assert then retract without drain yields both notices in order")))

(deftest retract-of-non-matching-assertion-does-not-notify
  (let [p (dataspace/provider)]
    (invoke p (observe-req "[:temperature :room/a ?t]" 0))
    (invoke p (assert-req "[:humidity :room/a 40]" 0))
    (invoke p (retract-req "[:humidity :room/a 40]" 0))
    (let [delivered (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
      (is (= [] (matches-bindings delivered)))
      (is (= [] (matches-notices delivered))
          "retract of a non-matching assertion does not notify that observer"))))

(deftest current-set-replay-is-assert-notices-not-retractions
  (let [p (dataspace/provider)]
    (invoke p (assert-req "[:temperature :room/a 21]" 0))
    (let [first-obs (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
      (is (= [(assert-notice [:temperature :room/a 21] {'?t 21})]
             (matches-notices first-obs))
          "first observe still returns present matches as :assert notices"))
    (invoke p (retract-req "[:temperature :room/a 21]" 0))
    (is (= [(retract-notice [:temperature :room/a 21] {'?t 21})]
           (matches-notices (invoke p (observe-req "[:temperature :room/a ?t]" 0)))))))

(deftest facet-leave-drops-undelivered-retraction-notices
  (let [p (dataspace/provider)
        entered (invoke p [dataspace/request-type :facet-enter true])
        fid (last (nth entered 2))]
    (invoke p (observe-req "[:temperature :room/a ?t]" fid))
    (invoke p (assert-req "[:temperature :room/a 21]" 0))
    (invoke p (retract-req "[:temperature :room/a 21]" 0))
    (invoke p [dataspace/request-type :facet-leave fid])
    (let [root (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
      (is (= [] (matches-bindings root)))
      (is (= [] (matches-notices root))
          "facet-leave drops undelivered retraction mail; new observer sees empty current-set"))))

(defn- observer-delivery-holds?
  [p]
  (invoke p (observe-req "[:temperature :room/a ?t]" 0))
  (invoke p (assert-req "[:temperature :room/a 21]" 0))
  (let [delivered (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
    (= [{:kind :assert :assertion [:temperature :room/a 21] :bindings {'?t 21}}]
       (matches-notices delivered))))

(defn- current-set-replay-holds?
  [p]
  (invoke p (assert-req "[:temperature :room/a 21]" 0))
  (let [first-obs (invoke p (observe-req "[:temperature :room/a ?t]" 0))
        drained (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
    (and (= [{'?t 21}] (matches-bindings first-obs))
         (= [(assert-notice [:temperature :room/a 21] {'?t 21})]
            (matches-notices first-obs))
         (= [] (matches-notices drained)))))

(defn- retraction-notice-holds?
  [p]
  (invoke p (observe-req "[:temperature :room/a ?t]" 0))
  (invoke p (assert-req "[:temperature :room/a 21]" 0))
  (invoke p (observe-req "[:temperature :room/a ?t]" 0))
  (invoke p (retract-req "[:temperature :room/a 21]" 0))
  (let [delivered (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
    (and (= [] (matches-bindings delivered))
         (= [(retract-notice [:temperature :room/a 21] {'?t 21})]
            (matches-notices delivered)))))

(defn- dropping-retract-notices-store
  "Broken store: retract removes the assertion but drains the mailbox so
  retraction notices never survive until the observer's next observe."
  []
  (let [inner (store/memory-store)
        q (:q inner)
        tx! (:transact! inner)]
    {:q q
     :transact!
     (fn [tx]
       (let [result (tx! tx)]
         (when (= :retract (:op tx))
           (doseq [observer (q {:op :observers})]
             (tx! {:op :observe
                   :pattern (:pattern observer)
                   :facet (:facet observer)})))
         result))}))

(defn- skipping-current-set-replay-store
  "Broken store: first observe returns empty notices even when matches exist."
  []
  (let [inner (store/memory-store)
        q (:q inner)
        tx! (:transact! inner)]
    {:q q
     :transact!
     (fn [tx]
       (if (not= :observe (:op tx))
         (tx! tx)
         (let [existing (some (fn [observer]
                                (and (= (:facet tx) (:facet observer))
                                     (= (:pattern tx) (:pattern observer))))
                              (q {:op :observers}))
               result (tx! tx)]
           (if existing
             result
             (assoc result :notices [])))))}))

(defn- swallowing-observer-notices-store
  "Broken store: assert enqueues, then immediately drains every mailbox."
  []
  (let [inner (store/memory-store)
        q (:q inner)
        tx! (:transact! inner)]
    {:q q
     :transact!
     (fn [tx]
       (let [result (tx! tx)]
         (when (= :assert (:op tx))
           (doseq [observer (q {:op :observers})]
             (tx! {:op :observe
                   :pattern (:pattern observer)
                   :facet (:facet observer)})))
         result))}))

(defn- dropping-facet-leave-store
  "Broken store: facet-leave drops observers and the facet, not assertions."
  []
  (let [inner (store/memory-store)
        q (:q inner)
        tx! (:transact! inner)]
    {:q q
     :transact!
     (fn [tx]
       (if (not= :facet-leave (:op tx))
         (tx! tx)
         (let [owned (filterv #(= (:id tx) (:facet %)) (q {:op :assertions}))
               result (tx! tx)]
           (doseq [cell owned]
             (tx! {:op :assert :value (:value cell) :facet 0}))
           result)))}))

(defn- facet-leave-retracts?
  [p]
  (let [entered (invoke p [dataspace/request-type :facet-enter true])
        fid (last (nth entered 2))]
    (invoke p (observe-req "[:temperature :room/a ?t]" fid))
    (invoke p (assert-req "[:temperature :room/a 21]" fid))
    (let [left (invoke p [dataspace/request-type :facet-leave fid])
          remaining (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
      (and (= :retracted (second left))
           (= 1 (last (nth left 2)))
           (= [] (matches-bindings remaining))))))

(defn- assert-retract-observe-hold?
  [p]
  (invoke p (assert-req "[:temperature :room/a 21]" 0))
  (let [seen (invoke p (observe-req "[:temperature :room/a ?t]" 0))
        retracted (invoke p (retract-req "[:temperature :room/a 21]" 0))
        after (invoke p (observe-req "[:temperature :room/a ?t]" 0))]
    (and (= [{'?t 21}] (matches-bindings seen))
         (= 1 (last (nth retracted 2)))
         (= [] (matches-bindings after)))))

(deftest default-memory-store-is-the-inject-boundary
  (is (store/store? (store/memory-store)))
  (is (store/store? (kgraph-store/store)))
  (is (thrown-with-msg?
       clojure.lang.ExceptionInfo #"dataspace store requires :q and :transact!"
       (dataspace/provider {:store {:q identity}}))))

(deftest injected-kgraph-store-honors-assert-retract-observe-facet-leave
  (is (assert-retract-observe-hold? (dataspace/provider {:store (kgraph-store/store)})))
  (is (facet-leave-retracts? (dataspace/provider {:store (kgraph-store/store)})))
  (is (observer-delivery-holds? (dataspace/provider {:store (kgraph-store/store)})))
  (is (current-set-replay-holds? (dataspace/provider {:store (kgraph-store/store)})))
  (is (retraction-notice-holds? (dataspace/provider {:store (kgraph-store/store)}))))

(deftest default-memory-store-still-honors-facet-leave
  (is (facet-leave-retracts? (dataspace/provider)))
  (is (assert-retract-observe-hold? (dataspace/provider)))
  (is (observer-delivery-holds? (dataspace/provider)))
  (is (current-set-replay-holds? (dataspace/provider)))
  (is (retraction-notice-holds? (dataspace/provider))))

(deftest store-that-drops-facet-leave-retracts-fails-closed
  (is (not (facet-leave-retracts?
            (dataspace/provider {:store (dropping-facet-leave-store)})))))

(deftest store-that-swallows-observer-notices-fails-closed
  (is (not (observer-delivery-holds?
            (dataspace/provider {:store (swallowing-observer-notices-store)})))))

(deftest store-that-skips-current-set-replay-fails-closed
  (is (not (current-set-replay-holds?
            (dataspace/provider {:store (skipping-current-set-replay-store)})))))

(deftest store-that-drops-retraction-enqueue-fails-closed
  (is (not (retraction-notice-holds?
            (dataspace/provider {:store (dropping-retract-notices-store)})))))
