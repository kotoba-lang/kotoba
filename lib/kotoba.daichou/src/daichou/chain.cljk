(ns daichou.chain
  "受領証の連鎖。

   **検証は「壊れているか」ではなく「どこで壊れたか」を返す。**壊れた事実だけを
   返す検証器は、運用では『台帳全体が信用できない』としか読めず、実務では捨てられる。
   位置が出れば、そこから前は使える。"
  (:require [daichou.receipt :as receipt]
            [daichou.hash :as h]))

(defn append
  "連鎖の末尾に1件足す。前件のハッシュを自動で結ぶ。"
  [chain {:keys [action approval at]}]
  (conj (vec chain)
        (receipt/make {:action action
                       :approval approval
                       :at at
                       :previous-hash (:receipt/hash (last chain))})))

(defn verify
  "連鎖を検証する。

   返すのは `{:ok? bool :length n :broken-at idx :reason kw}`。
   `:broken-at` は**最初に壊れた位置**で、そこまでは信用できる。

   `:verifier` を渡すと署名も検証する。渡さなければ**署名は見ない** — 見ていない
   ものを『通った』と報告しないため、`:signed-checked?` に何をしたかを出す。
   署名の無い受領証は、verifier を渡した場合に `:reason :unsigned` で落ちる:
   署名を検証すると決めた台帳に無署名の行があるのは、検証していないのと同じ。"
  [chain & [{:keys [verifier]}]]
  (let [chain (vec chain)]
    (loop [i 0 prev h/zero-hash]
      (if (>= i (count chain))
        {:ok? true :length (count chain) :signatures-checked? (boolean verifier)}
        (let [r (nth chain i)]
          (cond
            (not= (:receipt/previous-hash r) prev)
            {:ok? false :length (count chain) :broken-at i :reason :chain-break
             :signatures-checked? (boolean verifier)}

            (not (receipt/intact? r))
            {:ok? false :length (count chain) :broken-at i :reason :receipt-altered
             :signatures-checked? (boolean verifier)}

            (and verifier (nil? (:receipt/signature r)))
            {:ok? false :length (count chain) :broken-at i :reason :unsigned
             :signatures-checked? true}

            (and verifier (not (receipt/signature-valid? r verifier)))
            {:ok? false :length (count chain) :broken-at i :reason :signature-invalid
             :signatures-checked? true}

            :else (recur (inc i) (:receipt/hash r))))))))

(defn approvals-by
  "誰の承認で何件動いたか。監査で最初に聞かれる問いなので、台帳の側に置く。"
  [chain]
  (frequencies (map (comp :approval/by :receipt/approval) chain)))
