(ns mise.redirect
  "Hosted-redirect checkout path — mise の注文と `kotoba.kessai.redirect` の
  session をつなぐ層。

  **`mise.checkout/IPaymentPort` はこの経路を表現できない。** あちらは
  `authorize` が同期に成否を返す前提（card-present 由来）で、`place-order` は
  その戻り値で注文を作る。hosted redirect では merchant は authorization を
  発行せず、成否は**あとから webhook で届く**ので、注文は支払いの*前*に
  作られていなければならない —— でなければ webhook が「どの注文の話か」を
  引く先が無い。

  したがって順序が逆になる:

      place-order      : authorize → 成功なら Order を作る
      begin → confirm  : Order(:pending) を作る → payer を送る → webhook で :paid

  この ns だけが kessai に依存する。`mise.checkout` は素のままにしてある ——
  リダイレクト決済を使わない消費者に、その結合を読ませる理由が無い。

  Portable `.cljc`, zero host effects."
  (:require [mise.cart :as cart]
            [mise.order :as order]
            [mise.pricing :as pricing]
            [kotoba.kessai.redirect :as rd]))

;; ---------------------------------------------------------------------------
;; 金額の単位 — mise の Price と kessai の最小単位整数の橋
;; ---------------------------------------------------------------------------

(def zero-decimal-currencies
  "最小単位が「主単位そのもの」である通貨（ISO 4217 の minor unit = 0）。
  この通貨では Price の :amount をそのまま kessai に渡してよい。"
  #{"JPY" "KRW" "VND" "CLP" "ISK" "PYG" "RWF" "UGX" "VUV" "XAF" "XOF" "XPF"})

(def three-decimal-currencies
  "最小単位が 1/1000 の通貨（ISO 4217 の minor unit = 3）。**×100 では足りない。**
  既定の換算はここを扱わない —— 黙って 10 分の 1 の金額で session を作るより、
  拒否して呼び出し側に `:->minor` を書かせる方が安い。"
  #{"BHD" "IQD" "JOD" "KWD" "LYD" "OMR" "TND"})

(defn minor-amount
  "`Price` → 最小単位の整数。`{:ok n}` または `{:error reason ...}`。

  **通貨ごとの minor unit を取り違えるのは金額そのものを間違えることなので、
  推測して既定値を返さない。** zero-decimal は素通し、2 桁小数は ×100、
  3 桁小数は拒否（`:->minor` を渡せば任意の換算を使える）。"
  ([price] (minor-amount price nil))
  ([price ->minor]
   (let [{:keys [amount currency]} price]
     (cond
       (not (number? amount)) {:error :malformed-price :price price}
       (fn? ->minor)          {:ok (->minor amount currency)}
       (contains? zero-decimal-currencies currency) {:ok (long amount)}
       (contains? three-decimal-currencies currency)
       {:error :unsupported-currency-precision :currency currency
        :hint "3 桁小数通貨。:->minor を渡すこと"}
       (nil? currency) {:error :missing-currency :price price}
       :else {:ok (long (+ 0.5 (* 100 amount)))}))))

;; ---------------------------------------------------------------------------
;; begin — 支払いの前に注文を作る
;; ---------------------------------------------------------------------------

(defn begin
  "`:review` 段階の checkout から **:pending の Order** と、redirect session に
  渡すべき最小単位金額を作る。まだ何も支払われていない。

  `{:ok {:order o :amount n :currency c}}` または `{:error ... }`。

  Order を先に作るのは、webhook が戻ってきたときに「どの注文か」を引く先が
  必要だから。session の metadata に `(:id order)` を載せておくのが呼び出し側の
  仕事で、`confirm` はそれを突き合わせる。"
  [checkout opts]
  (let [{:keys [discount tax shipping ctx order-id-fn ->minor]
         :or {discount (pricing/no-discount)
              tax (pricing/flat-tax 0.0)
              shipping (pricing/free-shipping)
              order-id-fn #(str "ord_" (hash %))}} opts]
    (if (not= (:stage checkout) :review)
      {:error :not-at-review :stage (:stage checkout)}
      (let [cart (:cart checkout)
            totals (cart/totals cart {:discount discount :tax tax
                                      :shipping shipping :ctx ctx})
            total (:total totals)
            m (minor-amount total ->minor)]
        (if (:error m)
          m
          {:ok {:order (order/map->Order
                        {:id (order-id-fn checkout)
                         :items (:lines cart)
                         :shipping (:shipping checkout)
                         :contact (:contact checkout)
                         :payment-ref nil
                         :status :pending
                         :totals totals})
                :amount (:ok m)
                :currency (:currency total)}})))))

;; ---------------------------------------------------------------------------
;; confirm — webhook で確定した session だけが注文を :paid にする
;; ---------------------------------------------------------------------------

(defn confirm
  "確定済みの kessai redirect session で `:pending` の注文を `:paid` にする。
  `{:ok order}` または `{:error reason ...}`。

  拒否する条件と、それぞれが拒否である理由:

  - `:session-not-settled`  session が `:succeeded` でない。**payer が戻り URL に
                            到達しただけの session はここに来ても通らない** ——
                            kessai 側で `observe-return` が settle できないので、
                            この層まで来た時点で既に webhook を通っている。
  - `:order-mismatch`       session の metadata が指す注文 id が違う。正しい金額の
                            session を**別の注文に**当てるのを止める。kessai の
                            金額照合は session 対 event であって、注文対 session は
                            見ていないので、ここが唯一その組を見る場所。
  - `:amount-mismatch`      session の金額/通貨が注文合計と違う。合計が session 作成
                            後に変わった（カート編集・価格改定・税率変更）ときに出る。
  - `:not-pending`          注文が `:pending` でない。webhook の再送で二重に
                            `:paid` へ動かさない。"
  ([ord session] (confirm ord session nil))
  ([ord session ->minor]
   (let [m (minor-amount (get-in ord [:totals :total]) ->minor)]
     (cond
       (not (rd/succeeded? session))
       {:error :session-not-settled :status (rd/status session)}

       (not= :pending (:status ord))
       {:error :not-pending :status (:status ord)}

       (let [oid (get-in session [:redirect/metadata :order])]
         (and (some? oid) (not= oid (:id ord))))
       {:error :order-mismatch
        :expected (:id ord) :got (get-in session [:redirect/metadata :order])}

       (:error m) m

       (or (not= (:ok m) (:redirect/amount session))
           (not= (get-in ord [:totals :total :currency]) (:redirect/currency session)))
       {:error :amount-mismatch
        :expected [(:ok m) (get-in ord [:totals :total :currency])]
        :got [(:redirect/amount session) (:redirect/currency session)]}

       :else
       (let [paid (order/mark-paid (assoc ord :payment-ref (rd/->payment-ref session)))]
         (if (:ok paid) paid {:error :illegal-transition :order ord}))))))
