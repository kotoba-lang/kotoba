(ns kotoba.shohyo.renketsu
  "連結計算書類 — a group's statements, folded from its members' statements.

  `kotoba.shohyo` folds ONE entity's trial balance. `kotoba.shohyo.jp` says
  what a Japanese statement looks like; `kotoba.shohyo.ifrs` what an IFRS one
  looks like. This says what happens when there is more than one entity, and
  like both of those it is the caller's choice: **the core stays
  single-entity and knows nothing about groups.**

  ## The sentence this library exists for, with a group in it

  The core's refusal is:

      A balance sheet that omits an account still balances. It is wrong, it
      looks right, and nothing about the output says which.

  Consolidation is that sentence twice over. **A consolidated balance sheet
  that omits a subsidiary still balances.** So does one that fails to
  eliminate an intercompany receivable against its payable. Both are wrong,
  both look right, and a total is not enough to find either — so the scope is
  an argument, and what did not eliminate is NAMED, never counted.

  ## What was read

  Four texts, all from the e-Gov law API on 2026-08-18, all quoted verbatim
  in `provisions`:

  | | |
  |---|---|
  | 会社法 第四百四十四条 | 417AC0000000086, rev `..._20260812_508AC0000000064` |
  | 会社計算規則 第六十一〜六十九条, 第七十六条, 第九十四条 | 418M60000010013, rev `..._20250331_507M60000010014` |
  | 会社法施行規則 第三条 | 418M60000010012, rev `..._20240401_506M60000010011` |
  | 連結財務諸表規則 第五条, 第九条 | 351M50000040028, rev `..._20260331_508M60000002028` |

  ## The thing everybody quotes that the regulation does not say

  Every textbook says consolidation eliminates 内部取引高 and 債権債務.
  **Neither phrase occurs in 会社計算規則.** Measured, not assumed: across
  its 180 articles the strings 内部取引, 債権債務 and 未実現 occur **zero**
  times. 連結財務諸表規則 is the same — 内部取引 and 未実現 zero times, and
  its one 債権債務 is in 第十五条の四の二, a related-party *note*, not an
  elimination rule.

  What the regulation actually says is 第六十八条, and it is general:

      連結計算書類の作成に当たっては、連結子会社の資産及び負債の評価並びに
      株式会社の連結子会社に対する投資とこれに対応する当該連結子会社の資本
      との相殺消去その他必要とされる連結会社相互間の項目の相殺消去を
      しなければならない。

  Only 投資と資本 is named. Everything else is 「その他必要とされる連結会社
  相互間の項目の相殺消去」. So the elimination this module performs is
  authorised by that general clause and by nothing more specific, and the
  itemised vocabulary comes from 企業会計基準第22号, an ASBJ standard that is
  not on e-Gov and **was not read**. `catalog-verification` records that, and
  it is why 未実現損益 is refused rather than approximated.

  ## The rule a naive implementation gets wrong

  第六十三条第一項 and its ただし書:

      株式会社は、その全ての子会社を連結の範囲に含めなければならない。
      ただし、次のいずれかに該当する子会社は、連結の範囲に含めないもの
      とする。

  and 第二項:

      …重要性の乏しいものは、連結の範囲から除くことができる。

  These are **two different modalities and the obvious implementation flattens
  them into one**. 第一項's two grounds are 「含めないものとする」 — the
  subsidiary MUST be left out. 第二項's materiality ground is 「除くことが
  できる」 — the entity MAY leave it out. A model with one `:excludable?` flag
  lets a caller consolidate a subsidiary whose control is temporary, which the
  regulation forbids, and the consolidated statement balances anyway.

  So `exclusion-grounds` carries `:modality`, and a mandatory ground declared
  alongside `:included` is a scope problem.

  ## The second rule a naive implementation gets wrong

  Control is not a percentage. 会社法施行規則 第三条第三項 opens its own
  definition with an exception:

      前二項に規定する「財務及び事業の方針の決定を支配している場合」とは、
      次に掲げる場合（財務上又は事業上の関係からみて他の会社等の財務又は
      事業の方針の決定を支配していないことが明らかであると認められる場合を
      除く。）をいう

  so a holding over 百分の五十 is not sufficient; and 第三項第三号 reaches
  「自己の計算において議決権を所有していない場合を含み」 — **zero** voting
  rights — where 自己所有等議決権数, which counts 緊密な関係 parties and
  those who have agreed to vote alike, exceeds half. So a holding is not
  necessary either.

  None of 緊密な関係, 同意している者, 支配する契約等 or 「支配していることが
  推測される事実」 appears in a trial balance. **A library cannot observe
  control.** `:renketsu/control` is therefore a required declaration, a
  declared `:renketsu/voting-rights` does not substitute for it, and an
  undeclared scope is its own answer rather than a pass — the same discipline
  as `ifrs`'s `:presentation-method-not-declared` and `taxlaw`'s `:none`.

  ## What a group declares

      {:renketsu/parent \"P\"
       :renketsu/members
       {\"P\"  {:renketsu/role :parent :renketsu/statements <core result>}
        \"S1\" {:renketsu/role :subsidiary
                :renketsu/control :controlled
                :renketsu/inclusion :included
                :renketsu/ownership [1 1]
                :renketsu/statements <core result>}}
       :renketsu/intercompany
       [{:renketsu/pair \"loan\"
         :renketsu/legs [{:renketsu/entity \"P\"  :account \"due-from-s1\" :currency \"JPY\"}
                         {:renketsu/entity \"S1\" :account \"due-to-p\"    :currency \"JPY\"}]}]
       :renketsu/unrealised-profit {:renketsu/present? false}}

  `:renketsu/ownership` is `[numerator denominator]`, two integers. Not a
  ratio and not a decimal: **ClojureScript has no distinct float type** —
  `1.0` reads as `1` and `(str -0.0)` is `\"0\"` — and money is arithmetic, so
  nothing in this module divides. Wholly owned is `(= numerator denominator)`,
  which is exact in both runtimes.

  A chart may tag an account `:renketsu/counterparty`. The core forwards the
  whole chart entry onto each line as `:declared` without knowing what the key
  means, and that is what makes an unmatched intercompany balance
  unmissable — see `eliminations`."
  (:require [kotoba.lang.text :as str]
            [kotoba.shohyo :as shohyo]))

;; ---------------------------------------------------------------------------
;; provenance — what was read, and what backs each check
;; ---------------------------------------------------------------------------

(def sources
  "The four texts fetched, with the revision each was read at.

  A revision id rather than a date: 会社計算規則 has been amended eleven
  times since 2006 and `会社計算規則 第六十三条` alone does not say which one
  was read."
  {:jp/companies-act
   {:source/title "会社法"
    :source/law-id "417AC0000000086"
    :source/revision "417AC0000000086_20260812_508AC0000000064"
    :source/authority "e-Gov 法令 API (api/2/law_data)"
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/417AC0000000086?response_format=json"
    :source/http-status 200
    :source/bytes 3034237
    :source/retrieved-at "2026-08-18"}

   :jp/company-accounting-rules
   {:source/title "会社計算規則"
    :source/law-id "418M60000010013"
    :source/revision "418M60000010013_20250331_507M60000010014"
    :source/authority "e-Gov 法令 API (api/2/law_data)"
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/418M60000010013?response_format=json"
    :source/http-status 200
    :source/bytes 857066
    :source/retrieved-at "2026-08-18"}

   :jp/companies-act-enforcement-rules
   {:source/title "会社法施行規則"
    :source/law-id "418M60000010012"
    :source/revision "418M60000010012_20240401_506M60000010011"
    :source/authority "e-Gov 法令 API (api/2/law_data)"
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/418M60000010012?response_format=json"
    :source/http-status 200
    :source/bytes 1461146
    :source/retrieved-at "2026-08-18"}

   :jp/consolidated-financial-statements-rules
   {:source/title "連結財務諸表の用語、様式及び作成方法に関する規則（連結財務諸表規則）"
    :source/law-id "351M50000040028"
    :source/revision "351M50000040028_20260331_508M60000002028"
    :source/authority "e-Gov 法令 API (api/2/law_data)"
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/351M50000040028?response_format=json"
    :source/http-status 200
    :source/bytes 949702
    :source/retrieved-at "2026-08-18"
    :source/note (str "Read for corroboration only. It is made under 金融商品取引法 "
                      "and governs 連結財務諸表 in an 有価証券報告書, not the "
                      "連結計算書類 of 会社法 第四百四十四条. Its 第五条 and 第九条 "
                      "are worded almost identically to 会社計算規則 第六十三条 and "
                      "第六十八条, which is evidence that the general elimination "
                      "clause is not an accident of drafting.")}})

(def provisions
  "The provisions implemented here, quoted verbatim from `sources`.

  taxlaw's standing rule applies and is enforced in code, not prose: a claim
  that is ENFORCED must be read. `provision-read?` is the filter, and
  `consolidate` derives its `:unread` answer from it rather than asserting
  it, so downgrading any quote below to `:reachable-not-read` changes the
  behaviour in the same edit."
  {:retrieved-at "2026-08-18"
   :articles
   [{:provision "会社法 第四百四十四条第一項" :on :group-is-parent-and-subsidiaries
     :source :jp/companies-act :review :read-from-source
     :quote (str "会計監査人設置会社は、法務省令で定めるところにより、各事業年度に係る"
                 "連結計算書類（当該会計監査人設置会社及びその子会社から成る企業集団の"
                 "財産及び損益の状況を示すために必要かつ適当なものとして法務省令で"
                 "定めるものをいう。以下同じ。）を作成することができる。")}

    {:provision "会社法 第四百四十四条第三項" :on :when-consolidation-is-mandatory
     :source :jp/companies-act :review :read-from-source
     :enforced? false
     :quote (str "事業年度の末日において大会社であって金融商品取引法第二十四条第一項の"
                 "規定により有価証券報告書を内閣総理大臣に提出しなければならないものは、"
                 "当該事業年度に係る連結計算書類を作成しなければならない。")
     :note (str "Read and quoted, enforcing nothing. Whether a company is a 大会社 "
                "with an 有価証券報告書 obligation is not in a trial balance. Worth "
                "quoting because the common summary — `大会社 must consolidate` — "
                "drops the second, conjunctive condition: 第一項 says 作成すること"
                "ができる, so under 会社法 consolidation is PERMISSIVE by default "
                "and mandatory only where both limbs of 第三項 are met.")}

    {:provision "会社計算規則 第六十一条第一項" :on :what-連結計算書類-is
     :source :jp/company-accounting-rules :review :read-from-source
     :enforced? false
     :quote (str "法第四百四十四条第一項に規定する法務省令で定めるものは、次に掲げる"
                 "いずれかのものとする。一この編（第百二十条から第百二十条の三までを"
                 "除く。）の規定に従い作成される次のイからニまでに掲げるもの"
                 "イ連結貸借対照表ロ連結損益計算書ハ連結株主資本等変動計算書"
                 "ニ連結注記表")
     :note (str "Quoted to bound this module honestly. 連結計算書類 is FOUR "
                "documents; this produces the first two. 連結株主資本等変動計算書 "
                "needs opening balances and movement causes (第九十六条第七項) and "
                "連結注記表 needs disclosures, neither of which a closing trial "
                "balance carries. Recorded in `catalog-verification` as a scope "
                "limit rather than left to be inferred from silence.")}

    {:provision "会社計算規則 第六十三条第一項" :on :scope-of-consolidation
     :source :jp/company-accounting-rules :review :read-from-source
     :quote (str "株式会社は、その全ての子会社を連結の範囲に含めなければならない。"
                 "ただし、次のいずれかに該当する子会社は、連結の範囲に含めないものと"
                 "する。一財務及び事業の方針を決定する機関（株主総会その他これに準ずる"
                 "機関をいう。）に対する支配が一時的であると認められる子会社"
                 "二連結の範囲に含めることにより当該株式会社の利害関係人の判断を"
                 "著しく誤らせるおそれがあると認められる子会社")}

    {:provision "会社計算規則 第六十三条第二項" :on :materiality-exclusion
     :source :jp/company-accounting-rules :review :read-from-source
     :quote (str "前項の規定により連結の範囲に含めるべき子会社のうち、その資産、"
                 "売上高（役務収益を含む。以下同じ。）等からみて、連結の範囲から除いても"
                 "その企業集団の財産及び損益の状況に関する合理的な判断を妨げない程度に"
                 "重要性の乏しいものは、連結の範囲から除くことができる。")}

    {:provision "会社計算規則 第六十八条" :on :elimination
     :source :jp/company-accounting-rules :review :read-from-source
     :quote (str "連結計算書類の作成に当たっては、連結子会社の資産及び負債の評価並びに"
                 "株式会社の連結子会社に対する投資とこれに対応する当該連結子会社の資本との"
                 "相殺消去その他必要とされる連結会社相互間の項目の相殺消去を"
                 "しなければならない。")}

    {:provision "会社計算規則 第六十九条第一項" :on :equity-method
     :source :jp/company-accounting-rules :review :read-from-source
     :enforced? false
     :quote (str "非連結子会社及び関連会社に対する投資については、持分法により計算する"
                 "価額をもって連結貸借対照表に計上しなければならない。ただし、次の"
                 "いずれかに該当する非連結子会社及び関連会社に対する投資については、"
                 "持分法を適用しないものとする。")
     :note (str "Read, quoted, enforcing nothing. 持分法 restates an investment to "
                "the投資先's net assets times the holding, which needs that entity's "
                "own statements and the acquisition-date figures. A subsidiary "
                "excluded under 第六十三条 does not vanish from the group — it "
                "returns here — and this module does not carry it back. Said out "
                "loud rather than left absent, because an excluded subsidiary that "
                "is silently gone is exactly the omission this library refuses.")}

    {:provision "会社計算規則 第七十六条第一項第二号" :on :nci-is-a-mandatory-section
     :source :jp/company-accounting-rules :review :read-from-source
     :quote (str "純資産の部は、次の各号に掲げる貸借対照表等の区分に応じ、当該各号に"
                 "定める項目に区分しなければならない。…二株式会社の連結貸借対照表次に"
                 "掲げる項目イ株主資本ロ次に掲げるいずれかの項目（１）評価・換算差額等"
                 "（２）その他の包括利益累計額ハ株式引受権ニ新株予約権ホ非支配株主持分")
     :quote-is-partial? true
     :quote-omits "第一号 (単体の貸借対照表) and 第三号 (持分会社), and 第二項 onward."}

    {:provision "会社計算規則 第七十六条第九項第二号" :on :translation-adjustment
     :source :jp/company-accounting-rules :review :read-from-source
     :quote (str "第七項第四号の為替換算調整勘定外国にある子会社又は関連会社の資産及び"
                 "負債の換算に用いる為替相場と純資産の換算に用いる為替相場とが異なる"
                 "ことによって生じる換算差額")}

    {:provision "会社計算規則 第九十四条第三項" :on :nci-share-of-profit
     :source :jp/company-accounting-rules :review :read-from-source
     :quote (str "連結損益計算書には、次に掲げる項目の金額は、その内容を示す名称を付した"
                 "項目をもって、当期純利益金額又は当期純損失金額の次に表示しなければ"
                 "ならない。一当期純利益として表示した額があるときは、当該額のうち"
                 "非支配株主に帰属するもの二当期純損失として表示した額があるときは、"
                 "当該額のうち非支配株主に帰属するもの")}

    {:provision "会社計算規則 第九十四条第四項" :on :profit-attributable-to-owners
     :source :jp/company-accounting-rules :review :read-from-source
     :quote (str "連結損益計算書には、当期純利益金額又は当期純損失金額に当期純利益又は"
                 "当期純損失のうち非支配株主に帰属する額を加減して得た額は、親会社株主に"
                 "帰属する当期純利益金額又は当期純損失金額として表示しなければならない。")}

    {:provision "会社法施行規則 第三条第一項" :on :subsidiary-is-a-control-question
     :source :jp/companies-act-enforcement-rules :review :read-from-source
     :quote (str "法第二条第三号に規定する法務省令で定めるものは、同号に規定する会社が"
                 "他の会社等の財務及び事業の方針の決定を支配している場合における当該"
                 "他の会社等とする。")}

    {:provision "会社法施行規則 第三条第三項" :on :control-is-not-a-percentage
     :source :jp/companies-act-enforcement-rules :review :read-from-source
     :quote (str "前二項に規定する「財務及び事業の方針の決定を支配している場合」とは、"
                 "次に掲げる場合（財務上又は事業上の関係からみて他の会社等の財務又は"
                 "事業の方針の決定を支配していないことが明らかであると認められる場合を"
                 "除く。）をいう…一…議決権の数の割合が百分の五十を超えている場合"
                 "…二…百分の四十以上である場合…であって、次に掲げるいずれかの要件に"
                 "該当する場合…三他の会社等の議決権の総数に対する自己所有等議決権数の"
                 "割合が百分の五十を超えている場合（自己の計算において議決権を所有して"
                 "いない場合を含み、前二号に掲げる場合を除く。）であって、前号ロからホ"
                 "までに掲げるいずれかの要件に該当する場合")
     :quote-is-partial? true
     :quote-omits (str "the イ〜ホ sub-requirements of 第二号 (緊密な関係者の議決権, "
                       "役員構成, 支配する契約等, 融資, その他推測される事実) and the "
                       "イ〜ニ carve-out of 第一号 for companies in 民事再生 / "
                       "会社更生 / 破産 where 有効な支配従属関係 is absent. Elided "
                       "because nothing here turns on their content: the module "
                       "refuses to derive control at all.")}

    {:provision "連結財務諸表規則 第五条第一項" :on :scope-of-consolidation
     :source :jp/consolidated-financial-statements-rules :review :read-from-source
     :enforced? false
     :quote (str "連結財務諸表提出会社は、その全ての子会社を連結の範囲に含めなければ"
                 "ならない。ただし、次の各号の一に該当する子会社は、連結の範囲に含めない"
                 "ものとする。")
     :note "Corroboration for 会社計算規則 第六十三条第一項; enforces nothing here."}

    {:provision "連結財務諸表規則 第九条" :on :elimination
     :source :jp/consolidated-financial-statements-rules :review :read-from-source
     :enforced? false
     :quote (str "連結財務諸表の作成に当たつては、連結子会社の資産及び負債の評価並びに"
                 "連結財務諸表提出会社の連結子会社に対する投資とこれに対応する当該連結"
                 "子会社の資本との相殺消去その他必要とされる連結会社相互間の項目の消去を"
                 "しなければならない。")
     :note (str "Corroboration for 会社計算規則 第六十八条. Note it says 項目の消去 "
                "where 第六十八条 says 項目の相殺消去 — and neither enumerates what "
                "the items are.")}]})

(def catalog-verification
  "What was verified, what was measured, what was not read, and what this
  module does not attempt.

  Four distinct claims. Collapsing them is how a citation list becomes
  decoration."
  {:catalog/corroborated? true

   :catalog/corroboration
   (str "会社計算規則 第六十三条/第六十八条 and 連結財務諸表規則 第五条/第九条 were "
        "read independently and say the same things in almost the same words, "
        "under two different statutes. Where they differ the difference is "
        "recorded rather than smoothed over.")

   ;; Counted over the fetched texts on 2026-08-18. This is a claim about
   ;; absence, so it is stated as a measurement with its denominator: an
   ;; absence nobody counted cannot be told from one nobody looked for.
   :catalog/measured
   [{:claim :the-regulation-never-says-内部取引
     :how (str "Every 条 of both ordinances was extracted from the e-Gov JSON "
               "and searched. 会社計算規則: 180 articles, 0 containing 内部取引, "
               "0 containing 未実現, 0 containing 債権債務. 連結財務諸表規則: "
               "399 main articles, 0 containing 内部取引, 0 containing 未実現, "
               "1 containing 債権債務 — 第十五条の四の二, a 関連当事者 note.")
     :consequence (str "The elimination performed here rests on the general "
                       "clause その他必要とされる連結会社相互間の項目の相殺消去 "
                       "of 第六十八条 and on nothing more specific. The itemised "
                       "vocabulary everyone quotes is 企業会計基準第22号's, and "
                       "that standard was not read.")}]

   ;; Read, quoted, enforcing nothing — and said so, because a cited
   ;; provision that silently backs no check reads exactly like one that does.
   :catalog/read-but-not-enforced
   [{:provision "会社法 第四百四十四条第三項"
     :why "whether a company is a 大会社 with an 有価証券報告書 obligation is not in a trial balance"}
    {:provision "会社計算規則 第六十一条第一項"
     :why (str "連結株主資本等変動計算書 needs opening balances and movement "
               "causes; 連結注記表 needs disclosures. A closing trial balance "
               "carries neither, so two of the four documents are out of scope.")}
    {:provision "会社計算規則 第六十九条第一項"
     :why (str "持分法 needs the investee's own statements and its "
               "acquisition-date equity. An excluded subsidiary is named in the "
               "scope rather than restated.")}
    {:provision "連結財務諸表規則 第五条第一項"}
    {:provision "連結財務諸表規則 第九条"}]

   ;; Reachable and NOT read. Each one is the reason a computation is refused
   ;; rather than approximated — `blocked-by-unread` is the code path that
   ;; makes this record load-bearing instead of decorative.
   :catalog/not-verified
   [{:standard "企業会計基準第22号「連結財務諸表に関する会計基準」"
     :publisher "企業会計基準委員会 (ASBJ)"
     :where "not on e-Gov; ASBJ distributes it separately"
     :scopes ["未実現損益の消去" "内部取引高の相殺消去の具体的な範囲"
              "資本連結の手続と非支配株主持分の測定"]
     :review :reachable-not-read}
    {:standard "企業会計審議会「外貨建取引等会計処理基準」"
     :where "not on e-Gov"
     :scopes ["在外子会社の資産・負債・純資産・収益費用に用いる為替相場"
              "為替換算調整勘定の算定"]
     :review :reachable-not-read}
    {:standard "会社計算規則 第七十六条第七項第四号"
     :where "read as a heading only"
     :scopes ["為替換算調整勘定 as a 純資産 subdivision"]
     :review :reachable-not-read
     :why (str "第九項第二号 defines what the account measures and IS quoted; "
               "the rate to use is not in the ordinance at all.")}]

   ;; Not a citation question. Things a reader might reasonably expect this
   ;; module to do, that it does not, so that absence is never read as a pass.
   :catalog/out-of-scope
   [{:what "連結株主資本等変動計算書" :provision "会社計算規則 第九十六条"}
    {:what "連結注記表" :provision "会社計算規則 第六十一条第一項イ〜ニ"}
    {:what "持分法の適用" :provision "会社計算規則 第六十九条"}
    {:what "資本連結（投資と資本の相殺消去、のれん）" :provision "会社計算規則 第六十八条"
     :why (str "第六十八条 names this one elimination explicitly and it is the "
               "one this module cannot do: it needs the subsidiary's equity at "
               "the acquisition date and the carrying amount of the investment, "
               "neither of which is in a closing trial balance. Refused by name "
               "in every result rather than omitted.")}]})

(defn provision-read?
  "Was this provision read from source? Anything else may not back a check."
  [{:keys [review]}]
  (= :read-from-source review))

(defn enforced-provisions
  "The provisions that actually back a check here: read from source, and not
  marked `:enforced? false`.

  Derived from `provisions` rather than listed, so downgrading a quote's
  `:review` removes its check in the same edit."
  []
  (into []
        (comp (filter provision-read?)
              (remove #(false? (:enforced? %)))
              (map :provision))
        (:articles provisions)))

(defn unread-standards
  "The standards this module cites without having read them, and what each
  one's absence costs.

  Exposed rather than buried, and joined into prose rather than counted, for
  the same reason a missing account is named: a reader who cannot see what
  was unread has to take every refusal on trust."
  []
  (mapv (fn [{:keys [standard scopes review]}]
          {:standard standard :review review :affects (str/join ", " scopes)})
        (:catalog/not-verified catalog-verification)))

;; ---------------------------------------------------------------------------
;; 第六十三条 — the scope, and its two modalities
;; ---------------------------------------------------------------------------

(def exclusion-grounds
  "The grounds on which a 子会社 leaves the 連結の範囲, with the modality the
  article uses.

  `:mandatory` is 第六十三条第一項's 「含めないものとする」 — the subsidiary
  MUST be left out. `:permissive` is 第二項's 「除くことができる」 — the
  entity MAY leave it out. Flattening the two into one `:excludable?` flag is
  the mistake the namespace docstring names: it would let a caller consolidate
  a subsidiary whose control is temporary, and the statement would balance."
  {:temporary-control
   {:jp "財務及び事業の方針を決定する機関に対する支配が一時的であると認められる子会社"
    :provision "会社計算規則 第六十三条第一項第一号" :modality :mandatory}
   :seriously-misleading
   {:jp "連結の範囲に含めることにより当該株式会社の利害関係人の判断を著しく誤らせるおそれがあると認められる子会社"
    :provision "会社計算規則 第六十三条第一項第二号" :modality :mandatory}
   :immaterial
   {:jp "その資産、売上高等からみて…重要性の乏しいもの"
    :provision "会社計算規則 第六十三条第二項" :modality :permissive}})

(defn known-ground? [g] (contains? exclusion-grounds g))

(defn mandatory-ground? [g]
  (= :mandatory (:modality (exclusion-grounds g))))

;; ---------------------------------------------------------------------------
;; ownership, in integers
;; ---------------------------------------------------------------------------

(defn- int-like? [n]
  #?(:clj (integer? n)
     ;; ClojureScript has no distinct float type: `1.0` reads as `1`, and
     ;; `integer?` is true for any whole-valued number. That is exactly the
     ;; hazard this predicate exists for, so it tests whole-valuedness rather
     ;; than a tag that does not survive the reader.
     :cljs (and (number? n) (not (js/isNaN n)) (js/isFinite n) (== n (js/Math.trunc n)))))

(defn ownership-usable?
  "Is `[numerator denominator]` a usable holding?

  Two whole numbers, denominator positive, numerator between zero and the
  denominator. **Nothing here divides.** A ratio kept as a pair is exact in
  both runtimes; a percentage is not, and the one arithmetic mistake this
  library cannot afford is in money."
  [o]
  (boolean
   (and (vector? o) (= 2 (count o))
        (let [[n d] o]
          (and (int-like? n) (int-like? d)
               (pos? d) (<= 0 n) (<= n d))))))

(defn wholly-owned?
  "Is the holding the whole of it? Exact integer comparison, never a division."
  [[n d]] (= n d))

(defn- minority-share [[n d]] [(- d n) d])

;; ---------------------------------------------------------------------------
;; the scope declaration
;; ---------------------------------------------------------------------------

(def ^:private control-values #{:controlled :not-controlled})

(defn- member-problems
  [parent-id [id m]]
  (let [role (:renketsu/role m)
        control (:renketsu/control m)
        inclusion (:renketsu/inclusion m)
        ground (:renketsu/exclusion-ground m)
        ownership (:renketsu/ownership m)
        parent? (= id parent-id)
        p (fn [problem detail] {:entity id :problem problem :detail detail})]
    (cond-> []
      (nil? (:renketsu/statements m))
      (conj (p :member-without-statements
               "a member of the group with no folded statement to consolidate"))

      (and (not parent?) (not= :subsidiary role))
      (conj (p :unknown-role
               (str (pr-str role) " — a member other than the parent must be"
                    " declared :subsidiary")))

      ;; A percentage is evidence, never the answer: 会社法施行規則
      ;; 第三条第三項 excludes clear non-control above half and reaches zero
      ;; holdings below it.
      (and (not parent?) (nil? control))
      (conj (p :control-not-determined
               (str "支配力基準 is a determination about 財務及び事業の方針の決定, "
                    "not an arithmetic fact"
                    (when (:renketsu/voting-rights m)
                      (str "; :renketsu/voting-rights "
                           (pr-str (:renketsu/voting-rights m))
                           " was declared and does not substitute for it"))
                    " (会社法施行規則 第三条第三項)")))

      (and (some? control) (not (contains? control-values control)))
      (conj (p :unknown-control
               (str (pr-str control) " is neither :controlled nor :not-controlled")))

      (and (= :not-controlled control) (= :included inclusion))
      (conj (p :not-controlled-but-included
               (str "第六十三条第一項's 連結の範囲 is 子会社; an entity declared "
                    "outside 支配 cannot be inside the scope")))

      (and (not parent?) (= :controlled control) (nil? inclusion))
      (conj (p :inclusion-not-declared
               (str "第六十三条第一項 requires every 子会社 and 第一項ただし書 / "
                    "第二項 are the only ways out; silence is neither")))

      (and (some? inclusion) (not (contains? #{:included :excluded} inclusion)))
      (conj (p :unknown-inclusion
               (str (pr-str inclusion) " is neither :included nor :excluded")))

      (and (= :excluded inclusion) (nil? ground))
      (conj (p :excluded-without-ground
               "第六十三条第一項 requires every 子会社; an exclusion needs its 号"))

      (and (some? ground) (not (known-ground? ground)))
      (conj (p :unknown-exclusion-ground
               (str (pr-str ground) " is not a ground 第六十三条 states")))

      ;; The rule a naive implementation gets wrong. See `exclusion-grounds`.
      (and (known-ground? ground) (mandatory-ground? ground) (= :included inclusion))
      (conj (p :mandatory-exclusion-included
               (str (:provision (exclusion-grounds ground))
                    " says 連結の範囲に含めないものとする — it is not a permission"
                    " to exclude, and this subsidiary is included")))

      (and (not parent?) (= :controlled control) (= :included inclusion)
           (nil? ownership))
      (conj (p :ownership-not-declared
               (str "第七十六条第一項第二号ホ makes 非支配株主持分 a section of a "
                    "連結貸借対照表; whether one arises cannot be known without "
                    "the holding")))

      (and (some? ownership) (not (ownership-usable? ownership)))
      (conj (p :unusable-ownership
               (str (pr-str ownership) " is not [numerator denominator] of two"
                    " whole numbers with 0 <= numerator <= denominator and"
                    " denominator > 0"))))))

(defn scope-problems
  "Every way `group` is not a usable declaration of 連結の範囲.

  Checked before anything is folded, for the reason the core checks the chart
  first: a group with a malformed scope would consolidate some set of
  entities, and the result would balance."
  [group]
  (let [parent (:renketsu/parent group)
        members (:renketsu/members group)]
    (vec
     (concat
      (when (nil? parent)
        [{:entity nil :problem :parent-not-declared
          :detail (str "会社法 第四百四十四条第一項's 企業集団 is 当該会計監査人"
                       "設置会社及びその子会社; without a parent there is no group")}])
      (when (and (some? parent) (not (contains? members parent)))
        [{:entity parent :problem :parent-not-a-member
          :detail "the declared parent has no entry in :renketsu/members"}])
      (mapcat #(member-problems parent %) members)))))

(defn consolidated-members
  "The entity ids actually inside 連結の範囲: the parent, and every subsidiary
  declared `:included`.

  Excluded subsidiaries are NOT here and are not silently gone either —
  `consolidate` reports them, with the 号 each one left under."
  [group]
  (let [parent (:renketsu/parent group)]
    (vec
     (sort
      (keep (fn [[id m]]
              (when (or (= id parent)
                        (and (= :controlled (:renketsu/control m))
                             (= :included (:renketsu/inclusion m))))
                id))
            (:renketsu/members group))))))

;; ---------------------------------------------------------------------------
;; the lines of the group
;; ---------------------------------------------------------------------------

(defn- entity-lines
  "Every line of one member's statement, tagged with the entity it came from.

  The tag is what makes an elimination leg resolvable and what makes an
  unmatched balance nameable: `S1 / due-to-p / JPY` locates a row a human can
  go and look at, where a total does not."
  [id result]
  (mapcat (fn [[currency cur]]
            (map #(assoc % :renketsu/entity id :currency currency)
                 (concat (:bs cur) (:pl cur))))
          (:shohyo/by-currency result)))

(defn- line-key [l]
  [(:renketsu/entity l) (:account l) (:currency l)])

;; ---------------------------------------------------------------------------
;; 第六十八条 — the eliminations
;; ---------------------------------------------------------------------------

(defn- resolve-leg [by-key in-scope leg]
  (let [e (:renketsu/entity leg)
        k [e (:account leg) (:currency leg)]]
    (cond
      (not (contains? in-scope e))
      {:leg leg :problem :leg-entity-not-consolidated}

      (not (contains? by-key k))
      {:leg leg :problem :leg-not-found}

      :else {:leg leg :line (get by-key k)})))

(defn- pair-verdict
  "Resolve one declared pair and decide whether it eliminates.

  The test is that the legs' DEBIT-POSITIVE balances sum to zero. That one
  test covers both shapes 第六十八条 contemplates: a receivable +100 against a
  payable −100, and revenue −100 against an expense +100. It is also what
  makes elimination safe — removing a set of lines whose debit-positive
  balances sum to zero cannot move 資産 = 負債 + 純資産 + 当期純利益, in any
  currency, because every line's contribution to one side is matched inside
  the set.

  A pair that does NOT sum to zero is **not partially eliminated**. Removing
  the matched part and leaving a residue would require deciding which leg is
  right, which is a judgement about the underlying transaction and not
  something a trial balance answers. So the residual is named, both legs stay
  where they are, and the group is not conformant. The numbers survive — that
  is the core's rule for an incomplete statement, and it holds here."
  [by-key in-scope pair]
  (let [legs (:renketsu/legs pair)
        id (:renketsu/pair pair)
        resolved (mapv #(resolve-leg by-key in-scope %) legs)
        broken (filterv :problem resolved)
        currencies (distinct (map :currency legs))]
    (cond
      (< (count legs) 2)
      {:pair id :eliminated? false :problem :fewer-than-two-legs
       :legs legs
       :detail "an elimination with one leg is a deletion"}

      (seq broken)
      {:pair id :eliminated? false :problem :leg-unresolved
       :unresolved (mapv (fn [{:keys [leg problem]}]
                           {:entity (:renketsu/entity leg) :account (:account leg)
                            :currency (:currency leg) :problem problem})
                         broken)
       :detail (str "a leg naming a line that is not in the consolidated "
                    "statement eliminates nothing, and the group still balances")}

      (< 1 (count currencies))
      {:pair id :eliminated? false :problem :legs-in-different-currencies
       :currencies (vec (sort currencies))
       :detail (str "offsetting across currencies would net yen against dollars;"
                    " 第六十八条 does not authorise a rate and neither does this")}

      :else
      (let [lines (mapv :line resolved)
            residual (reduce + 0 (map :balance lines))
            currency (first currencies)]
        (if (zero? residual)
          {:pair id :eliminated? true :currency currency
           :amount (reduce + 0 (map #(max 0 (:balance %)) lines))
           :lines (mapv line-key lines)}
          (cond-> {:pair id :eliminated? false :problem :residual
                   :currency currency :residual residual
                   :lines (mapv (fn [l] {:entity (:renketsu/entity l) :account (:account l)
                                         :currency (:currency l) :balance (:balance l)})
                                lines)
                   :detail (str "the legs do not offset; consolidating them anyway "
                                "leaves a statement that balances and is wrong")}
            ;; A residual on 投資と資本 is not a bookkeeping error — it is
            ;; のれん, or 非支配株主持分, or both, and telling them apart needs
            ;; the acquisition-date figures. Named rather than split.
            (= :investment-and-equity (:renketsu/kind pair))
            (assoc :why-residual
                   {:refused :goodwill-or-nci-needs-acquisition-figures
                    :provision "会社計算規則 第六十八条"
                    :unread-standard "企業会計基準第22号「連結財務諸表に関する会計基準」"
                    :detail (str "the difference between an investment and the "
                                 "equity it bought is のれん, 非支配株主持分, or "
                                 "both; separating them needs the subsidiary's "
                                 "equity at the acquisition date, which a "
                                 "closing trial balance does not carry")})))))))

(defn- unpaired-intercompany
  "Lines a chart marked `:renketsu/counterparty` that no pair eliminated.

  **This is what makes an unmatched intercompany balance unmissable.** Without
  it a caller who simply declares no pairs at all gets a clean answer: nothing
  failed to eliminate because nothing was attempted, and the consolidated
  statement balances, and 第六十八条 was ignored in silence.

  So the claim moves to where it can be checked. A chart that says an account
  faces a group company has made an assertion about that account; the core
  forwards it onto the line as `:declared` without knowing what the key means;
  and any such line still standing after the pairs are applied is named here,
  with its entity, its currency and its balance."
  [lines eliminated-keys]
  (vec
   (sort-by (juxt :entity :currency :account)
            (keep (fn [l]
                    (let [cp (get-in l [:declared :renketsu/counterparty])]
                      (when (and (some? cp)
                                 (not (contains? eliminated-keys (line-key l))))
                        {:entity (:renketsu/entity l) :account (:account l)
                         :currency (:currency l) :counterparty cp
                         :balance (:balance l)})))
                  lines))))

(defn eliminations
  "Apply the declared pairs to the group's lines.

  Returns `{:applied [...] :unmatched [...] :unpaired [...] :remaining [...]}`.
  `:remaining` are the lines that survive into the consolidated statement.

  Everything that did not eliminate is NAMED — never a count, never a total.
  A caller who is told `3 eliminations failed` has to go and find them; a
  caller who is told `S1 / due-to-p / JPY / −100` has been handed the row."
  [group lines]
  (let [in-scope (set (consolidated-members group))
        by-key (into {} (map (juxt line-key identity)) lines)
        verdicts (mapv #(pair-verdict by-key in-scope %)
                       (:renketsu/intercompany group))
        applied (filterv :eliminated? verdicts)
        unmatched (vec (remove :eliminated? verdicts))
        eliminated-keys (into #{} (mapcat :lines) applied)]
    {:applied applied
     :unmatched unmatched
     :unpaired (unpaired-intercompany lines eliminated-keys)
     :remaining (vec (remove #(contains? eliminated-keys (line-key %)) lines))}))

;; ---------------------------------------------------------------------------
;; currencies — 換算 is refused, never guessed
;; ---------------------------------------------------------------------------

(defn- translation
  "Do the consolidated members report in one currency, and if not, what then?

  Not translated. 会社計算規則 第七十六条第九項第二号 defines 為替換算調整勘定
  as the difference arising because 資産及び負債 and 純資産 are translated at
  DIFFERENT rates — so the ordinance presumes rates, and states none. Which
  rate applies to what is 「外貨建取引等会計処理基準」's, and that was not
  read.

  A library that translated anyway would have to invent a rate, and the
  arithmetic it would silently perform is adding yen to dollars — the exact
  bug the core refuses one entity at a time. So the per-currency statements
  are produced side by side and complete, and the group is not conformant
  until someone supplies the rates and does the translation somewhere that
  has them."
  [currencies]
  (let [cs (vec (sort currencies))]
    (if (< (count cs) 2)
      {:answered? true :required? false :currencies cs}
      {:answered? false :required? true :currencies cs
       :refused :translation-needs-dated-rates
       :provision "会社計算規則 第七十六条第九項第二号"
       :unread-standard "企業会計審議会「外貨建取引等会計処理基準」"
       :why (str "the group reports in " (str/join ", " cs)
                 "; presenting one figure would require translating at rates "
                 "this library has not read and cannot date")})))

;; ---------------------------------------------------------------------------
;; 非支配株主持分 and 未実現損益 — both need an input, and one needs a standard
;; ---------------------------------------------------------------------------

(defn- non-controlling-interests
  "Does a 非支配株主持分 arise, and can this module measure it?

  Whether one arises IS answerable from a declared holding: 第七十六条第一項
  第二号ホ makes it a section of the 純資産 half, and it is nil exactly when
  every consolidated subsidiary is wholly owned. `wholly-owned?` compares two
  integers and never divides.

  Its AMOUNT is not answerable here, and is refused rather than approximated.
  第九十四条第三項 and 第四項 want 当期純利益のうち非支配株主に帰属するもの,
  which is the minority's share of the subsidiary's profit SINCE ACQUISITION
  — so measuring it needs the subsidiary's equity at the acquisition date and
  the carrying amount of the parent's investment, to strike 第六十八条's
  投資と資本の相殺消去 first. A closing trial balance carries neither, and the
  standard that lays out the procedure (企業会計基準第22号) was not read.
  Two independent reasons; both are named."
  [group in-scope]
  (let [parent (:renketsu/parent group)
        partly (vec
                (sort-by :entity
                         (keep (fn [id]
                                 (let [m (get-in group [:renketsu/members id])
                                       o (:renketsu/ownership m)]
                                   (when (and (not= id parent)
                                              (ownership-usable? o)
                                              (not (wholly-owned? o)))
                                     {:entity id :ownership o
                                      :non-controlling-share (minority-share o)})))
                               in-scope)))]
    (if (empty? partly)
      {:answered? true :arises? false :arises-from []
       :why (str "every consolidated subsidiary is wholly owned, so no "
                 "非支配株主持分 arises under 第七十六条第一項第二号ホ")}
      {:answered? false :arises? true :arises-from partly
       :refused :non-controlling-interest-needs-acquisition-date-equity
       :provisions ["会社計算規則 第七十六条第一項第二号"
                    "会社計算規則 第九十四条第三項" "会社計算規則 第九十四条第四項"]
       :unread-standard "企業会計基準第22号「連結財務諸表に関する会計基準」"
       :why (str "the share is known and the amount is not: striking it needs "
                 "the subsidiary's equity at acquisition and the carrying "
                 "amount of the investment, and a closing trial balance "
                 "carries neither")})))

(defn- capital-consolidation
  "投資と資本の相殺消去 — the one elimination 第六十八条 names, answered from
  the data rather than refused on principle.

  第六十八条 says 株式会社の連結子会社に対する投資とこれに対応する当該連結
  子会社の資本との相殺消去. Both sides are ordinary lines: the parent's
  investment is an asset in the parent's books and the subsidiary's 資本 is
  equity in the subsidiary's. So this is a pairing like any other and it is
  declared like any other — `:renketsu/kind :investment-and-equity` — rather
  than being a second mechanism.

  What is checked is the **result**: after the declared pairs are applied, no
  equity line of a consolidated subsidiary may still be standing. One that is
  has been added to the parent's own equity, and the group's balance sheet
  balances with the same capital counted twice.

  This is deliberately not an unconditional refusal. An unconditional one
  would make `consolidated?` false for every group with a subsidiary in it,
  and a predicate that is a constant tells nobody anything — the same reason
  the core's `complete?` is reachable. It IS reachable here, and only in the
  case where it is honestly true: a wholly-owned subsidiary carried at the
  equity it bought, with every intercompany balance paired. Where the two
  sides differ, the pair reports a residual and says what the residual is."
  [parent in-scope remaining]
  (let [subs (set (remove #(= % parent) in-scope))
        standing (vec
                  (sort-by (juxt :entity :currency :account)
                           (keep (fn [l]
                                   (when (and (contains? subs (:renketsu/entity l))
                                              (= :equity (:type l)))
                                     {:entity (:renketsu/entity l)
                                      :account (:account l)
                                      :currency (:currency l)
                                      :balance (:balance l)}))
                                 remaining)))]
    (if (empty? standing)
      {:answered? true :standing-subsidiary-equity []
       :provision "会社計算規則 第六十八条"
       :why (str "no equity line of a consolidated subsidiary survives the "
                 "declared eliminations, so nothing is counted twice")}
      {:answered? false
       :refused :investment-and-equity-not-eliminated
       :provision "会社計算規則 第六十八条"
       :standing-subsidiary-equity standing
       :why (str "第六十八条 requires 投資と資本の相殺消去; these subsidiary "
                 "equity lines are still standing, so the group's 資本 is the "
                 "parent's plus theirs and the balance sheet balances anyway")})))

(defn- unrealised-profit
  "未実現損益 — refused, and the refusal is not conditional on being asked.

  Unrealised profit is the margin one group company charged another on goods
  that are still in the group's inventory at the reporting date. Finding it
  needs, per item still on hand, the price it moved at and the cost it moved
  from. **A trial balance carries a closing balance and no such history**, so
  there is no arrangement of this data from which the figure can be recovered.

  It is therefore a determination like the scope, and it is handled the same
  way: an unstated one is its own answer and not a pass. A caller who declares
  `{:renketsu/present? false}` has asserted something this module records and
  did not verify; a caller who declares `true` gets a refusal naming why; a
  caller who says nothing gets neither a refusal nor a pass, which is the
  honest third answer.

  Eliminating only what is easy — the receivables, because they pair, and not
  the margin, because it does not — is how a consolidated statement comes out
  balanced and overstated."
  [group]
  (let [d (:renketsu/unrealised-profit group)
        declared-by-pair (vec (sort (keep (fn [p]
                                            (when (:renketsu/unrealised-profit? p)
                                              (:renketsu/pair p)))
                                          (:renketsu/intercompany group))))
        present (:renketsu/present? d)]
    (cond
      (nil? d)
      {:answered? false :why :not-declared
       :detail (str "whether goods bought from a group company are still on "
                    "hand is not in a trial balance, and silence is not no")
       :unread-standard "企業会計基準第22号「連結財務諸表に関する会計基準」"}

      (and (false? present) (seq declared-by-pair))
      {:answered? false :why :contradicted-by-a-pair
       :pairs declared-by-pair
       :detail (str "the group declares no unrealised profit while "
                    (str/join ", " declared-by-pair)
                    " declares :renketsu/unrealised-profit? true")}

      (true? present)
      {:answered? false :why :not-eliminable
       :pairs declared-by-pair
       :refused :unrealised-profit-needs-cost-of-goods-still-held
       :unread-standard "企業会計基準第22号「連結財務諸表に関する会計基準」"
       :detail (str "eliminating it needs, per item still on hand, the price it "
                    "moved at and the cost it moved from; a closing balance is "
                    "neither")}

      (false? present)
      {:answered? true :declared :absent
       :detail (str "asserted by the caller and NOT verified here — this module "
                    "has no data from which unrealised profit could be seen")}

      :else
      {:answered? false :why :unknown-declaration
       :detail (str (pr-str present)
                    " — :renketsu/present? must be true or false")})))

;; ---------------------------------------------------------------------------
;; the consolidated statement
;; ---------------------------------------------------------------------------

(defn consolidate
  "Fold a group's member statements into 連結貸借対照表 and 連結損益計算書.

  `group` is described in the namespace docstring. Returns, three-valued at
  the top and never a bare boolean:

      {:shohyo.renketsu/coverage :unread}         no provision was read
      {:shohyo.renketsu/coverage :scope-not-declared}
      {:shohyo.renketsu/coverage :unusable-scope} the scope does not parse
      {:shohyo.renketsu/coverage :checked ...}    answered, per currency

  **Only the last can be a pass, and it still need not be.** The first three
  are all `no` in the sense that matters — nothing was demonstrated — and they
  are kept apart because the fix differs: a citation to go and read, a scope
  to go and declare, a declaration to go and correct.

  `:checked` carries the consolidated figures under
  `:shohyo.renketsu/consolidated`, which is shaped exactly like a result from
  `kotoba.shohyo/statements` — so `shohyo/out-of-balance` and
  `shohyo/complete?` compose onto it directly, and the accounting equation is
  the same equation, checked per currency on the group. Consolidation composes
  single-entity results; it does not reimplement them.

  The figures are present even when the group is not conformant, for the
  core's reason: refusing to show anything helps nobody. A caller that renders
  without reading `:shohyo.renketsu/reasons` is rendering a group statement
  that is short by whatever it was told about."
  [group]
  (let [any-read? (boolean (seq (enforced-provisions)))
        problems (scope-problems group)]
    (cond
      (not any-read?)
      {:shohyo.renketsu/coverage :unread
       :shohyo.renketsu/why
       (str "no provision of 会社法 / 会社計算規則 / 会社法施行規則 is marked "
            ":read-from-source; an unread rule cannot make a group statement "
            "conformant")}

      (empty? (:renketsu/members group))
      {:shohyo.renketsu/coverage :scope-not-declared
       :shohyo.renketsu/why
       (str "連結の範囲 is a determination about 支配, not a computation "
            "(会社法施行規則 第三条第三項). No members were declared, and a "
            "consolidated balance sheet that omits a subsidiary still balances.")}

      (seq problems)
      {:shohyo.renketsu/coverage :unusable-scope
       :shohyo.renketsu/scope-problems problems
       :shohyo.renketsu/consolidated {:shohyo/coverage :incomplete
                                      :shohyo/by-currency {}
                                      :shohyo/unclassified []}
       :shohyo.renketsu/why
       "no figures are produced on an unusable scope, the way the core produces none on an unusable chart"}

      :else
      (let [parent (:renketsu/parent group)
            members (:renketsu/members group)
            in-scope (consolidated-members group)
            excluded (vec (sort-by :entity
                                   (keep (fn [[id m]]
                                           (when (= :excluded (:renketsu/inclusion m))
                                             {:entity id
                                              :ground (:renketsu/exclusion-ground m)
                                              :provision (:provision (exclusion-grounds
                                                                      (:renketsu/exclusion-ground m)))
                                              :modality (:modality (exclusion-grounds
                                                                    (:renketsu/exclusion-ground m)))}))
                                         members)))
            member-coverage (into {}
                                  (map (fn [id]
                                         [id (get-in members [id :renketsu/statements
                                                              :shohyo/coverage])]))
                                  in-scope)
            incomplete-members (vec (sort (keep (fn [[id c]]
                                                  (when (not= :complete c) id))
                                                member-coverage)))
            lines (vec (mapcat (fn [id]
                                 (entity-lines id (get-in members [id :renketsu/statements])))
                               in-scope))
            elim (eliminations group lines)
            remaining (:remaining elim)
            currencies (distinct (map :currency remaining))
            ;; Grouped by currency before folding, exactly as `statements`
            ;; does. `fold-lines` returns one statement and so has nowhere to
            ;; say `these were two currencies`; the grouping is what keeps yen
            ;; and dollars apart, and `translation` is what says so out loud.
            by-cur (into {}
                         (map (fn [[currency ls]] [currency (shohyo/fold-lines (vec ls))]))
                         (group-by :currency remaining))
            unclassified (vec (sort (distinct
                                     (mapcat (fn [id]
                                               (get-in members [id :renketsu/statements
                                                                :shohyo/unclassified]))
                                             in-scope))))
            consolidated {:shohyo/coverage (if (or (empty? by-cur) (seq unclassified))
                                             :incomplete :complete)
                          :shohyo/chart-problems []
                          :shohyo/unclassified unclassified
                          :shohyo/by-currency by-cur}
            trans (translation currencies)
            capital (capital-consolidation parent in-scope remaining)
            nci (non-controlling-interests group in-scope)
            urp (unrealised-profit group)
            equation-ok? (shohyo/complete? consolidated)
            reasons (cond-> []
                      (seq incomplete-members) (conj :member-statement-incomplete)
                      (seq (:unmatched elim)) (conj :intercompany-not-eliminated)
                      (seq (:unpaired elim)) (conj :intercompany-account-unpaired)
                      (not equation-ok?) (conj :consolidated-equation-or-coverage-fails)
                      (not (:answered? trans)) (conj :currency-translation-refused)
                      (not (:answered? nci)) (conj :non-controlling-interest-not-measurable)
                      (not (:answered? urp)) (conj :unrealised-profit-not-eliminated)
                      (not (:answered? capital))
                      (conj :investment-and-equity-not-eliminated))]
        {:shohyo.renketsu/coverage :checked
         :shohyo.renketsu/parent parent
         :shohyo.renketsu/consolidated-entities in-scope
         :shohyo.renketsu/excluded-subsidiaries excluded
         :shohyo.renketsu/member-coverage member-coverage
         :shohyo.renketsu/incomplete-members incomplete-members
         :shohyo.renketsu/consolidated consolidated
         :shohyo.renketsu/eliminations (dissoc elim :remaining)
         :shohyo.renketsu/translation trans
         :shohyo.renketsu/non-controlling-interests nci
         :shohyo.renketsu/unrealised-profit urp
         :shohyo.renketsu/capital-consolidation capital
         :shohyo.renketsu/conformant? (empty? reasons)
         :shohyo.renketsu/reasons (vec (sort-by name reasons))}))))

(defn consolidated?
  "Convenience boolean over `consolidate`, conservative like the rest.

  Deliberately not `(:shohyo.renketsu/conformant? …)` alone: `:unread`,
  `:scope-not-declared` and `:unusable-scope` carry no such key, so a caller
  reaching for the convenient boolean gets false there too. `shohyo/complete?`,
  `ifrs/presented?`, `taxlaw/supported?` and `worklaw/compliant?` all make the
  same choice for the same reason — the convenient answer must be the
  conservative one, not the flattering one.

  It is reachable, and only where it is honestly true: every member statement
  complete, every intercompany balance paired and offsetting, no subsidiary
  equity left standing, one currency, wholly owned, and 未実現損益 addressed.
  A boolean that no input can turn true would tell nobody anything — the same
  objection as a check that never goes red."
  [r] (true? (:shohyo.renketsu/conformant? r)))

(defn out-of-balance
  "Currencies whose accounting equation does not hold on the CONSOLIDATED
  statement, with the difference.

  `consolidated?` answers whether to worry; this answers where — the same
  division of labour as `shohyo/out-of-balance`, which this delegates to
  rather than reimplements. The group's equation is the entity's equation:
  資産 = 負債 + 純資産 + 当期純利益, per currency, never across."
  [r] (shohyo/out-of-balance (:shohyo.renketsu/consolidated r)))

(defn not-eliminated
  "Everything 第六十八条 asked to be eliminated and that was not, named.

  Three kinds, kept apart because the fix differs:

  - `:unmatched` — a pair was declared and did not eliminate (a leg that
    resolves to nothing, legs in two currencies, a residual)
  - `:unpaired` — a line the chart marked `:renketsu/counterparty` that no
    pair covered at all
  - `:refused` — the eliminations this module does not attempt

  A caller that prints only a count of these has thrown away the part that
  lets someone act. That is why every entry carries entity, account, currency
  and amount."
  [r]
  {:unmatched (get-in r [:shohyo.renketsu/eliminations :unmatched] [])
   :unpaired (get-in r [:shohyo.renketsu/eliminations :unpaired] [])
   :refused (vec
             (keep identity
                   [(let [c (:shohyo.renketsu/capital-consolidation r)]
                      (when (and c (not (:answered? c)))
                        (assoc c :what :投資と資本の相殺消去)))
                    (let [u (:shohyo.renketsu/unrealised-profit r)]
                      (when (and u (not (:answered? u)))
                        (assoc u :what :未実現損益)))]))})
