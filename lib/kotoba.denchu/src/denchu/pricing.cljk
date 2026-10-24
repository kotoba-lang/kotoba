(ns denchu.pricing
  "電柱広告の料金モデルと**参考見積**。

  重要な設計判断: この ns が返す金額は常に `:indicative`（参考）である。
  電柱広告の実額は掲載地域・柱の条件・掲出面で変わり、最終的には代理店の
  見積でしか確定しない。したがって:

  - 料金表 (`rate-cards`) は**代理店が公開している数値だけ**を、税区分・
    改定日・出典 URL 付きで持つ。
  - 地域区分が分からない見積は `:quote/total nil` を返し、何が足りないかを
    `:quote/unknowns` に列挙する。**足りない値を平均や中央値で埋めない。**
  - 税抜/税込を混ぜて合算しない。混在は `:quote/unknowns` になる。"
  (:require [kotoba.lang.text :as str]))

(def rate-cards
  "代理店 id → 公開料金表。ここに無い代理店の料金は不明であって 0 ではない。"
  {:tepco-town-planning
   {:rate/agency :tepco-town-planning
    :rate/currency "JPY"
    :rate/tax :included
    :rate/monthly-from 2640
    :rate/monthly-note "「月々2,640円（税込）～」。広告料金は掲載地域によって異なる。"
    :rate/zones :not-published
    :rate/setup :not-published
    :rate/source-url "https://www.ttplan.co.jp/service/ad_pole/"
    :rate/as-of "2026-08-04"}

   :telwel-east-higashikanto
   {:rate/agency :telwel-east
    :rate/branch "東関東支店（千葉エリア）"
    :rate/currency "JPY"
    :rate/tax :excluded
    :rate/effective-from "2025-06-01"
    :rate/zones {:A {:zone/monthly 2800 :zone/areas ["市川市" "浦安市"]}
                 :B {:zone/monthly 2600 :zone/areas ["千葉市" "四街道市ほか"]}
                 :C {:zone/monthly 2400 :zone/areas ["野田市" "我孫子市ほか"]}
                 :D {:zone/monthly 2200 :zone/areas ["袖ケ浦市" "木更津市ほか"]}
                 :E {:zone/monthly 2000 :zone/areas ["上記以外"]}}
    :rate/setup 15000
    :rate/setup-note "製作費15,000円（税抜）。取り付け費用を含む。"
    :rate/coverage "千葉県全域（A〜E地域）"
    :rate/source-url "https://www.telwel-east.co.jp/denchu-koukoku/fee/"
    :rate/as-of "2026-08-04"}})

(defn rate-card [id] (get rate-cards id))

(defn zone-monthly
  "料金表 × 地域区分 → 月額。区分表を公開していない料金表では nil。"
  [card zone]
  (let [zones (:rate/zones card)]
    (when (map? zones)
      (get-in zones [zone :zone/monthly]))))

(defn- missing
  [card zone units months]
  (cond-> []
    (nil? card) (conj "rate-card が未収録（この代理店の公開料金を調べる）")
    (and card (not (map? (:rate/zones card))) (nil? (:rate/monthly-from card)))
    (conj "月額の公開値が無い")
    (and card (map? (:rate/zones card)) (nil? zone))
    (conj "地域区分 (zone) が未指定 — 掲載地域が決まらないと月額が決まらない")
    (and card (map? (:rate/zones card)) zone (nil? (zone-monthly card zone)))
    (conj (str "地域区分 " zone " が料金表に無い"))
    (and card (= :not-published (:rate/setup card)))
    (conj "製作・取付費が非公開（代理店見積で確定する）")
    (not (pos-int? units)) (conj "units は正の整数")
    (not (pos-int? months)) (conj "months は正の整数")))

(defn quote-order
  "参考見積。`{:agency-rate <rate-card id> :zone :A :units 3 :months 12}`

  戻り値は必ず `:quote/confidence :indicative`。総額を出せない場合は
  `:quote/total nil` と `:quote/unknowns` を返し、**推定値で埋めない**。"
  [{:keys [agency-rate zone units months]}]
  (let [card (rate-card agency-rate)
        unknowns (missing card zone units months)
        monthly (when card
                  (or (zone-monthly card zone)
                      (when-not (map? (:rate/zones card)) (:rate/monthly-from card))))
        setup (when card (let [s (:rate/setup card)] (when (number? s) s)))
        computable? (and (empty? unknowns) monthly)
        monthly-total (when computable? (* monthly units months))
        setup-total (when (and computable? setup) (* setup units))]
    {:quote/agency-rate agency-rate
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
     :quote/floor? (and card (map? (:rate/zones card)) (nil? zone))
     :quote/confidence :indicative
     :quote/basis (when card (select-keys card [:rate/source-url :rate/as-of
                                                :rate/effective-from :rate/tax]))
     :quote/unknowns (vec unknowns)
     :quote/note "参考値。実額は代理店見積でのみ確定する。"}))

(defn quote-summary
  "監査ログ用の一行。金額が出せなかったことも明示的に書く。"
  [q]
  (if (:quote/total q)
    (str (:quote/units q) "本 × " (:quote/months q) "ヶ月 = "
         (:quote/total q) " " (:quote/currency q)
         " (" (name (or (:quote/tax q) :unknown)) ", indicative, 出典 "
         (get-in q [:quote/basis :rate/source-url]) ")")
    (str "見積不能: " (str/join " / " (:quote/unknowns q)))))
