(ns okugai.pricing
  "屋外広告の**参考見積**モデル（媒体非依存）。料金表そのものは媒体 repo が持つ
  （電柱なら `denchu.pricing/rate-cards`）—— ここは『どう計算し、何を不明として
  返すか』だけを決める。

  設計判断: この ns が返す金額は常に `:indicative`（参考）。屋外広告の実額は
  掲出地域・地点条件・掲出面・期間で変わり、最終的には媒体社/代理店の見積でしか
  確定しない。したがって:

  - 料金表は**公開されている数値だけ**を、税区分・改定日・出典 URL 付きで持つ
  - 地域区分が分からない見積は `:quote/total nil` を返し、何が足りないかを
    `:quote/unknowns` に列挙する。**足りない値を平均や中央値で埋めない**
  - 税抜/税込を混ぜて合算しない"
  (:require [kotoba.lang.text :as str]))

(defn rate-card?
  [c]
  (and (map? c)
       (string? (:rate/source-url c))
       (string? (:rate/as-of c))
       (contains? #{:included :excluded} (:rate/tax c))))

(defn zone-monthly
  "料金表 × 地域区分 → 月額。区分表を公開していない料金表では nil。"
  [card zone]
  (let [zones (:rate/zones card)]
    (when (map? zones) (get-in zones [zone :zone/monthly]))))

(defn- missing
  [card zone units months]
  (cond-> []
    (nil? card) (conj "rate-card が未収録（この媒体社の公開料金を調べる）")
    (and card (not (rate-card? card))) (conj "rate-card に出典・改定日・税区分のいずれかが無い")
    (and card (not (map? (:rate/zones card))) (nil? (:rate/monthly-from card)))
    (conj "月額の公開値が無い")
    (and card (map? (:rate/zones card)) (nil? zone))
    (conj "地域区分 (zone) が未指定 — 掲載地域が決まらないと月額が決まらない")
    (and card (map? (:rate/zones card)) zone (nil? (zone-monthly card zone)))
    (conj (str "地域区分 " zone " が料金表に無い"))
    (and card (= :not-published (:rate/setup card)))
    (conj "製作・設置費が非公開（媒体社見積で確定する）")
    (not (pos-int? units)) (conj "units は正の整数")
    (not (pos-int? months)) (conj "months は正の整数")))

(defn quote-order
  "参考見積。`{:rate-card <card> :zone :A :units 3 :months 12}`
  戻り値は必ず `:quote/confidence :indicative`。総額を出せない場合は
  `:quote/total nil` と `:quote/unknowns` を返し、推定値で埋めない。"
  [{:keys [rate-card zone units months medium]}]
  (let [card rate-card
        unknowns (missing card zone units months)
        monthly (when card
                  (or (zone-monthly card zone)
                      (when-not (map? (:rate/zones card)) (:rate/monthly-from card))))
        setup (when card (let [s (:rate/setup card)] (when (number? s) s)))
        computable? (and (empty? unknowns) monthly)
        monthly-total (when computable? (* monthly units months))
        setup-total (when (and computable? setup) (* setup units))]
    {:quote/medium medium
     :quote/agency-rate (:rate/agency card)
     :quote/zone zone
     :quote/units units
     :quote/months months
     :quote/currency (when card (:rate/currency card))
     :quote/tax (when card (:rate/tax card))
     :quote/monthly-per-unit monthly
     :quote/monthly-total monthly-total
     :quote/setup-per-unit setup
     :quote/setup-total setup-total
     :quote/total (when (and monthly-total (or setup-total (nil? setup)))
                    (+ monthly-total (or setup-total 0)))
     :quote/confidence :indicative
     :quote/basis (when card (select-keys card [:rate/source-url :rate/as-of
                                                :rate/effective-from :rate/tax]))
     :quote/unknowns (vec unknowns)
     :quote/note "参考値。実額は媒体社／代理店の見積でのみ確定する。"}))

(defn quote-summary
  [q]
  (if (:quote/total q)
    (str (:quote/units q) "件 × " (:quote/months q) "ヶ月 = "
         (:quote/total q) " " (:quote/currency q)
         " (" (name (or (:quote/tax q) :unknown)) ", indicative, 出典 "
         (get-in q [:quote/basis :rate/source-url]) ")")
    (str "見積不能: " (str/join " / " (:quote/unknowns q)))))
