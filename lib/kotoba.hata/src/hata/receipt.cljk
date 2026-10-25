(ns hata.receipt
  "機 が 糸 に残す receipt の形 —— kototama の VM spec（kototama-vm-v1.edn
  の :receipt、schema :kototama.vm/receipt-v1）に合わせる。

  root ADR-2610082200 P3「実行が kototama の receipt を残す」を、宿 がまだ
  接続されていない今でも嘘にしない形で満たす: 機 は kototama が受けない
  receipt を記録しない。宿 を繋いだら、その receipt がそのまま通る。"
  (:require [hata.ito :as ito]))

(def receipt-v1-required
  "spec/kototama-vm-v1.edn の :receipt :required（順序も spec どおり）。"
  [:machine-spec :implementation :profile :message-cid :program-cid
   :state-before :state-after :outcome :fuel-used :events :authority-decision])

(def receipt-v1-forbidden
  "同 spec の :forbidden。ここが出た receipt は記録してはいけない。"
  #{:raw-biscuit :private-key :ambient-host-handle})

(def authority-decision-keys
  "同 spec の :authority-decision。"
  [:manifest-cid :grant-ids :policy-id :world :epoch])

(defn problems
  "Everything kototama's receipt-v1 would refuse about this receipt.
  Empty = the receipt is one the VM spec accepts."
  [receipt]
  (cond-> []
    (not (map? receipt))
    (conj {:problem :receipt-not-a-map})

    true (into (for [k receipt-v1-required
                     :when (nil? (get receipt k))]
                 {:problem :missing-receipt-key :key k}))

    true (into (for [k receipt-v1-forbidden
                     :when (contains? receipt k)]
                 {:problem :forbidden-receipt-key :key k}))

    (map? (:authority-decision receipt))
    (into (for [k authority-decision-keys
                :when (nil? (get-in receipt [:authority-decision k]))]
              {:problem :missing-authority-key :key k}))))

(defn acceptable?
  [receipt]
  (empty? (problems receipt)))
