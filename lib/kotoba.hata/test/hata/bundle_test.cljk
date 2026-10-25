(ns hata.bundle-test
  "The addressing gate: a bundle whose CIDs hold reads, one that lies does
  not. Digests are injected fakes here — this repo owns no hashing; what is
  pinned is the shape of the refusal."
  (:require #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing]])
            [hata.bundle :as bundle]))

(defn fake-digest [bytes] (str "d:" (hash bytes)))

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

(def entries
  {mon-cid mon-bytes
   logic-cid logic-bytes
   ui-cid ui-bytes})

(def seams {:digest-fn fake-digest})

(deftest a-truthful-bundle-reads
  (is (= [] (bundle/problems seams {:bundle/manifest manifest :bundle/entries entries})))
  (let [read (:ok (bundle/read-bundle seams {:bundle/manifest manifest :bundle/entries entries}))]
    (is (= mon-cid (:mon-cid read)))
    (is (= mon-bytes (:mon read)))
    (is (= [{:cid logic-cid :bytes logic-bytes}] (:logic read)))
    (is (= {:cid ui-cid :entry "index.html" :bytes ui-bytes} (:ui read)))))

(deftest a-lying-cid-is-refused-by-reason
  (let [bad (assoc entries mon-cid "tampered")]
    (is (= [{:problem :digest-mismatch :cid mon-cid}]
           (bundle/problems seams {:bundle/manifest manifest :bundle/entries bad}))))
  (is (= [{:problem :missing-entry :cid logic-cid}]
         (bundle/problems seams {:bundle/manifest manifest
                                 :bundle/entries (dissoc entries logic-cid)}))))

(deftest a-bundle-without-a-manifest-or-role-reads-as-nothing
  (is (= [{:problem :no-manifest} {:problem :no-roles
                                   :detail "a role carries the 紋 and its logic"}]
         (bundle/problems seams {:bundle/entries entries})))
  (is (= [{:problem :no-roles :detail "a role carries the 紋 and its logic"}]
         (bundle/problems seams {:bundle/manifest (dissoc manifest :kotoba.app/roles)
                                 :bundle/entries entries}))))
