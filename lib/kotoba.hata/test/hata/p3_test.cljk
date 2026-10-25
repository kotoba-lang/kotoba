(ns hata.p3-test
  "P3 合否条件の経路 — app DID だけで bundle を開き、logic を宿 で動かし、
  糸 に receipt を残す。seams は fake だが経路は本物: CID が嘘をつく
  bundle では cell すら生まれない。"
  (:require #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing]])
            [hata.bundle :as bundle]
            [hata.conductor :as conductor]))

;; ------------------------------------------------------------- fixtures

(defn fake-digest [bytes] (str "d:" (hash bytes)))
(def fake-verify (fn [author action signature] (= signature (str "sig:" author ":" (hash action)))))
(defn fake-sign [author action] (str "sig:" author ":" (hash action)))

(def mon-bytes "mon-bytes")
(def logic-bytes "logic-bytes")
(def ui-bytes "ui-bytes")
(def mon-cid (fake-digest mon-bytes))
(def logic-cid (fake-digest logic-bytes))
(def ui-cid (fake-digest ui-bytes))

(def manifest
  {:kotoba.app/id "itonami-hello"
   :kotoba.app/kind :app
   :kotoba.app/did "did:key:z6MkApp"
   :kotoba.app/bundle-cid "bafyCarRoot"
   :kotoba.app/roles [{:role :hello :mon mon-cid :logic [logic-cid] :clone-limit 0}]
   :kotoba.app/ui {:bundle ui-cid :entry "index.html"}})

(def bundle-bytes
  {:bundle/manifest manifest
   :bundle/entries {mon-cid mon-bytes
                    logic-cid logic-bytes
                    ui-cid ui-bytes}})

(def ok-receipt
  {:machine-spec "kototama.vm/1" :implementation "test-host" :profile :core/v1
   :message-cid "bafyMsg" :program-cid "bafyProg"
   :state-before "bafyS0" :state-after "bafyS1"
   :outcome :ran :fuel-used 1 :events []
   :authority-decision {:manifest-cid "bafyM" :grant-ids []
                        :policy-id "p1" :world :w :epoch 1}})

(defn machine [& {:as overrides}]
  (merge
   (conductor/resident
    {:cid-fn fake-digest
     :sign-fn fake-sign
     :verify-fn fake-verify
     :digest-fn fake-digest
     :device-key "device-1"
     :membrane-check-fn (constantly true)
     :fetch-fn (fn [app-did] (when (= app-did "did:key:z6MkApp") :bundle-bytes))
     :parse-bundle-fn (fn [_bytes] bundle-bytes)
     :host-fn (fn [cell call] (assoc ok-receipt :host :ran :call call
                                     :mon (:hata.cell/mon-cid cell)))
     :admit-fn (fn [_cell call] (not= :forbidden (:op call)))})
   overrides))

;; ------------------------------------------------------------------ P3

(deftest an-app-opens-from-its-did-alone
  (let [m (machine)
        opened (conductor/open-bundle! m "did:key:z6MkApp")]
    (is (vector? (:ok opened)))
    (is (= [mon-cid "device-1"] (:ok opened)))
    (is (= manifest (:manifest (:bundle opened))))
    ;; 合否条件 (3): the first 糸 action names what was opened
    (let [cell (get @(:cells m) (:ok opened))
          genesis (first (:hata.cell/ito cell))]
      (is (= :open (get-in genesis [:hata.action/action :hata.action/kind])))
      (is (= {:app-did "did:key:z6MkApp" :bundle-cid "bafyCarRoot"}
             (get-in genesis [:hata.action/action :hata.action/body]))))))

(deftest a-lying-bundle-opens-nothing
  (let [m (machine :parse-bundle-fn
                   (fn [_] (update bundle-bytes :bundle/entries
                                   assoc mon-cid "tampered")))
        result (conductor/open-bundle! m "did:key:z6MkApp")]
    (is (= [{:problem :digest-mismatch :cid mon-cid}] (:problems result)))
    (is (empty? @(:cells m)))))

(deftest an-unfetched-did-opens-nothing
  (let [m (machine)]
    (is (= [{:problem :unfetched :app-did "did:key:z6MxNope"}]
           (:problems (conductor/open-bundle! m "did:key:z6MxNope"))))
    (is (empty? @(:cells m)))))

(deftest logic-runs-on-the-host-and-leaves-a-receipt
  (let [m (machine)
        cell-id (:ok (conductor/open-bundle! m "did:key:z6MkApp"))
        ran (conductor/run-logic! m cell-id {:op :compute})]
    ;; 合否条件 (2): the execution is a host call that returns a receipt
    (is (= :ran (get-in ran [:ok :host])))
    ;; 合否条件 (3): the receipt lands in the 糸 as the second action
    (let [cell (get @(:cells m) cell-id)
          chain (:hata.cell/ito cell)]
      (is (= 2 (count chain)))
      (is (= :commit (get-in (second chain) [:hata.action/action :hata.action/kind])))
      (is (= {:op :compute} (get-in (second chain) [:hata.action/action :hata.action/body :call])))
      ;; the link is explicit: the commit's prev is the genesis action's cid
      (is (= (fake-digest (:hata.action/action (first chain)))
             (get-in (second chain) [:hata.action/action :hata.action/prev]))))))

(deftest an-admit-refusal-runs-nothing-and-writes-nothing
  (let [m (machine)
        cell-id (:ok (conductor/open-bundle! m "did:key:z6MkApp"))
        refused (conductor/run-logic! m cell-id {:op :forbidden})]
    (is (= :admit-refused (:problem (first (:problems refused)))))
    (is (= 1 (count (:hata.cell/ito (get @(:cells m) cell-id)))))))
