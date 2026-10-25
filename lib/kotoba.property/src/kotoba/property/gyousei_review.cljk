(ns kotoba.property.gyousei-review
  "行政事業レビューシート（行政改革推進本部）の**支出先上位 10 者リスト**から、
   国の支出を受けた法人を法人番号付きで取り出す。

   ## なぜこれが要るか

   これまで「誰が交付を受けたか」は **gBizINFO 経由でしか持っていなかった**
   （ADR-2608181000 Consequences）—— つまり経済産業省が集約したものを読んでいる
   だけで、原典から組み立ててはいなかった。レビューシートは**各府省が自分の事業に
   ついて出す一次資料**で、1 事業あたり上位 10 者の 支出先・**法人番号**・支出額・
   契約方式・落札率 を持つ。

   実測 2026-08-19（`database240918.xlsx`）: 5,442 事業 × 14,298 列。

   ## 個人は取らない

   支出先には個人事業主や個人が現れうる。**法人番号を持つか、法人格の語を名前に
   持つもの以外は落とす**（落とした数は manifest に出す —— 黙って減らさない）。
   官報の清算人・PR TIMES の代表者と同じ線。

   ## 金額は百万円単位の申告値

   `支出額（百万円）` はシート上の申告値で、円に直すときは丸めが入っている。
   **円に正規化しない** —— `:grant/amount-million-jpy` として原文の単位のまま持つ。
   gBizINFO の `:grant/amount-yen` と足し合わせられないのはそのためで、
   混ぜたい者に気付かせる方が、静かに桁を間違えるより良い。"
  (:require [kotoba.lang.text :as str]))

(def dataset "gyousei-review")
(def authority-id "JP/GYOUKAKU-Review")
(def licence "行政事業レビューシート（内閣官房行政改革推進本部）— 政府標準利用規約")
(def attribution "出典：行政事業レビューシートのデータベース（内閣官房行政改革推進本部）https://www.gyoukaku.go.jp/review/database/ を加工して作成")

(def program-columns
  "事業側の列。**列文字ではなくヘッダ名で引く** —— 年度版で列が動く。"
  {"府省庁" :grant/ministry
   "事業名" :grant/title
   "事業開始年度" :program/start-year
   "会計区分" :program/account-class})

(def ^:private recipient-field-re
  ;; 「支出先上位１０者リスト-A.支払先-3-法人番号-01」のような列名。
  ;; block = A/B/C…（事業内の支出区分）、seq = 支払先の順位。
  #"^支出先上位１０者リスト-([A-Z])\.支払先-(\d+)-(.+?)-\d+$")

(defn- parse-rank
  ;; ⚠ `.cljc` に `js/parseInt` を直書きしない —— JVM 側のテストが
  ;; `No such namespace: js` で落ちる（実測 2026-08-19）。
  [s]
  #?(:clj (Long/parseLong (str s))
     :cljs (js/parseInt (str s) 10)))

(defn recipient-column
  "列名 -> `{:block \"A\" :seq 3 :field :houjin-bangou}`、それ以外は nil。"
  [header]
  (when-let [[_ block seq* field] (re-find recipient-field-re (str header))]
    (let [f (case field
              "支出先" :name
              "法人番号" :houjin-bangou
              "支出額（百万円）" :amount-million-jpy
              "契約方式等" :contract-method
              "落札率" :winning-rate
              nil)]
      ;; key は `:rank`（`:seq` にすると呼び出し側で `clojure.core/seq` を
      ;; 隠す名前になりやすい）。
      (when f {:block block :rank (parse-rank seq*) :field f}))))

(def placeholder-re
  "**支出先ではない記入**。シートには「【なし】」「【調査中】」「〃」「○○」
   「↑昨年のままとなっています」のような欄が実在する（実測 2026-08-19、
   落とした 2,446 名を分類して出てきた）。

   これを「組織と言えないので落とした」に混ぜると、**個人を守って落とした数**と
   **そもそも相手が書かれていない数**が同じ数字になる。分けて数える。"
  ;; 「その他」「その他（多数）」も相手ではなく**まとめ欄**である（実測 2026-08-19）。
  #"^(【?(なし|無し|該当なし|調査中|未定|非公表)】?|〃|同上|その他(（[^）]*）)?|○+|●+|-+|―+|ー+|\s*)$|昨年のまま|記入|↑")

(defn placeholder? [s] (boolean (re-find placeholder-re (str/trim (str s)))))

(def organization-marker-re
  ;; インラインの `(?i)` を書かない（JS が `Invalid group` で落ちる）。小文字化して当てる。
  ;;
  ;; ⚠ **2 度広げている。** 最初は法人格の語だけで 13,669 行を落とし、中身は
  ;; 協議会・センター・法務局だった。2 度目（実測 2026-08-19、残り 2,446 名の分類）で
  ;; **官公署 244・共同企業体/JV/共同提案体 217・学校 49** がまだ落ちているのが見えた。
  ;; **落とした物を毎回見ない限り、規則は静かに狭いまま。**
  #"株式会社|株式會社|有限会社|合同会社|合資会社|合名会社|相互会社|一般社団法人|公益社団法人|一般財団法人|公益財団法人|医療法人|学校法人|宗教法人|社会福祉法人|特定非営利活動法人|npo法人|独立行政法人|国立研究開発法人|国立大学法人|公立大学法人|地方独立行政法人|協同組合|事業協同組合|農業協同組合|漁業協同組合|信用金庫|信用組合|連合会|振興会|協議会|委員会|審議会|機構|公社|公団|事業団|基金|センター|研究所|研究センター|試験場|事務所|法務局|財務局|運輸局|気象台|保健所|病院|大学|学園|高等専門学校|学校|協会|財団|社団|組合|共同企業体|共同提案体|共同体|コンソーシアム|プロジェクトチーム|連携会議|ｊｖ|jv|省$|庁$|局$|署$|部$|課$|裁判所|検察庁|大使館|領事館|市$|町$|村$|都$|道$|府$|県$|区$|[a-z]")

(def ^:private person-name-re
  ;; 逆向きの安全弁: **人名の形をしているものは、marker に当たっても落とす。**
  #"^[一-龥]{2,4}[\s　]+[一-龥]{1,4}$")

(defn organization?
  "組織だと言えるか。**法人番号が付いていれば確実**（個人には無い）。無い場合は
   名前の形で判断する —— 組織語を含み、かつ人名の形をしていないこと。"
  [name houjin-bangou]
  (boolean (and (not (str/blank? (str name)))
                (not (re-matches person-name-re (str/trim (str name))))
                (or (re-matches #"[0-9]{13}" (str houjin-bangou))
                    (re-find organization-marker-re (str/lower (str name)))))))

(defn- clean [s]
  (let [v (-> (str s) (str/replace #"[\s　]+" " ") str/trim)]
    (when-not (or (str/blank? v) (= "-" v) (= "－" v)) v)))

(defn classify
  "支出先の名前を 3 つに分ける: `:organisation` / `:placeholder`（相手が書かれて
   いない欄）/ `:not-organisation`（個人か、組織だと言えないもの）。"
  [name houjin-bangou]
  (cond
    (placeholder? name) :placeholder
    (organization? name houjin-bangou) :organisation
    :else :not-organisation))

(defn recipient-record
  "1 支出先 -> 1 レコード。組織だと言えないものは nil（推測しない）。"
  [{:keys [program block rank fields publish]}]
  (let [nm (clean (:name fields))
        hb (some-> (clean (:houjin-bangou fields)) (str/replace #"[^0-9]" ""))
        hb (when (re-matches #"[0-9]{13}" (str hb)) hb)]
    (when (and nm (organization? nm hb))
      (cond-> (merge {:source/dataset dataset
                      :grant/kind "subsidy-or-contract"
                      :grant/recipient-name nm
                      :review/block block
                      :review/rank rank}
                     (select-keys program (vals program-columns)))
        ;; ⚠ **年を名乗らない。** シート自身が「支出先上位10者リストの中には、
        ;; 令和２年度、令和３年度に入札等を行ったものが含まれる」と注記しており、
        ;; 支出先行の年度は DB の年度と一致しない。さらに**版と年は 1 対 1 でない**
        ;; —— `database240502`（R04 ページ）と `database240918`（R05 ページ）は
        ;; どちらも 2024 年公表で、年を識別子にすると衝突する（実測 2026-08-19、
        ;; cell を書いて初めて出た）。言えるのは**publish そのもの**だけ。
        publish (assoc :review/database-publish publish)
        hb (assoc :company/houjin-bangou hb :company/registration-no hb)
        (clean (:amount-million-jpy fields))
        (assoc :grant/amount-million-jpy (clean (:amount-million-jpy fields)))
        (clean (:contract-method fields))
        (assoc :grant/contract-method (clean (:contract-method fields)))
        (clean (:winning-rate fields))
        (assoc :grant/winning-rate (clean (:winning-rate fields)))))))

(defn parse-amount
  "「1,234」「0.5」-> 数値、「-」「」「※」-> nil。**読めない値を 0 として足さない**
   （0 を足すと「支出が無かった」と「読めなかった」が同じ合計になる）。"
  [s]
  (let [t (-> (str s) (str/replace #"[,，\s　]" ""))]
    (when (re-matches #"-?\d+(\.\d+)?" t)
      #?(:clj (Double/parseDouble t) :cljs (js/parseFloat t)))))

(defn fold-key [rec] [(:company/houjin-bangou rec) (:grant/ministry rec)])

(defn fold-recipients
  "支出先の行 -> **会社 × 府省** 1 entity。

   面はクエリのたびに全部 load するので、17,808 行の明細は置かない（corpus には
   在る）。畳んだ側が答えるのは「この会社にどの府省が、いくつの事業で、合計いくら
   払ったか」——それ以上が要るなら corpus を引く。

   **読めなかった金額は数える**（`:review/amount-unparsed`）—— 0 として足すと
   「支出が無かった」と「読めなかった」が同じ合計になる。"
  [records]
  (->> records
       (filter :company/houjin-bangou)
       (reduce (fn [acc r]
                 (let [k (fold-key r)
                       amt (parse-amount (:grant/amount-million-jpy r))]
                   (-> acc
                       (update-in [k :payments] (fnil inc 0))
                       (update-in [k :programs] (fnil conj #{}) (:grant/title r))
                       ;; **最大の 1 事業だけ名前を残す。** 畳むと事業名が全部消え、
                       ;; jGrants（公募）と突き合わせる鍵が面から無くなる（実測
                       ;; 2026-08-19: `:grant/title` はプレーン上で nil）。全部載せると
                       ;; 面が太るので、金額が最大の 1 つに絞る —— **その会社への
                       ;; 支出の代表であって、唯一の事業ではない**（件数は
                       ;; `:review/programs` が言う）。
                       (update-in [k :top] (fn [cur]
                                             (if (and amt (or (nil? cur) (> amt (:amount cur))))
                                               {:amount amt :title (:grant/title r)}
                                               cur)))
                       ;; ⚠ **最初に見た名前を代表にしない。** 同じ法人番号に対して
                       ;; シートは表記を揺らす（「札幌市」「札幌市 市立札幌病院」）。
                       ;; 最初の 1 つを載せると、読み手は合計をその表記の主体に
                       ;; 帰属させる —— 実測 2026-08-19、市の合計 209,456 百万円が
                       ;; 「市立札幌病院」の額に見えた（明細では 0.6 百万円）。
                       (update-in [k :names] (fnil conj #{}) (:grant/recipient-name r))
                       (update-in [k :name-counts (:grant/recipient-name r)] (fnil inc 0))
                       (update-in [k :publish] #(or % (:review/database-publish r)))
                       (cond-> amt (update-in [k :total] (fnil + 0) amt))
                       (cond-> (nil? amt) (update-in [k :unparsed] (fnil inc 0))))))
               {})
       (mapv (fn [[[hb ministry] v]]
               (cond-> {:source/dataset dataset
                        :company/houjin-bangou hb
                        :company/registration-no hb
                        ;; 代表は**最も多く現れた表記**（同数なら短い方）。
                        :company/legal-name (->> (:name-counts v)
                                                 (sort-by (fn [[nm n]] [(- n) (count (str nm))]))
                                                 ffirst)
                        :grant/ministry ministry
                        :grant/kind "subsidy-or-contract"
                        :review/payments (:payments v)
                        :review/programs (count (:programs v))}
                 (:publish v) (assoc :review/database-publish (:publish v))
                 (:total v) (assoc :review/total-million-jpy
                                   #?(:clj (format "%.1f" (:total v))
                                      :cljs (.toFixed (:total v) 1)))
                 (:unparsed v) (assoc :review/amount-unparsed (:unparsed v))
                 (get-in v [:top :title]) (assoc :review/largest-program (get-in v [:top :title]))
                 ;; 表記が 1 つでないことを**数で言う** —— 代表名だけを見た読み手が
                 ;; 合計をその表記に帰属させないため。
                 (> (count (:names v)) 1) (assoc :review/name-variants (count (:names v))))))
       (sort-by (juxt :company/houjin-bangou :grant/ministry))
       vec))

(defn corpus-manifest
  [{:keys [observed-at record-count programs recipients-seen dropped-individuals
           with-houjin-bangou publish source-url organisations-seen queried
           folded-from placeholder-rows]}]
  (cond-> {:corpus/manifest true
           :corpus/projection true
           :corpus/format :edn-lines
           :source/dataset dataset
           :source/authority authority-id
           :source/licence licence
           :source/attribution attribution
           :source/observed-at observed-at}
    publish (assoc :source/publish publish)
    source-url (assoc :source/url source-url)
    programs (assoc :projection/programs programs)
    ;; 分母 3 つ: 見た支出先、法人番号が付いたもの、個人として落としたもの。
    ;; **落とした数を出さないと「国の支出先はこれで全部」に読める。**
    recipients-seen (assoc :projection/recipients-seen recipients-seen)
    ;; 絞る前に何件が組織として残ったか、そして何番号で絞ったか。**この 2 つが
    ;; 無いと、絞った結果が「国の支出先はこれで全部」に読める。**
    organisations-seen (assoc :projection/organisations-seen organisations-seen)
    ;; 相手が書かれていない欄（「【なし】」「〃」「調査中」）。**個人を守って落とした
    ;; 数と分ける** —— 混ぜると規則の厳しさも記入漏れの多さも読めない。
    placeholder-rows (assoc :projection/placeholder-rows placeholder-rows)
    (pos? (or queried 0)) (assoc :projection/queried queried)
    with-houjin-bangou (assoc :projection/with-houjin-bangou with-houjin-bangou)
    (some? dropped-individuals) (assoc :projection/dropped-not-organisation dropped-individuals)
    ;; 畳んだ側は**畳む前の行数**を持つ（ADR-2608181000 16 節と同じ規律）。
    folded-from (assoc :projection/folded-from folded-from)
    record-count (assoc :corpus/record-count record-count)))
