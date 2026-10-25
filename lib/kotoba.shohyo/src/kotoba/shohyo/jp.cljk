(ns kotoba.shohyo.jp
  "会社計算規則 — the 区分 a Japanese 貸借対照表 and 損益計算書 must have,
  and the 段階利益 ladder, read from the regulation rather than from custom.

  `kotoba.shohyo` classifies into the five account types and checks the
  accounting equation. That is jurisdiction-neutral and stops short of what a
  Japanese statement actually looks like: 流動 vs 固定, and the ladder from
  売上高 down to 当期純利益.

  Those are not convention. 会社計算規則 (418M60000010013, revision
  418M60000010013_20250331_507M60000010014, retrieved 2026-08-18 from the
  e-Gov law API) states them, and every quote in `provisions` is verbatim.

  ## The rule a naive implementation gets wrong

  第八十九条第二項, and the identical second paragraph in 第九十条, 第九十一条,
  第九十二条 and 第九十四条:

      前項の規定にかかわらず、売上総損益金額が零未満である場合には、
      零から売上総損益金額を減じて得た額を売上総損失金額として
      表示しなければならない。

  A negative 売上総損益金額 is NOT shown as a negative 売上総利益金額. It is
  shown as a **positive 売上総損失金額** — a different label and a sign flip.
  Printing -500 under 売上総利益 is the obvious implementation and it is not
  what the article says, so `stage-profits` returns a `:label` per rung, not
  only a number.

  ## The second rule a naive implementation gets wrong

  第七十六条第二項 makes 自己株式 **a deduction**: 「この場合において、
  第五号に掲げる項目は、控除項目とする。」A chart that adds 自己株式 into
  株主資本 overstates equity by twice the treasury holding, and the balance
  sheet still balances — the error is invisible in the equation. `deduction?`
  answers this per section rather than leaving it to the caller's memory.

  ## Container sections are not classifications

  第七十四条第二項, 第七十六条第二項, 第七十六条第四項, 第七十六条第五項 and
  第七十六条第七項 all say 区分しなければならない / 細分しなければならない.
  An account parked directly on 固定資産 or 株主資本 is therefore not
  classified yet, and `section-problems` says so — `:subdivided-by` marks the
  containers whose subdivision the regulation MANDATES, as distinct from
  第七十六条第六項 and 第八項, which say ことができる and are left alone."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; 貸借対照表 — 第七十三条 to 第七十六条
;; ---------------------------------------------------------------------------

(def bs-sections
  "The sections of 資産の部 / 負債の部 / 純資産の部.

  第七十四条第二項 makes 固定資産 a section that CONTAINS three, so those
  three are `:parent`-linked rather than flattened into peers. 第七十六条 does
  the same thing three levels deep for 純資産の部.

  `:subdivided-by` names the paragraph that makes the subdivision mandatory;
  a section carrying it cannot itself hold accounts. `:deduction` marks
  第七十六条第二項第五号. `:consolidated-only` marks the two items 第七十六条
  第七項ただし書 confines to a 連結貸借対照表."
  {;; 資産の部 — 第七十四条
   :current-assets      {:jp "流動資産"         :type :asset     :provision "第七十四条第一項"}
   :fixed-assets        {:jp "固定資産"         :type :asset     :provision "第七十四条第一項"
                         :subdivided-by "第七十四条第二項"}
   :tangible-fixed      {:jp "有形固定資産"     :type :asset     :parent :fixed-assets :order 1
                         :provision "第七十四条第二項"}
   :intangible-fixed    {:jp "無形固定資産"     :type :asset     :parent :fixed-assets :order 2
                         :provision "第七十四条第二項"}
   :investments-other   {:jp "投資その他の資産" :type :asset     :parent :fixed-assets :order 3
                         :provision "第七十四条第二項"}
   :deferred-assets     {:jp "繰延資産"         :type :asset     :provision "第七十四条第一項"}

   ;; 負債の部 — 第七十五条
   :current-liabilities {:jp "流動負債"         :type :liability :provision "第七十五条"}
   :fixed-liabilities   {:jp "固定負債"         :type :liability :provision "第七十五条"}

   ;; 純資産の部 — 第七十六条第一項第一号（株式会社の貸借対照表）
   :shareholders-equity {:jp "株主資本"         :type :equity
                         :provision "第七十六条第一項第一号イ"
                         :subdivided-by "第七十六条第二項"}
   :valuation-adjustments
   {:jp "評価・換算差額等" :type :equity
    :provision "第七十六条第一項第一号ロ"
    :subdivided-by "第七十六条第七項"}
   :share-subscription-rights
   {:jp "株式引受権"       :type :equity :provision "第七十六条第一項第一号ハ"}
   :subscription-rights-to-shares
   {:jp "新株予約権"       :type :equity :provision "第七十六条第一項第一号ニ"}

   ;; 株主資本の区分 — 第七十六条第二項
   :capital-stock       {:jp "資本金"           :type :equity :parent :shareholders-equity :order 1
                         :provision "第七十六条第二項第一号"}
   :new-share-subscription-deposits
   {:jp "新株式申込証拠金" :type :equity :parent :shareholders-equity :order 2
    :provision "第七十六条第二項第二号"}
   :capital-surplus     {:jp "資本剰余金"       :type :equity :parent :shareholders-equity :order 3
                         :provision "第七十六条第二項第三号"
                         :subdivided-by "第七十六条第四項"}
   :retained-earnings   {:jp "利益剰余金"       :type :equity :parent :shareholders-equity :order 4
                         :provision "第七十六条第二項第四号"
                         :subdivided-by "第七十六条第五項"}
   :treasury-stock      {:jp "自己株式"         :type :equity :parent :shareholders-equity :order 5
                         :provision "第七十六条第二項第五号"
                         :deduction true}
   :treasury-stock-subscription-deposits
   {:jp "自己株式申込証拠金" :type :equity :parent :shareholders-equity :order 6
    :provision "第七十六条第二項第六号"}

   ;; 資本剰余金の区分 — 第七十六条第四項
   :legal-capital-surplus
   {:jp "資本準備金"       :type :equity :parent :capital-surplus :order 1
    :provision "第七十六条第四項第一号"}
   :other-capital-surplus
   {:jp "その他資本剰余金" :type :equity :parent :capital-surplus :order 2
    :provision "第七十六条第四項第二号"}

   ;; 利益剰余金の区分 — 第七十六条第五項
   :legal-retained-earnings
   {:jp "利益準備金"       :type :equity :parent :retained-earnings :order 1
    :provision "第七十六条第五項第一号"}
   :other-retained-earnings
   {:jp "その他利益剰余金" :type :equity :parent :retained-earnings :order 2
    :provision "第七十六条第五項第二号"}

   ;; 評価・換算差額等の細分 — 第七十六条第七項
   :other-securities-valuation-difference
   {:jp "その他有価証券評価差額金" :type :equity :parent :valuation-adjustments :order 1
    :provision "第七十六条第七項第一号"}
   :deferred-hedge-gains-losses
   {:jp "繰延ヘッジ損益"   :type :equity :parent :valuation-adjustments :order 2
    :provision "第七十六条第七項第二号"}
   :land-revaluation-difference
   {:jp "土地再評価差額金" :type :equity :parent :valuation-adjustments :order 3
    :provision "第七十六条第七項第三号"}
   :foreign-currency-translation-adjustment
   {:jp "為替換算調整勘定" :type :equity :parent :valuation-adjustments :order 4
    :provision "第七十六条第七項第四号" :consolidated-only true}
   :retirement-benefits-adjustment
   {:jp "退職給付に係る調整累計額" :type :equity :parent :valuation-adjustments :order 5
    :provision "第七十六条第七項第五号" :consolidated-only true}

   ;; 新株予約権の控除項目 — 第七十六条第八項（「できる」なので任意）
   :treasury-subscription-rights
   {:jp "自己新株予約権"   :type :equity :parent :subscription-rights-to-shares :order 1
    :provision "第七十六条第八項" :deduction true}})

;; ---------------------------------------------------------------------------
;; 損益計算書 — 第八十八条 / 第九十三条
;; ---------------------------------------------------------------------------

(def pl-sections
  "The seven 区分 of 第八十八条第一項, in the order the article lists them,
  followed by the 税等 items 第九十三条 puts 「税引前当期純利益金額…の次に」.

  `:signed` marks 法人税等調整額. Every other section here is a natural
  positive magnitude, but a 調整額 under 税効果会計 has a direction — a
  credit is a negative charge, and forcing it positive would move 当期純利益
  by twice the adjustment."
  {:net-sales             {:jp "売上高"               :type :revenue :order 1
                           :provision "第八十八条第一項第一号"}
   :cost-of-sales         {:jp "売上原価"             :type :expense :order 2
                           :provision "第八十八条第一項第二号"}
   :sga                   {:jp "販売費及び一般管理費" :type :expense :order 3
                           :provision "第八十八条第一項第三号"}
   :non-operating-income  {:jp "営業外収益"           :type :revenue :order 4
                           :provision "第八十八条第一項第四号"}
   :non-operating-expense {:jp "営業外費用"           :type :expense :order 5
                           :provision "第八十八条第一項第五号"}
   :extraordinary-income  {:jp "特別利益"             :type :revenue :order 6
                           :provision "第八十八条第一項第六号"}
   :extraordinary-loss    {:jp "特別損失"             :type :expense :order 7
                           :provision "第八十八条第一項第七号"}
   :income-taxes          {:jp "法人税等"             :type :expense :order 8
                           :provision "第九十三条第一項第一号"}
   :deferred-income-taxes {:jp "法人税等調整額"       :type :expense :order 9
                           :provision "第九十三条第一項第二号" :signed true}
   :global-minimum-tax    {:jp "国際最低課税額に対する法人税等" :type :expense :order 10
                           :provision "第九十三条第二項" :optional true}
   :tax-payment-on-reassessment
   {:jp "法人税等の更正・決定等による納付税額" :type :expense :order 11
    :provision "第九十三条第三項" :optional true}
   :tax-refund-on-reassessment
   {:jp "法人税等の更正・決定等による還付税額" :type :revenue :order 12
    :provision "第九十三条第三項" :optional true}})

(def provisions
  "The articles implemented here, quoted. The standing rule from
  `kotoba-lang/taxlaw` applies: a claim that is ENFORCED must be read."
  {:law/id "418M60000010013"
   :law/title "会社計算規則"
   :law/revision "418M60000010013_20250331_507M60000010014"
   :retrieved-at "2026-08-18"
   :articles
   [{:article "第七十三条" :on :bs-parts
     :quote "貸借対照表等は、次に掲げる部に区分して表示しなければならない。一 資産 二 負債 三 純資産"}
    {:article "第七十四条第一項" :on :asset-sections
     :quote "資産の部は、次に掲げる項目に区分しなければならない。…一 流動資産 二 固定資産 三 繰延資産"}
    {:article "第七十四条第二項" :on :fixed-asset-sections
     :quote "固定資産に係る項目は、次に掲げる項目に区分しなければならない。…一 有形固定資産 二 無形固定資産 三 投資その他の資産"}
    {:article "第七十六条第一項第一号" :on :equity-sections
     :quote (str "純資産の部は、次の各号に掲げる貸借対照表等の区分に応じ、当該各号に定める項目に"
                 "区分しなければならない。一 株式会社の貸借対照表 次に掲げる項目 "
                 "イ 株主資本 ロ 評価・換算差額等 ハ 株式引受権 ニ 新株予約権")}
    {:article "第七十六条第二項" :on :shareholders-equity-sections
     :quote (str "株主資本に係る項目は、次に掲げる項目に区分しなければならない。この場合において、"
                 "第五号に掲げる項目は、控除項目とする。一 資本金 二 新株式申込証拠金 "
                 "三 資本剰余金 四 利益剰余金 五 自己株式 六 自己株式申込証拠金")}
    {:article "第七十六条第四項" :on :capital-surplus-sections
     :quote (str "株式会社の貸借対照表の資本剰余金に係る項目は、次に掲げる項目に区分しなければ"
                 "ならない。一 資本準備金 二 その他資本剰余金")}
    {:article "第七十六条第五項" :on :retained-earnings-sections
     :quote (str "株式会社の貸借対照表の利益剰余金に係る項目は、次に掲げる項目に区分しなければ"
                 "ならない。一 利益準備金 二 その他利益剰余金")}
    {:article "第七十六条第七項" :on :valuation-adjustment-sections
     :quote (str "評価・換算差額等又はその他の包括利益累計額に係る項目は、次に掲げる項目その他"
                 "適当な名称を付した項目に細分しなければならない。ただし、第四号及び第五号に"
                 "掲げる項目は、連結貸借対照表に限る。一 その他有価証券評価差額金 "
                 "二 繰延ヘッジ損益 三 土地再評価差額金 四 為替換算調整勘定 "
                 "五 退職給付に係る調整累計額")}
    {:article "第八十八条第一項" :on :pl-sections
     :quote "損益計算書等は、次に掲げる項目に区分して表示しなければならない。…一 売上高 二 売上原価 三 販売費及び一般管理費 四 営業外収益 五 営業外費用 六 特別利益 七 特別損失"}
    {:article "第八十九条" :on :gross
     :quote "売上高から売上原価を減じて得た額（以下「売上総損益金額」という。）は、売上総利益金額として表示しなければならない。２ …零未満である場合には、零から売上総損益金額を減じて得た額を売上総損失金額として表示しなければならない。"}
    {:article "第九十条" :on :operating
     :quote "売上総損益金額から販売費及び一般管理費の合計額を減じて得た額（以下「営業損益金額」という。）は、営業利益金額として表示しなければならない。２ …零未満である場合には、…営業損失金額として表示しなければならない。"}
    {:article "第九十一条" :on :ordinary
     :quote "営業損益金額に営業外収益を加えて得た額から営業外費用を減じて得た額（以下「経常損益金額」という。）は、経常利益金額として表示しなければならない。２ …零未満である場合には、…経常損失金額として表示しなければならない。"}
    {:article "第九十二条" :on :pretax
     :quote "経常損益金額に特別利益を加えて得た額から特別損失を減じて得た額（以下「税引前当期純損益金額」という。）は、税引前当期純利益金額…として表示しなければならない。２ …零未満である場合には、…税引前当期純損失金額…として表示しなければならない。"}
    {:article "第九十三条第一項" :on :taxes
     :quote (str "次に掲げる項目の金額は、その内容を示す名称を付した項目をもって、税引前当期純利益"
                 "金額又は税引前当期純損失金額…の次に表示しなければならない。"
                 "一 当該事業年度…に係る法人税等 二 法人税等調整額（税効果会計の適用により"
                 "計上される前号に掲げる法人税等の調整額をいう。）")}
    {:article "第九十三条第三項" :on :reassessment
     :quote (str "法人税等の更正、決定等による納付税額又は還付税額がある場合には、第一項第一号に"
                 "掲げる項目及び国際最低課税額項目の次に、その内容を示す名称を付した項目をもって"
                 "表示するものとする。…")}
    {:article "第九十四条" :on :net-income
     :quote (str "第一号及び第二号に掲げる額の合計額から第三号及び第四号に掲げる額の合計額を減じて"
                 "得た額（以下「当期純損益金額」という。）は、当期純利益金額として表示しなければ"
                 "ならない。一 税引前当期純損益金額 二 前条第三項に規定する場合…において、"
                 "還付税額があるときは、当該還付税額 三 前条第一項各号に掲げる項目の金額…"
                 "四 前条第三項に規定する場合…において、納付税額があるときは、当該納付税額 "
                 "２ 前項の規定にかかわらず、当期純損益金額が零未満である場合には、零から"
                 "当期純損益金額を減じて得た額を当期純損失金額として表示しなければならない。")}]})

(defn known-section? [s]
  (or (contains? bs-sections s) (contains? pl-sections s)))

(defn section-of [s] (or (bs-sections s) (pl-sections s)))

(defn deduction?
  "Is this section a 控除項目 — subtracted from its parent rather than added?

  第七十六条第二項後段 (自己株式) and 第七十六条第八項 (自己新株予約権). A
  caller that sums its children without asking overstates 純資産 by twice the
  holding, and the accounting equation still holds."
  [s]
  (boolean (:deduction (section-of s))))

(defn consolidated-only?
  "第七十六条第七項ただし書 — 為替換算調整勘定 and 退職給付に係る調整累計額 are
  「連結貸借対照表に限る」."
  [s]
  (boolean (:consolidated-only (section-of s))))

(defn requires-subdivision?
  "Does the regulation MANDATE subdividing this section (区分／細分しなければ
  ならない), making it a container rather than a place to put an account?

  第七十六条第六項 and 第八項 say ことができる and are deliberately absent."
  [s]
  (boolean (:subdivided-by (section-of s))))

(defn subsections
  "The sections whose `:parent` is `s`, **in the order the article numbers
  them** (`:order` = the 号).

  Not map order. `bs-sections` has more than eight entries, so it is a
  hash-map and its seq order is unspecified — a subdivision listed back to
  the caller in hash order reads as if the regulation numbered it that way."
  [s]
  (->> bs-sections
       (keep (fn [[k v]] (when (= s (:parent v)) [(:order v 0) k])))
       (sort-by first)
       (mapv second)))

(defn section-problems
  "Sections the regulation does not name, sections whose declared account
  type contradicts the article, accounts parked on a container the regulation
  says must be subdivided, and 連結-only sections used on a standalone sheet.

  The type conflict is the one worth having first: tagging 売上原価 as
  `:revenue` would put it on the wrong side of 第八十九条, and the gross
  figure would come out looking right and being wrong.

  `opts` takes `{:consolidated? true}`. **The default is standalone**, which
  is the strict reading — 第七十六条第七項ただし書 confines two sections to a
  連結貸借対照表, so assuming consolidation would silently permit them on a
  sheet that may not carry them."
  ([chart] (section-problems chart nil))
  ([chart {:keys [consolidated?]}]
   (vec
    (mapcat
     (fn [[account {:keys [section type]}]]
       (if (nil? section)
         []
         (if-not (known-section? section)
           [{:account account :problem :unknown-section :section section}]
           (let [spec     (section-of section)
                 declared (:type spec)]
             (cond-> []
               (and type (not= type declared))
               (conj {:account account :problem :section-type-conflict :section section
                      :detail (str (name section) " is " (name declared)
                                   " under 会社計算規則, not " (name type))})

               (requires-subdivision? section)
               (conj {:account account :problem :section-requires-subdivision
                      :section section
                      :detail (str (name section) " must be subdivided per "
                                   (:subdivided-by spec)
                                   "; classify into one of "
                                   (str/join ", " (map name (subsections section))))})

               (and (consolidated-only? section) (not consolidated?))
               (conj {:account account :problem :consolidated-only-section
                      :section section
                      :detail (str (name section)
                                   " is 連結貸借対照表に限る per 第七十六条第七項ただし書")}))))))
     chart))))

;; ---------------------------------------------------------------------------
;; 段階利益 — 第八十九条 to 第九十四条
;; ---------------------------------------------------------------------------

(defn- rung [amount profit-label loss-label article]
  ;; 第八十九条第二項 and its siblings: below zero it is not a negative
  ;; profit. It is a positive LOSS under a different name.
  (if (neg? amount)
    {:amount (- amount) :label loss-label :sign :loss :article article}
    {:amount amount :label profit-label :sign :profit :article article}))

(def ^:private ladder-sections
  [:net-sales :cost-of-sales :sga
   :non-operating-income :non-operating-expense
   :extraordinary-income :extraordinary-loss])

(def ^:private tax-sections
  "第九十三条第一項 — both 号 are 表示しなければならない, so neither is
  optional once the ladder goes past 税引前."
  [:income-taxes :deferred-income-taxes])

(def ^:private conditional-tax-sections
  "第九十三条第二項 (ある場合における…できる) and 第三項 (…がある場合には).
  Both are conditioned on the amount EXISTING, so absent really is zero here
  — unlike `tax-sections`, where absent means unstated."
  [:global-minimum-tax :tax-payment-on-reassessment :tax-refund-on-reassessment])

(defn- net-income-rung
  "第九十四条第一項: (税引前当期純損益金額 + 還付税額) − (第九十三条第一項各号
  + 国際最低課税額項目 + 納付税額).

  Returns `:not-declared` naming the missing 税等 rather than treating an
  unstated tax charge as a zero one — a company with no 法人税等 line and a
  company that pays none produce the same 当期純利益 otherwise."
  [section-totals pretax]
  (let [missing (vec (remove #(contains? section-totals %) tax-sections))]
    (if (seq missing)
      {:shohyo.jp/coverage :not-declared
       :shohyo.jp/missing-sections missing
       :shohyo.jp/why "第九十三条第一項 requires both 税等 items; absent is not zero"}
      (let [g   (fn [k] (get section-totals k 0))
            net (- (+ pretax (g :tax-refund-on-reassessment))
                   (+ (g :income-taxes)
                      (g :deferred-income-taxes)
                      (g :global-minimum-tax)
                      (g :tax-payment-on-reassessment)))]
        (assoc (rung net "当期純利益金額" "当期純損失金額" "第九十四条")
               :shohyo.jp/coverage :checked)))))

(defn stage-profits
  "The ladder of 第八十九条 → 第九十四条 from section totals.

  `section-totals` is `{section-keyword amount}` in natural positive
  magnitudes — 売上原価 is the cost, not a negative revenue. **法人税等調整額
  is the exception and is signed** (第九十三条第一項第二号 calls it a 調整額),
  so a 税効果 credit is passed as a negative and increases 当期純利益.

  `:not-declared` when a section the ladder needs is absent, naming which.
  **A missing 売上原価 is not zero cost, it is an unstated one**, and
  treating it as zero would report a gross profit equal to sales.

  `:shohyo.jp/net-income` carries its own coverage: the four rungs down to
  税引前 are `:checked` as soon as the 第八十八条 sections are present, and
  the fifth is reported `:not-declared` on its own when 法人税等 /
  法人税等調整額 are not. Running out of inputs one rung early is not the
  same as the ladder failing, and the two must not read alike."
  [section-totals]
  (let [missing (vec (remove #(contains? section-totals %) ladder-sections))]
    (if (seq missing)
      {:shohyo.jp/coverage :not-declared
       :shohyo.jp/missing-sections missing
       :shohyo.jp/why "a section the ladder needs was not declared; absent is not zero"}
      (let [g   (- (:net-sales section-totals) (:cost-of-sales section-totals))
            o   (- g (:sga section-totals))
            ord (- (+ o (:non-operating-income section-totals))
                   (:non-operating-expense section-totals))
            pre (- (+ ord (:extraordinary-income section-totals))
                   (:extraordinary-loss section-totals))
            ni  (net-income-rung section-totals pre)]
        {:shohyo.jp/coverage :checked
         :shohyo.jp/gross      (rung g   "売上総利益金額"       "売上総損失金額"       "第八十九条")
         :shohyo.jp/operating  (rung o   "営業利益金額"         "営業損失金額"         "第九十条")
         :shohyo.jp/ordinary   (rung ord "経常利益金額"         "経常損失金額"         "第九十一条")
         :shohyo.jp/pretax     (rung pre "税引前当期純利益金額" "税引前当期純損失金額" "第九十二条")
         :shohyo.jp/net-income ni
         ;; kanjō's canonical concepts, signed, so an internally-produced
         ;; ladder and an externally-read filing line up. net-income appears
         ;; only when it was actually computed.
         :shohyo.jp/concepts
         (cond-> {"gross-profit" g "operating-income" o
                  "ordinary-income" ord "pretax-income" pre}
           (= :checked (:shohyo.jp/coverage ni))
           (assoc "net-income" (if (= :loss (:sign ni)) (- (:amount ni)) (:amount ni))))}))))
