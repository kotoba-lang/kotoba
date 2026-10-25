(ns kekkai.cli.desired-test
  (:require [cljs.test :refer [deftest is]]
            [kekkai.cli.desired :as desired]
            [kekkai.cli.sign :as sign]
            ["node:fs" :as fs]
            ["node:os" :as os]
            ["node:path" :as path]))

(defn temp-root [] (.mkdtempSync fs (.join path (.tmpdir os) "kekkai-desired-")))

(deftest signed-desired-state-round-trips-across-independent-roots
  (let [identity (sign/generate-authority)
        roots [(temp-root) (temp-root)]
        input {:kind :murakumo/apps :subject "murakumo/fleet/apps"
               :epoch 1 :previous-cid nil :payload {:apps [{:cid "bafytest"}]}}
        envelope (desired/seal input identity)
        published (desired/publish! roots 2 envelope (:public-b64 identity))
        pulled (desired/pull roots (:subject input) (:public-b64 identity)
                             {:kind (:kind input)})]
    (is (= 2 (:desired/copies published)))
    (is (= (:desired/cid envelope) (:desired/cid pulled)))
    (is (= (:payload input) (:desired/payload pulled)))))

(deftest same-epoch-split-brain-fails-closed
  (let [identity (sign/generate-authority)
        roots [(temp-root) (temp-root)]
        input {:kind :test/state :subject "test/state" :epoch 7 :previous-cid nil}
        left (desired/seal (assoc input :payload {:side :left}) identity)
        right (desired/seal (assoc input :payload {:side :right}) identity)]
    (desired/publish! [(first roots)] 1 left (:public-b64 identity))
    (desired/publish! [(second roots)] 1 right (:public-b64 identity))
    (is (thrown-with-msg? js/Error #"disagree"
                          (desired/pull roots "test/state" (:public-b64 identity) {})))))
