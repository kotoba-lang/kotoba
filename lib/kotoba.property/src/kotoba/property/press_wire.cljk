(ns kotoba.property.press-wire
  "プレスリリース配信サイトの公開フィードを読む（いまは PR TIMES）。

   ## なぜ配信サイトか

   実測 2026-08-19: 追跡している 1,040 社のうち**自社サイトに feed を持つのは 41 社**
   （`kotoba.property.web-presence`）。日本のプレスリリースは PR TIMES 等の配信
   サイトに集まるので、残り 96% はそちらでしか拾えない。

   ## フィードは窓ではなく標本

   `index.rdf` は 200 件を返すが、それは「最新 200 件」ではない —— 数分あけて
   取り直すと 129〜165 件が入れ替わり、1 回が張る期間も 6.8 日〜28 日と動く。
   したがって**全リリースを網羅することはできない**し、「1 日 N 件」という率も
   このフィードからは出せない。貯まるのは増え続ける標本である。

   ## 何を保存して、何を保存しないか

   保存するのは**引用の形**だけ —— 見出し・URL・配信日時・発表者名。
   本文（`<description>`）は発表者の著作物なので**入れない**。newsfeed の
   `:news.source/rightsPolicy \"fair-use-quote\"` と同じ線を、こちらでも引く。

   ## robots.txt を読んでから来ている

   - PR TIMES: `Allow: /`（除外は like_count / releaseimage / m3u8 の 3 つだけ）。
     公式 RSS 1.0 が `https://prtimes.jp/index.rdf` に在る。
   - ValuePress: **`Disallow: /rss/`** —— feed を明示的に禁じているので**使わない**。
   - DreamNews: robots.txt が 503 で読めない → 許可を確認できないので**使わない**。
   - 共同通信 PR ワイヤー / @Press: robots.txt は歓迎的だが、autodiscovery に
     feed が無い。HTML を掻きに行くのはここでは選ばない。

   出典：PR TIMES（株式会社 PR TIMES）https://prtimes.jp/ の公開 RSS を加工して作成"
  (:require [kotoba.lang.text :as str]))

(def dataset "press-wire")

(def distributors
  {:prtimes {:id "prtimes"
             :name "PR TIMES"
             :feed-url "https://prtimes.jp/index.rdf"
             :authority "JP/PR-TIMES"
             :attribution "出典：PR TIMES（株式会社PR TIMES）https://prtimes.jp/ の公開 RSS を加工して作成"
             ;; **窓ではなく標本である。** 実測 2026-08-19:
             ;;   - 5 秒あけた 2 回の取得は 200/200 完全一致（瞬間的には安定）
             ;;   - 数分あけると 129〜165 件が入れ替わる
             ;;   - 1 回の取得が張る期間は 6.8 日だったり 28 日だったりする
             ;; つまり `index.rdf` は「最新 200 件」ではなく**直近 1 ヶ月ほどからの
             ;; 回転する標本**で、ここから「1 日あたり何件」は出せない。巡回間隔を
             ;; 窓の広さから導けないので、**礼儀と逓減する取り分**で日次にしている。
             ;; 毎回およそ 130〜165 件が新規なので、貯めれば標本は増え続ける。
             :sample-items 200}})

(defn- tag [block name]
  (some-> (re-find (re-pattern (str "<" name "[^>]*>([\\s\\S]*?)</" name ">")) block)
          second
          str/trim
          (str/replace #"^<!\[CDATA\[" "")
          (str/replace #"\]\]>$" "")))

(def ^:private item-re #"<item\s+rdf:about[^>]*>([\s\S]*?)</item>")

(defn parse-items
  "PR TIMES の RDF -> レコード。**本文は取らない。**

   `<items><rdf:Seq>` の中にも `rdf:li` が並ぶが、あれは目次であって item ではない
   （`<item rdf:about=…>` だけを見る）。"
  [xml {:keys [id authority] :as distributor} observed-at]
  (for [[_ block] (re-seq item-re (str xml))
        :let [title (tag block "title")
              link (tag block "link")
              corp (tag block "dc:corp")]
        :when (and (not (str/blank? (str title))) (not (str/blank? (str link))))]
    (cond-> {:source/dataset dataset
             :source/authority authority
             :source/observed-at observed-at
             :press/distributor id
             :press/title title
             :press/url link}
      corp (assoc :press/company-name corp)
      (tag block "dc:date") (assoc :press/published-at (tag block "dc:date"))
      (tag block "business_form") (assoc :press/business-form (tag block "business_form")))))

(defn release-key
  "同じリリースを 2 度書かないための鍵。URL がリリースごとに一意なのでそれを使う
   （PR TIMES の URL は `/main/html/rd/p/<release>.<company>.html`）。"
  [r]
  (:press/url r))

(defn with-company
  "名寄せの結果を 1 件のリリースに反映する。**解決しなかったものも捨てない** ——
   配信サイトの発表者名は登記上の商号とは限らない（ブランド名・屋号・英字表記）ので、
   未解決は「この会社は存在しない」ではなく「この名前では引けない」である。"
  [r hit]
  (if hit
    (assoc r
           :company/houjin-bangou (:houjin-bangou hit)
           :company/registration-no (:houjin-bangou hit)
           :company/legal-name (:legal-name hit)
           :company/name-match (:match hit))
    r))


(def ^:private company-card-re
  ;; PR TIMES のリリースページ末尾にある企業概要カード。tag を落とすと
  ;;   「業種 情報通信 本社所在地 神奈川県横浜市西区… 電話番号 - 代表者名 …」
  ;; という固定の並びになる。**代表者名の手前で切る** ので、この経路では
  ;; 個人名が住所欄に紛れ込みようがない。
  #"本社所在地\s*[：:]?\s*(.+?)\s*(?:電話番号|代表者名|上場|資本金|設立|URL)")

(def ^:private free-text-address-re
  ;; カードが無いページ向けの予備。本文の会社概要ブロック。
  #"(?:所在地|住所)\s*[：:]\s*(.+?)(?:\s*(?:設立|代表|資本金|事業|従業員|URL|TEL|電話|https?://|・|、|。)|$)")

(defn strip-tags [html]
  (when html
    (-> (str html)
        (str/replace #"(?s)<script[^>]*>.*?</script>" " ")
        (str/replace #"(?s)<style[^>]*>.*?</style>" " ")
        (str/replace #"<[^>]+>" " ")
        (str/replace #"&nbsp;" " ")
        (str/replace #"\s+" " "))))

(def ^:private label-cut-re
  ;; ラベルは字間を空けて組まれることがある（「代 表：」「上 場：」）。tag を落として
  ;; 空白を畳んでも空白は 1 つ残るので、`代表` では**当たらない**。実測 2026-08-19、
  ;; この 1 件で「京都府…655番地 創 業： 1976年12月 上 場： … 代 表：」を住所として
  ;; 書き出しかけた。字の間に空白を許す形で切る。
  #"\s*(?:創\s*業|上\s*場|代\s*表|設\s*立|資\s*本\s*金|事\s*業|従\s*業\s*員|電\s*話|所\s*在\s*地|U\s*R\s*L|TEL|https?://).*$")

(defn- clean-address [addr]
  (when addr
    (let [a (-> (str addr)
                (str/replace label-cut-re "")
                (str/replace #"^〒?\s*[0-9０-９]{3}[-‐ー－]?[0-9０-９]{4}\s*" "")
                (str/replace #"[・、。]\s*$" "")
                str/trim)
          squeezed (str/replace a #"\s" "")]
      (when (and (>= (count a) 4)
                 (re-find #"(都|道|府|県)" a)
                 ;; 個人名・役職が混ざったものは住所として採らない（捨てる方を選ぶ）。
                 ;; 判定は空白を除いてから行う —— 空白入りの組版に負けないため。
                 (not (re-find #"代表|取締役|社長|理事|部長|設立|資本金" squeezed)))
        a))))

(defn issuer-address
  "リリースページから発表者の**所在地だけ**を取る。

   同じブロックに「代表者名 上田英介」が並ぶが、**取らない** —— gbizinfo/basic-record
   や官報の発注機関と同じ線で、公表物であっても個人名は持ち歩かない。ここで欲しいのは、
   同名 2 社を分ける都道府県だけである。`clean-address` は役職語を含む候補を
   救おうとせず捨てる —— 名前が 1 件混じるより住所が 1 件足りない方がよい。"
  [html]
  (when-let [t (strip-tags html)]
    (or (clean-address (second (re-find company-card-re t)))
        (clean-address (second (re-find free-text-address-re t))))))

(defn issuer-company-id
  "リリース URL に既に入っている PR TIMES の企業 ID。

   `…/rd/p/000000136.000143568.html` の後半 `000143568` が
   `prtimes.jp/main/html/searchrlp/company_id/143568` と同じ ID。つまり
   **発表者の同一性はフィードだけで分かる** —— 名寄せのために 1 ページも取る
   必要がない（住所を取りに行くのは、法人番号に結び付けるときだけ）。"
  [url]
  (when url
    (when-let [m (re-find #"/rd/p/\d+\.(\d+)\.html" (str url))]
      (str/replace (second m) #"^0+" ""))))

(defn corpus-manifest
  [{:keys [observed-at distributor record-count seen linked sample-items]}]
  (cond-> {:corpus/manifest true
           :corpus/projection true
           :corpus/format :edn-lines
           :source/dataset dataset
           :source/authority (:authority distributor)
           :source/attribution (:attribution distributor)
           :source/observed-at observed-at
           :press/distributor (:id distributor)}
    sample-items (assoc :corpus/sample-items sample-items)
    seen (assoc :projection/seen seen)
    linked (assoc :projection/linked linked)
    record-count (assoc :corpus/record-count record-count)))
