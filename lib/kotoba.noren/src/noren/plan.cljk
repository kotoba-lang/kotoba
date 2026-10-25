(ns noren.plan
  "月額プランと entitlement。純 `.cljc`。

  **決済はここに無い。** ここが持つのは「いくらで、何が付いていて、今日
  その capability を使ってよいか」だけで、実際の課金は cloud-itonami 側の
  請求面（itonami.cloud の Stripe 連携）が行う。値を 2 箇所に持たないため、
  金額の正本はこのカタログ 1 つにする。

  entitlement を先に置くのは、**契約していない相手に loop が働き続ける**のを
  止めるため。解約した店のサイトを毎月診断して提案を送り続ける loop は、
  解約を無効にしているのと同じである。"
  (:require [noren.prospect :as prospect]))

(def catalog
  "月額プラン。税抜 JPY。"
  [{:plan/id :noren.plan/mamori
    :plan/label "守り"
    :plan/price-jpy 9800
    :plan/entitlements #{:site/hosted :diagnosis/monthly :report/monthly :content/refresh-quarterly}
    :plan/for "今のサイトを直して維持する"}
   {:plan/id :noren.plan/hiraki
    :plan/label "開き"
    :plan/price-jpy 19800
    :plan/entitlements #{:site/hosted :diagnosis/monthly :report/monthly :content/refresh-monthly
                         :site/rebuild :catalog/managed}
    :plan/for "建て替えて、商品や季節の内容を毎月入れ替える"}])

(def tax-rate 0.10)

(defn plan [id] (first (filter #(= id (:plan/id %)) catalog)))

(defn recommend
  "処方 → 提案するプラン。`:none` には何も勧めない（用が無いので）。"
  [{:keys [action surface]}]
  (case action
    :none nil
    :repair (if (= surface :catalog) :noren.plan/hiraki :noren.plan/mamori)
    :rebuild :noren.plan/hiraki
    nil))

(defn monthly-charge
  "税込月額。`{:net :tax :gross}`。丸めは円未満切り捨て（請求側と一致させる）。"
  [plan-id]
  (when-let [{:plan/keys [price-jpy]} (plan plan-id)]
    (let [tax (long (Math/floor (* price-jpy tax-rate)))]
      {:net price-jpy :tax tax :gross (+ price-jpy tax)})))

;; ── 契約 ─────────────────────────────────────────────────────────────────

(defn activate
  "契約の開始。`:subscription/external-ref` は請求面（Stripe）側の識別子で、
  **無いまま active にしない** —— 課金されていない契約を active と呼ぶと、
  entitlement だけが先に開く。"
  [{:keys [plan-id prospect-key external-ref now]}]
  (when-not external-ref
    (throw (ex-info "external-ref が無い契約は active にしない" {:plan-id plan-id})))
  {:subscription/plan plan-id
   :subscription/prospect prospect-key
   :subscription/external-ref external-ref
   :subscription/state :active
   :subscription/started-at now
   :subscription/service-until nil})

(defn cancel
  "解約。`service-until` までは entitlement が生きる（払った分は使える）。"
  [subscription now service-until]
  (assoc subscription
         :subscription/state :cancelled
         :subscription/cancelled-at now
         :subscription/service-until service-until))

(defn entitled?
  "今日 `capability` を使ってよいか。解約済みで期限も切れていれば false。"
  [{:subscription/keys [state service-until] :as sub} capability now]
  (let [p (plan (:subscription/plan sub))]
    (boolean
     (and sub p
          (contains? (:plan/entitlements p) capability)
          (case state
            :active true
            :cancelled (boolean (and service-until
                                     (when-let [a (prospect/epoch-day now)]
                                       (when-let [b (prospect/epoch-day service-until)]
                                         (<= a b)))))
            false)))))
