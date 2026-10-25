(ns hata.receipt-test
  "機 は kototama の VM spec が受けない receipt を 糸 に残さない。
  key 集合は kototama/spec/kototama-vm-v1.edn の :receipt から写した。"
  (:require #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing]])
            [hata.conductor :as conductor]
            [hata.receipt :as receipt]))

(def ok-receipt
  {:machine-spec "kototama.vm/1"
   :implementation "host-stub"
   :profile :core/v1
   :message-cid "bafyMsg"
   :program-cid "bafyProg"
   :state-before "bafyS0"
   :state-after "bafyS1"
   :outcome :ran
   :fuel-used 1
   :events []
   :authority-decision {:manifest-cid "bafyM" :grant-ids []
                        :policy-id "p1" :world :w :epoch 1}})

(deftest a-spec-shaped-receipt-is-acceptable
  (is (= [] (receipt/problems ok-receipt)))
  (is (true? (receipt/acceptable? ok-receipt))))

(deftest a-missing-key-is-named
  (is (= [{:problem :missing-receipt-key :key :fuel-used}]
         (receipt/problems (dissoc ok-receipt :fuel-used)))))

(deftest a-forbidden-key-refuses-the-receipt
  (is (= [{:problem :forbidden-receipt-key :key :private-key}]
         (receipt/problems (assoc ok-receipt :private-key "oops")))))

(deftest the-authority-decision-is-complete
  (is (= [{:problem :missing-authority-key :key :policy-id}]
         (receipt/problems (assoc-in ok-receipt [:authority-decision :policy-id] nil)))))

(deftest the-machine-records-no-receipt-kototama-would-refuse
  (letfn [(machine [host-fn]
            (conductor/resident
             {:cid-fn hash :sign-fn (fn [a x] (str "sig:" (hash [a x])))
              :verify-fn (fn [a x s] (= s (str "sig:" (hash [a x]))))
              :device-key "d1" :membrane-check-fn (constantly true)
              :host-fn host-fn}))
          (genesis! [m id]
            (let [action {:hata.action/kind :open :hata.action/mon (first id)
                          :hata.action/prev nil}]
              (conductor/record! m id {:hata.action/action action
                                       :author "d1"
                                       :signature ((:sign-fn m) "d1" action)})))]
    ;; a stub host that answers with a non-receipt
    (let [m (machine (fn [_ _] {:host :ran}))
          id ["mon-1" "d1"]
          _ (conductor/start-cell! m {:mon-cid "mon-1" :agent-key "d1" :membrane-proof "p"})
          _ (genesis! m id)
          ran (conductor/run-logic! m id {:op :compute})]
      (is (true? (:receipt-refused ran)))
      ;; the genesis is there, the refused receipt is not
      (is (= 1 (count (:hata.cell/ito (get @(:cells m) id))))))
    ;; a spec-shaped host records
    (let [m (machine (fn [_ _] (assoc ok-receipt :host :ran)))
          id ["mon-1" "d1"]
          _ (conductor/start-cell! m {:mon-cid "mon-1" :agent-key "d1" :membrane-proof "p"})
          _ (genesis! m id)
          _ (conductor/run-logic! m id {:op :compute})
          chain (:hata.cell/ito (get @(:cells m) id))]
      (is (= 2 (count chain)))
      (is (= :core/v1 (get-in (second chain)
                              [:hata.action/action :hata.action/body :receipt :profile]))))))
