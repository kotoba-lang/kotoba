(ns kotoba.shohyo.genka
  "売上原価の内訳 and the 製造原価明細書 — the statement `kotoba.shohyo.jp`
  has no section for, and the one place in this library where the authority
  runs out partway down.

  `kotoba.shohyo.jp` implements 会社計算規則, which names 売上原価 as one of
  the seven 区分 of 第八十八条第一項 and stops there. It says nothing about
  what is inside it. A manufacturer's chart therefore has nowhere to put
  期首材料棚卸高, 労務費 or 仕掛品, and every such account comes back
  `:unknown-section`.

  Measured 2026-08-20 against the live MoneyForward chart for one 製造業
  株式会社: **35 of 200 accounts across 10 categories** were in exactly this
  position.

  ## Two levels of authority, and they are not the same

  **第七十五条第一項 is law and is read.** 財務諸表等規則
  (338M50000040059, revision `..._20260807_508M60000002070`, retrieved
  2026-08-20 from the e-Gov law API) states the three 科目 売上原価 is shown
  as, and makes the third a 控除科目. `provisions` quotes it verbatim.

  **The 材料費 / 労務費 / 経費 breakdown beneath it is NOT law and is NOT
  read.** 第七十五条第二項 requires 「その内訳を記載した明細書」 and does not
  say what the 内訳 is; searched for in the full text of the regulation,
  材料費 and 労務費 occur **zero** times. The three-way split comes from
  原価計算基準 (企業会計審議会, 1962) — a pronouncement, not a 法令, and
  therefore not on the law API this library reads from.

  So `cost-report-sections` carries `:source :observed`, not `:source
  :statute`, and `cost-of-goods-manufactured` returns
  `:genka/authority-not-read` alongside its figure. The number is produced —
  refusing to produce it helps nobody — but nothing here lets a reader mistake
  it for a figure this library checked against a statute, which is what every
  other number in `kotoba.shohyo` is.

  ## The rule a naive implementation gets wrong, again

  第七十五条第一項第三号 is a **控除科目**: 「これらの科目に対する控除科目
  としての第三号の項目」. 期末棚卸高 is subtracted. Adding it overstates
  売上原価 by twice the closing stock, and — exactly like 自己株式 under
  会社計算規則 第七十六条第二項 — **the accounting equation still holds**, so
  `out-of-balance` never sees it. 期末仕掛品棚卸高 and 他勘定振替高 sit the
  same way inside the 明細書.")

;; ---------------------------------------------------------------------------
;; 売上原価 — 財務諸表等規則 第七十五条第一項。法令であり、読んである
;; ---------------------------------------------------------------------------

(def provisions
  {:law/id "338M50000040059"
   :law/title "財務諸表等の用語、様式及び作成方法に関する規則"
   :law/revision "338M50000040059_20260807_508M60000002070"
   :retrieved-at "2026-08-20"
   :articles
   [{:article "第七十五条第一項" :on :cogs-items
     :quote (str "売上原価に属する項目は、第一号及び第二号の項目を示す名称を付した科目"
                 "並びにこれらの科目に対する控除科目としての第三号の項目を示す名称を"
                 "付した科目をもつて掲記しなければならない。"
                 "一 商品又は製品（半製品、副産物、作業くず等を含む。以下この項及び"
                 "次条において同じ。）の期首棚卸高 "
                 "二 当期商品仕入高又は当期製品製造原価 "
                 "三 商品又は製品の期末棚卸高")}
    {:article "第七十五条第二項" :on :cost-report
     :quote (str "前項第二号の当期製品製造原価については、その内訳を記載した明細書を"
                 "損益計算書に添付しなければならない。ただし、連結財務諸表において、"
                 "連結財務諸表規則第十五条の二第一項に規定するセグメント情報を注記して"
                 "いる場合は、この限りでない。")}]})

(def cogs-items
  "The three 科目 of 第七十五条第一項. The third is a 控除科目 — the article
  says so in the same sentence that names the other two."
  {:beginning-inventory
   {:jp "商品又は製品の期首棚卸高" :order 1 :provision "第七十五条第一項第一号"}
   :purchases-or-cost-of-goods-manufactured
   {:jp "当期商品仕入高又は当期製品製造原価" :order 2 :provision "第七十五条第一項第二号"
    :requires-schedule "第七十五条第二項"}
   :ending-inventory
   {:jp "商品又は製品の期末棚卸高" :order 3 :provision "第七十五条第一項第三号"
    :deduction true}})

(def ^:private cogs-required (vec (sort (keys cogs-items))))

(defn cost-of-sales
  "売上原価 from the three 科目 of 第七十五条第一項.

  `:not-declared` naming what is absent. A missing 期末棚卸高 is not a zero
  one — read as zero it inflates 売上原価 by the whole closing stock, and the
  ladder in `kotoba.shohyo.jp` carries that error all the way to 当期純利益."
  [totals]
  (let [missing (vec (remove #(contains? totals %) cogs-required))]
    (if (seq missing)
      {:genka/coverage :not-declared
       :genka/missing missing
       :genka/why "第七十五条第一項 names three 科目; absent is not zero"}
      {:genka/coverage :checked
       :genka/cost-of-sales (- (+ (:beginning-inventory totals)
                                  (:purchases-or-cost-of-goods-manufactured totals))
                               (:ending-inventory totals))
       :genka/article "第七十五条第一項"})))

;; ---------------------------------------------------------------------------
;; 製造原価明細書 — 第七十五条第二項 が「明細書」を要求する。
;; その中身は 原価計算基準 のものであり、法令ではない = 読んでいない
;; ---------------------------------------------------------------------------

(def authority
  "What backs the shape below, stated so a reader does not have to infer it."
  {:genka/mandated-by "財務諸表等規則 第七十五条第二項"
   :genka/mandated-what "当期製品製造原価の内訳を記載した明細書を添付すること"
   :genka/shape-from "原価計算基準（企業会計審議会 1962）"
   :genka/shape-read? false
   :genka/why-not-read
   (str "原価計算基準 is an 企業会計審議会 pronouncement, not a 法令, and is not "
        "served by the e-Gov law API this library reads from. 材料費 and 労務費 "
        "occur zero times in the full text of 財務諸表等規則.")
   :genka/shape-observed-from
   "the MoneyForward chart of accounts for one 製造業 株式会社, 2026-08-20"})

(def cost-report-sections
  "The 明細書's sections. `:source :observed` on every one of them — see
  `authority`. `:deduction` marks the two that are subtracted."
  {:beginning-materials
   {:jp "期首材料棚卸高" :group :materials :order 1 :source :observed}
   :material-purchases
   {:jp "当期材料仕入高" :group :materials :order 2 :source :observed}
   :ending-materials
   {:jp "期末材料棚卸高" :group :materials :order 3 :source :observed :deduction true}
   :labor-costs
   {:jp "労務費"         :group :labor     :order 1 :source :observed}
   :manufacturing-overhead
   {:jp "経費"           :group :overhead  :order 1 :source :observed}
   :beginning-work-in-process
   {:jp "期首仕掛品棚卸高" :group :work-in-process :order 1 :source :observed}
   :ending-work-in-process
   {:jp "期末仕掛品棚卸高" :group :work-in-process :order 2 :source :observed
    :deduction true}
   :transfers-to-other-accounts
   {:jp "他勘定振替高"   :group :transfers :order 1 :source :observed :deduction true}})

(defn deduction?
  "Is this item subtracted rather than added? Covers both maps."
  [k]
  (boolean (:deduction (or (cogs-items k) (cost-report-sections k)))))

(def ^:private cost-report-required
  (vec (sort (keys cost-report-sections))))

(defn cost-of-goods-manufactured
  "当期製品製造原価 from the 明細書's sections.

      当期材料費   = 期首材料 + 当期材料仕入 − 期末材料
      当期総製造費用 = 当期材料費 + 労務費 + 経費
      当期製品製造原価 = 当期総製造費用 + 期首仕掛品 − 期末仕掛品 − 他勘定振替高

  **The figure is produced and the result says it is not statute-checked.**
  `:genka/authority` travels with it. Every other number in `kotoba.shohyo`
  is backed by a quoted article; this one is backed by a pronouncement this
  library has not read, and a caller must be able to tell the two apart
  without going and looking.

  `:not-declared` naming what is absent, on the same reasoning as everywhere
  else here: an unstated 期末仕掛品棚卸高 read as zero inflates the figure by
  the whole closing balance."
  [totals]
  (let [missing (vec (remove #(contains? totals %) cost-report-required))]
    (if (seq missing)
      {:genka/coverage :not-declared
       :genka/missing missing
       :genka/why "the 明細書 needs every section; absent is not zero"
       :genka/authority authority}
      (let [materials (- (+ (:beginning-materials totals)
                            (:material-purchases totals))
                         (:ending-materials totals))
            total-mfg (+ materials (:labor-costs totals) (:manufacturing-overhead totals))
            cogm (- (+ total-mfg (:beginning-work-in-process totals))
                    (:ending-work-in-process totals)
                    (:transfers-to-other-accounts totals))]
        {:genka/coverage :checked-arithmetic-only
         :genka/materials materials
         :genka/total-manufacturing-cost total-mfg
         :genka/cost-of-goods-manufactured cogm
         :genka/authority authority}))))
