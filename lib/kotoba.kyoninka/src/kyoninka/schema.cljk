(ns kyoninka.schema
  "許認可手続きを procedure-as-data で表すための Datomic 互換スキーマと
  状態機械の定義。ADR-2607141620 (com-junkawasaki/root)。

  **法域は日本に限らない**（2026-08-07 に GBR / DEU を収録）。ここの型は
  『日本ならこう』を前提にしない —— 実際、通貨を属性名に焼いた
  `:procedure/fee-jpy` と、額をスカラ 1 個に限った初版の手数料表現は、
  どちらも最初の非 JPN を収録した瞬間に破れた。

  設計原則:
  - 手続き(procedure)は不変の data。案件(case)は手続きに対する進行状態。
  - 手数料・標準処理期間・様式は改定されうる「標準値」なので、必ず :verify
    (未確認フラグ + 確認方法) を伴う。申請直前の実値確認は手続きの一部。
  - 提出・官庁接触・支払いを伴う遷移/ステップは :requires-human true。
    このライブラリは next-action を提案するだけで、実行はしない。
  - 法的論点(:legal-questions)は結論を出さず data として保持する。"
  )

(def schema
  "Datomic 互換の属性宣言。**実データが正、ここが写し。**

  以前ここは実データとずれていた（2026-08-06 実測）:
  `:procedure/fee-jpy` は宣言だけで一度も使われず（実データは `:procedure/fee`）、
  `:procedure/standard-period-days` は `long` 宣言なのに実データは
  `{:value n :verify {...}}` の map で、`:procedure/{fee,documents,requirements,
  steps,legal-questions,waste-categories}` と `:document/* :requirement/* :step/*
  :question/*` の 4 族はまるごと未宣言だった。

  **ずれた理由は、この vector をどこも参照していなかったから。** 宣言が
  誰にも検査されなければ、実装が動いても宣言だけが古くなる —— しかも
  『Datomic 互換 schema がある』と読めるので、外からは気付けない。
  `schema_test.cljc` が宣言と実データの双方向一致を検査する（片方向だと
  未使用の宣言が残り続ける）。

  ## 複合値の扱い

  `:verify` を伴う標準値（手数料・標準処理期間）は **queryable なスカラと
  検証フラグに分けて**宣言する。map のまま 1 属性にすると『¥19,000 の手続きを
  探す』が書けない —— この library の目的は procedure-as-data なので、
  値が query から見えないなら data として持っている意味が薄い。

  ネストした集合（steps / documents / requirements / legal-questions）は
  それぞれ独立した entity 族なので `:db.type/ref` の cardinality/many。"
  [;; procedure(手続きテンプレート)
   {:db/ident :procedure/id :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one :db/unique :db.unique/identity}
   {:db/ident :procedure/name :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :procedure/law :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :procedure/authority :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :procedure/window :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   ;; **法域軸。** 以前は属性が 1 つも無く、日本であることが暗黙だった。
   ;; ISO 3166-1 alpha-3。国より細かい単位（都道府県・州）は :procedure/window が
   ;; 持つ —— そちらは窓口であって法域ではないので、混ぜない。
   {:db/ident :procedure/jurisdiction :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   ;; **法の適用範囲。** 昨日この schema は「国より細かい単位は `:procedure/window`
   ;; が持つ」と決めたが、同じ docstring が「窓口は法域ではない」とも言っている。
   ;; **GBR がその設計判断が最初に破れる法域になった**（実測 2026-08-07）:
   ;; Scrap Metal Dealers Act 2013 の extent は England and Wales のみ、
   ;; 廃棄物運搬業登録は England のみで、どちらも `"GBR"` の全域を覆わない。
   ;; 窓口とは別の軸なので別属性にする。省略時は法域全域を意味する。
   {:db/ident :procedure/extent :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   ;; **通貨中立の手数料。** `:procedure/fee-jpy` は型に JPY を焼いていたので、
   ;; 日本以外の手続きを収録した瞬間に嘘になる。金額と通貨を分ける。
   ;; **最小単位の整数で持つ。** 昨日は素朴に `long` で「額」を宣言したが、
   ;; GOV.UK の廃棄物運搬業登録は **£191.02** で整数ではない（実測 2026-08-07）。
   ;; JPY は最小単位の端数を持たないので既存 2 本では顕在化しなかった ——
   ;; **最初の非 JPY を収録した瞬間に破れる型**だった。
   ;; 浮動小数で金額を持たないため、値は最小単位（pence / cent / 円）の整数にし、
   ;; 1 通貨単位あたりの最小単位数を `:procedure/fee-minor-unit` で持つ
   ;; （GBP/EUR は 100、JPY は 1）。
   {:db/ident :procedure/fee-amount :db/valueType :db.type/long :db/cardinality :db.cardinality/one}
   {:db/ident :procedure/fee-minor-unit :db/valueType :db.type/long :db/cardinality :db.cardinality/one}
   {:db/ident :procedure/fee-currency :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :procedure/fee-kind :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   {:db/ident :procedure/fee-verify :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   ;; ## 額を決めるのは誰か
   ;;
   ;; **`:procedure/fee-amount` が意味を持つのは、額を法が全国一律に定めている
   ;; ときだけ。** 額を下位の当局が決める制度で「代表額」を 1 つ書くと、
   ;; その 1 当局の値が制度全体の額として読まれる —— 残りの全当局について嘘になる。
   ;;
   ;; 実測でこれが 2 制度に当たった: GBR scrap metal は council が決め
   ;; £181〜£804.78（4.4 倍）、DEU は州が決め、しかも州によっては幅で定める。
   ;; どちらも `:amount` を**書けなかった**ので観測値が散文（`:verify` 文字列と
   ;; ns docstring）に閉じ込められていた —— 読めるが引けない状態。
   ;;
   ;; **level が区別しているのは「誰が偉いか」ではなく「全国値が存在するか」。**
   ;;
   ;;   :statute            額が法令本文にある。全国一律
   ;;   :national-authority 国の規制庁が権限に基づき定める。全国一律だが法定ではない
   ;;                       （England の廃棄物運搬業 £191.02 は Environment Agency の
   ;;                        charging scheme で、改定に法改正を要さない ——
   ;;                        実際 2025-10 の £184 から動いている）
   ;;   :statute-standard   国が標準額を定め、下位の当局が条例でそれに拠る
   ;;                       （日本の手数料条例など）。一律でも純粋な自治でもない
   ;;   :sub-national       各当局が自分で決める。**全国値は存在しない**
   ;;
   ;; 最初の 3 つは `:procedure/fee-amount` を書いてよい。最後の 1 つは書けない ——
   ;; どの当局の値を選んでも残り全部について嘘になる。
   {:db/ident :procedure/fee-set-by-level :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   {:db/ident :procedure/fee-set-by-body :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :procedure/fee-set-by-basis :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   ;; ## 観測 —— これは「幅」ではない
   ;;
   ;; 個々の当局について実際に引いた額。**この集合の min/max を制度の幅として
   ;; 出さない。** Leeds £181 と Kirklees £804.78 は「£181〜£804.78 が法定の幅」
   ;; ではなく「私が見た 4 つの council がその範囲だった」でしかない。£900 の
   ;; council が無い証拠はどこにもない。
   ;;
   ;; 一方 Berlin の 250–5.000 € は**その州の規則自身が幅として定めている**もので、
   ;; 法的な対象が違う。だから幅は observation の**中**にだけ置き、`:procedure/fee`
   ;; の直下には置かない —— 直下に幅があると、それが法定なのか標本なのかを
   ;; 読み手が区別できない。この 2 つを 1 つの表現に混ぜないことが、この family を
   ;; 足した理由そのものである。
   ;;
   ;; **観測は `:procedure/fee` の中ではなく外に置く。** 中に入れると
   ;; 「この手続きの手数料」という 1 つの値の一部に見えるが、観測はそれぞれ
   ;; 別の当局についての別個の事実で、それ自体が entity である。
   {:db/ident :procedure/fee-observations :db/valueType :db.type/ref :db/cardinality :db.cardinality/many}
   {:db/ident :fee-observation/id :db/valueType :db.type/string :db/cardinality :db.cardinality/one :db/unique :db.unique/identity}
   {:db/ident :fee-observation/procedure :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   {:db/ident :fee-observation/authority :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   ;; ## 何の額かは 2 軸ある。1 つの keyword に畳まない
   ;;
   ;; 最初 `:variant` 1 本に `:site-new` `:collector-renewal` と畳もうとしたが、
   ;; **実測 14 council のうち 6 つが『Grant/Renewal』と 1 つの額で示していた**
   ;; （Bradford・Cornwall・Wrexham 等）。これを `:site-new` と書くと、
   ;; その council が**新規と更新を区別していないという事実そのものが消える**。
   ;; 残り 8 つのうち複数は種別も段階も書かず額だけを出している。
   ;;
   ;;   :licence-type  何の免許か   :site :collector :unspecified
   ;;                               / DEU は :erlaubnis(§54) :anzeige(§53)
   ;;   :stage         どの段階か   :new :renewal :change
   ;;                               :grant-or-renewal :grant-or-change :unstated
   ;;
   ;; `:grant-or-renewal` は「両方に同じ額」であって「調べていない」ではない。
   ;; `:unstated` は「当局が書いていない」。**この 2 つを同じ値にしない** ——
   ;; 前者は当局の設計、後者はこちらの限界で、責任の所在が違う。
   {:db/ident :fee-observation/licence-type :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   {:db/ident :fee-observation/stage :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   ;; **当局が「何年度の額か」を書いているか。** `:as-of`（こちらが読んだ日）とは
   ;; 別の事実。実測 14 council のうち年度を書いていたのは 2 つだけで、しかも
   ;; うち 1 つ（Cornwall）は同じ表で 2026-2027 と『Effective from 1st April 2025』が
   ;; 矛盾していた。**残り 12 は年度不明であって『今年度』ではない。**
   {:db/ident :fee-observation/fee-year :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   ;; ## 額の「形」は 5 つある。幅を既定にしない
   ;;
   ;; 最初この family は `:amount` か `[:range-min :range-max]` の 2 択で書いた。
   ;; **ドイツ 16 州を実測して、その 2 択では 5 州が表現できないと分かった**
   ;; （2026-08-07）:
   ;;
   ;;   :fixed         定額。Hessen（電子 800 € / 紙 1.000 €）—— 16 州で唯一
   ;;   :range         両端が定まった幅。11 州。BY 250–6.000 €、SL 100–10.000 € 等
   ;;   :floor         下限のみ、上限なし。NI「時間費用、ただし最低 160 €」、HH ≥371 €
   ;;   :ceiling       上限のみ、下限なし。MV「時間費用、最高 5.500 €」
   ;;   :no-amount-set **規則が額を一切定めない。** NRW は純粋な時間手数料で、
   ;;                  額は所管庁の時間単価 × 実所要時間としてしか出ない
   ;;
   ;; **`:no-amount-set` は「調べていない」ではなく「額という形の答えが無い」。**
   ;; この 2 つを同じ空欄にすると、NRW を調査漏れと読ませてしまう。
   ;;
   ;; 「§54 の手数料は州ごとに幅で定まっている」という一般化は 16 州中 11 州に
   ;; しか当たらない。**幅を既定の形として型に焼かない**のはそのため。
   {:db/ident :fee-observation/rule-form :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   {:db/ident :fee-observation/amount :db/valueType :db.type/long :db/cardinality :db.cardinality/one}
   ;; **開いた端を欠測と区別する。** `:floor` は上限が無いのであって、上限を
   ;; 調べていないのではない。`:rule-form` がどちらかを言う。
   {:db/ident :fee-observation/range-min :db/valueType :db.type/long :db/cardinality :db.cardinality/one}
   {:db/ident :fee-observation/range-max :db/valueType :db.type/long :db/cardinality :db.cardinality/one}
   ;; ## 提出経路で額が変わる制度がある
   ;;
   ;; Hessen §54 は電子 800 € / 紙 1.000 €、Sachsen-Anhalt §53 は紙 100 € /
   ;; 電子 75 €、Hessen §53 と Niedersachsen §53 は電子だけ無料。
   ;; **4 州で確認**した以上、note に書いて済ませる軸ではない。
   ;; `:any` は「経路で変わらない」であって「調べていない」ではない。
   {:db/ident :fee-observation/channel :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   ;; ## 「規則がそう定めている」と「所管庁がそう言っている」を分ける
   ;;
   ;;   :instrument          条例・規則の行項目まで辿れた。11 州
   ;;   :authority-guidance  所管庁の公式表明（ポータル・Merkblatt）だが
   ;;                        条文の行項目に対応づかない。HB / ST / TH の 3 州
   ;;   :practice            運用上の平均・実績値。条文には現れない
   ;;
   ;; **この区別は Niedersachsen が要求した。** 条文（AllGO 2.1.35）は
   ;; 「時間費用、ただし最低 160 €」で、以前この library が記録していた
   ;; 「平均 ca. 360 €」は所管庁 Merkblatt の運用平均だった —— 数値は正しいが
   ;; 法的性格の記述が誤っていた。両方を別の observation として持ち、
   ;; どちらが規則でどちらが実務かを `:source-kind` が言う。
   ;;
   ;; Thüringen はさらに極端で、ThürVwKostOMUEN に §§53/54 の項目自体が無い
   ;; （条例が 2012 年の KrWG 施行に追随せず旧法の Transportgenehmigung のまま）。
   ;; ポータルの 250–5.000 € は所管省が承認した表明だが、条文の裏付けは無い。
   {:db/ident :fee-observation/source-kind :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   ;; 「ca.」「平均」としか書かれていない値。確定額と同じ列に置くが、
   ;; **確定額のふりをさせない。**
   {:db/ident :fee-observation/approximate? :db/valueType :db.type/boolean :db/cardinality :db.cardinality/one}
   ;; いつ引いたか。手数料は改定される（GBR 廃棄物運搬業は 2025-10 の £184 から
   ;; 2026-08 の £191.02 へ実際に動いた）ので、日付の無い額は検証できない。
   {:db/ident :fee-observation/as-of :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :fee-observation/source-url :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :fee-observation/basis :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :fee-observation/note :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :procedure/standard-period-days :db/valueType :db.type/long :db/cardinality :db.cardinality/one}
   {:db/ident :procedure/standard-period-verify :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   ;; 有効期間。**nil を 0 にしない** —— 古物商許可のように更新制度が無い手続きが
   ;; あり、0 年と「期限なし」は別のこと。属性を出さないことで表す。
   {:db/ident :procedure/valid-years :db/valueType :db.type/long :db/cardinality :db.cardinality/one}
   {:db/ident :procedure/requirements :db/valueType :db.type/ref :db/cardinality :db.cardinality/many}
   {:db/ident :procedure/steps :db/valueType :db.type/ref :db/cardinality :db.cardinality/many}
   {:db/ident :procedure/documents :db/valueType :db.type/ref :db/cardinality :db.cardinality/many}
   {:db/ident :procedure/legal-questions :db/valueType :db.type/ref :db/cardinality :db.cardinality/many}
   ;; 手続き固有の分類。**2 つの手続きが別の属性名を使っている**（実測）:
   ;; sanpai は `:procedure/waste-categories`（産廃の品目）、kobutsu は
   ;; `:procedure/categories`（古物の区分）。同じ概念だが語彙が違うので統合せず
   ;; 両方宣言する —— 片方に寄せると、その手続きの用語ではない名前で保持することになる。
   ;; **出所。** この library の原則は「捏造ゼロ・標準値には :verify」なのに、
   ;; URL を持てる属性が 1 つも無く、出所が ns docstring とコメントにしか
   ;; 無かった（3 本の非 JPN を書いた際に 3 者が独立に指摘）。
   ;; `cloud-itonami-licensed-operator` は `:rule/url` を持っている ——
   ;; data として query できないと、出所は「書いてあるが引けない」ままになる。
   {:db/ident :procedure/source-urls :db/valueType :db.type/string :db/cardinality :db.cardinality/many}
   {:db/ident :procedure/waste-categories :db/valueType :db.type/keyword :db/cardinality :db.cardinality/many}
   {:db/ident :procedure/categories :db/valueType :db.type/keyword :db/cardinality :db.cardinality/many}
   ;; 複合値そのもの。datom 面へは下の 4 スカラに展開されるが、**library の
   ;; 実データはこの map で持つ**（`:verify` を値から離さないため）。
   {:db/ident :procedure/fee :db/valueType :db.type/ref :db/cardinality :db.cardinality/one}
   ;; requirement(許可要件)
   {:db/ident :requirement/id :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one :db/unique :db.unique/identity}
   {:db/ident :requirement/name :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :requirement/detail :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   ;; 実データは `blocking?`（述語形）。**宣言側を実データに合わせる** ——
   ;; 逆をやると 1 つの概念に 2 つの名前ができる。
   {:db/ident :requirement/blocking? :db/valueType :db.type/boolean :db/cardinality :db.cardinality/one}
   ;; step(手順)
   {:db/ident :step/id :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one :db/unique :db.unique/identity}
   {:db/ident :step/order :db/valueType :db.type/long :db/cardinality :db.cardinality/one}
   {:db/ident :step/title :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :step/detail :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   ;; 提出・官庁接触・支払いを伴う step。**この library は提案するだけで実行しない。**
   {:db/ident :step/requires-human :db/valueType :db.type/boolean :db/cardinality :db.cardinality/one}
   {:db/ident :step/errand :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   ;; document(必要書類)
   {:db/ident :document/id :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one :db/unique :db.unique/identity}
   {:db/ident :document/name :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :document/who :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   ;; legal-question(法的論点)。**結論を出さず data として保持する。**
   {:db/ident :question/id :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one :db/unique :db.unique/identity}
   {:db/ident :question/title :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :question/detail :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :question/status :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   ;; case(案件)
   {:db/ident :case/id :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one :db/unique :db.unique/identity}
   {:db/ident :case/procedure :db/valueType :db.type/ref :db/cardinality :db.cardinality/one}
   {:db/ident :case/applicant :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :case/status :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   {:db/ident :case/done-steps :db/valueType :db.type/keyword :db/cardinality :db.cardinality/many}
   {:db/ident :case/collected-docs :db/valueType :db.type/keyword :db/cardinality :db.cardinality/many}])

(def statuses
  [:not-started :preparing :ready-to-submit :submitted :under-review
   :granted :rejected :withdrawn])

(def transitions
  "有効な状態遷移。:human のものは human-approved な event でしか進めない
  (提出・取り下げ・官庁の処分の記録は必ず人間の確認を経る)。"
  {:not-started     {:preparing :auto}
   :preparing       {:ready-to-submit :auto}
   :ready-to-submit {:submitted :human
                     :preparing :auto}
   :submitted       {:under-review :auto
                     :withdrawn :human}
   :under-review    {:granted :human
                     :rejected :human
                     :withdrawn :human}})

(defn transition-kind
  "from → to が有効なら :auto / :human、無効なら nil。"
  [from to]
  (get-in transitions [from to]))

(defn unverified
  "標準値に付ける『申請前に実値確認せよ』フラグ。"
  [how]
  {:status :unverified
   :how how
   :note "行政の手数料・様式・処理期間は改定されうる。申請直前に必ず最新値を確認する(ADR-2607141620 捏造ゼロ原則)。"})
