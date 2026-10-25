(ns hata.core-test
  "The seams are fakes here and only fakes: this repo owns no crypto. What
  these tests pin is the shape discipline — a chain grows only at its head,
  nothing follows a :close, a refused membrane leaves no cell, and the 機
  delegates execution instead of deciding permission."
  (:require #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing]])
            [hata.cell :as cell]
            [hata.conductor :as conductor]
            [hata.ito :as ito]))

;; ------------------------------------------------------------ fake seams

(defn fake-cid [x]
  (str "cid:" (hash x)))

(def fake-verify (fn [author action signature] (= signature (str "sig:" author ":" (hash action)))))

(defn fake-sign [author action] (str "sig:" author ":" (hash action)))

(defn entry
  ([kind] (entry kind nil))
  ([kind extra]
   (let [action (merge {:hata.action/kind kind :hata.action/mon "mon-1"
                        :hata.action/prev nil} extra)]
     {:hata.action/action action
      :author "alice"
      :signature (fake-sign "alice" action)})))

(def seams {:cid-fn fake-cid :verify-fn fake-verify})

;; ------------------------------------------------------------------ ito

(deftest a-chain-grows-only-at-its-head
  (let [genesis (entry :open)
        cid (fake-cid (:hata.action/action genesis))
        step (entry :commit {:hata.action/prev cid})]
    (is (seq (:ok (ito/append seams [] genesis))))
    (is (seq (:ok (ito/append seams [genesis] step))))
    ;; a wrong parent is refused, and the refusal names the head
    (let [result (ito/append seams [genesis] (entry :commit {:hata.action/prev "cid:other"}))]
      (is (= :not-the-head (:problem (first (:problems result))))))))

(deftest nothing-follows-a-close
  (let [genesis (entry :open)
        genesis-cid (fake-cid (:hata.action/action genesis))
        close (entry :close {:hata.action/prev genesis-cid
                             :hata.action/next-mon "mon-2"})]
    (is (seq (:ok (ito/append seams [genesis] close))))
    (is (= :not-the-head
           (:problem (first (:problems (ito/append seams [genesis close]
                                                   (entry :commit {:hata.action/prev genesis-cid})))))))))

(deftest a-close-points-at-the-next-mon
  (let [genesis (entry :open)
        bad-close (entry :close {:hata.action/prev (fake-cid (:hata.action/action genesis))})]
    (is (= :close-without-next-mon
           (:problem (first (:problems (ito/append seams [genesis] bad-close))))))))

(deftest a-bad-signature-is-refused
  (let [forged (update (entry :open) :signature (constantly "sig:mallory:0"))]
    (is (= :bad-signature
           (:problem (first (:problems (ito/append seams [] forged))))))))

(deftest only-open-genesis-and-only-once
  (is (= :genesis-is-open
         (:problem (first (:problems (ito/append seams [] (entry :commit)))))))
  (let [genesis (entry :open)
        again (entry :open {:hata.action/prev (fake-cid (:hata.action/action genesis))})]
    (is (= :open-after-genesis
           (:problem (first (:problems (ito/append seams [genesis] again))))))))

(deftest two-chains-from-one-parent-diverge
  (let [genesis (entry :open)
        parent (fake-cid (:hata.action/action genesis))
        a [(entry :commit {:hata.action/prev parent :hata.action/body {:n 1}})]
        b [(entry :commit {:hata.action/prev parent :hata.action/body {:n 2}})]
        c [(entry :commit {:hata.action/prev "cid:somewhere" :hata.action/body {:n 1}})]]
    ;; a and b share a parent but differ: that is the 糸 の分岐
    (is (true? (ito/diverged? fake-cid a b)))
    (is (false? (ito/diverged? fake-cid a a)))
    (is (false? (ito/diverged? fake-cid a c)))))

;; ----------------------------------------------------------------- cell

(def membrane-ok (constantly true))

(deftest a-refused-membrane-leaves-no-cell
  (let [result (cell/open {:mon-cid "mon-1" :agent-key "alice"
                           :membrane-proof "proof" :membrane-check-fn (constantly false)})]
    (is (= :membrane-refused (:problem (first (:problems result)))))
    (is (nil? (:ok result))))
  (is (= :no-mon-cid
         (:problem (first (:problems (cell/open {:agent-key "alice"
                                                 :membrane-check-fn membrane-ok})))))))

(deftest a-cell-records-only-its-own-mon
  (let [cell (:ok (cell/open {:mon-cid "mon-1" :agent-key "alice"
                              :membrane-proof "p" :membrane-check-fn membrane-ok}))
        foreign (entry :open {:hata.action/mon "mon-2"})]
    (is (= :wrong-mon (:problem (first (:problems (cell/append seams cell foreign))))))))

;; ------------------------------------------------------------- conductor

(defn machine []
  (conductor/resident
   {:cid-fn fake-cid :verify-fn fake-verify :membrane-check-fn membrane-ok
    :host-fn (fn [cell call] {:host :ran :call call :mon (:hata.cell/mon-cid cell)})
    :admit-fn (fn [_cell call] (not= :forbidden (:op call)))}))

(deftest the-machine-starts-cells-and-records
  (let [m (machine)
        id (:ok (conductor/start-cell! m {:mon-cid "mon-1" :agent-key "alice"
                                          :membrane-proof "p"}))]
    (is (= ["mon-1" "alice"] id))
    (is (seq (:ok (conductor/record! m id (entry :open)))))
    (is (= :no-such-cell (:problem (first (:problems (conductor/record! m ["mon-9" "x"] (entry :open)))))))))

(deftest execution-delegates-and-a-refusal-sends-nothing
  (let [m (machine)
        id (:ok (conductor/start-cell! m {:mon-cid "mon-1" :agent-key "alice"
                                          :membrane-proof "p"}))
        ran (:ok (conductor/execute m id {:op :compute}))
        refused (conductor/execute m id {:op :forbidden})]
    (is (= :ran (:host ran)))
    (is (= :admit-refused (:problem (first (:problems refused)))))
    ;; the 機 never decides: without admit-fn the host is asked directly
    (let [m2 (dissoc m :admit-fn)]
      (is (= :ran (:host (:ok (conductor/execute m2 id {:op :forbidden}))))))))
