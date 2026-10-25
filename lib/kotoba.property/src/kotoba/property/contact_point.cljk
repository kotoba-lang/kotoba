(ns kotoba.property.contact-point
  "法人番号 -> **公開連絡点**（問い合わせフォーム URL・公開メール・所在地・代表者名）の
   可搬コントラクト。I/O は 1 バイトも無い。

   ## 出所を 3 段に分ける（`web-presence` が 2 段に分けたのと同じ理由）

   - `:company/location` `:company/representative-name` は **登記由来**
     （gBizINFO 経由の法人番号 registry）。所在地と代表者名は公示された事実である。
   - `:contact/form-url` `:contact/emails` は **こちらが探しに行って、実際に
     取得できたもの**。当てただけでは載せない —— fetch して 200 が返り、
     連絡点らしさを判定してから載せる。
   - `:contact/solicitation-forbidden?` は **相手のサイトがそう書いていた**という
     観測。これが true の行に営業をしないための列であって、こちらの意見ではない。

   混ぜないのは、1 段目が「国がそう記録している」、2 段目が「この URL はこの日
   これを返した」、3 段目が「相手がそう言っている」で、更新の主体が全部違うからである。

   ## 個人のアドレスを既定で載せない

   `classify-email` が local part を見て `:role`（info/contact/sales…）と
   `:personal`（個人名らしきもの）に分ける。既定の出力は `:role` だけで、
   `:personal` は**件数だけ**数える。B2B の窓口に出すのが目的であって、
   個人の連絡先を集めるのが目的ではない。

   ## 「見つからなかった」と「見に行けなかった」を同じ値にしない

   `:lead/status` は 6 値。`:ok` / `:no-website`（登記に URL が無い）/
   `:fetch-failed`（取りに行けなかった）/ `:no-contact-point`（取れたが連絡点が
   無かった）/ `:robots-disallowed`（robots.txt が拒んだ）/ `:unresolved`
   （社名を法人番号に解決できなかった）。**測れなかった終わり方を 1 つの nil に
   畳むと、測れなかった行が「連絡先の無い会社」として並ぶ。**

   出典：gBizINFO（経済産業省）https://info.gbiz.go.jp/ を加工して作成 +
   各社の自己公表ページ（`:source/observed-at` に取得時刻、`:contact/source-url` に URL）"
  (:require [kotoba.lang.text :as str]))

(def dataset "lead-contact-point")
(def authority-id "JP/METI-gBizINFO+self-published")
(def attribution
  "出典：gBizINFO（経済産業省）https://info.gbiz.go.jp/ を加工して作成。連絡点は各社の自己公表ページ。")

(def user-agent
  "自分を名乗る。robots.txt の突き合わせもこの token で行う。"
  "murakumo-lead-collector/1.0 (+https://murakumo.cloud/; hello@murakumo.cloud)")

(def statuses
  "`:lead/status` の値域。**閉じている** —— 新しい終わり方を足すときはここに足す。"
  #{:ok :no-website :fetch-failed :no-contact-point :robots-disallowed :unresolved})

;; ---------------------------------------------------------------------------
;; URL

(defn normalise-url
  "末尾スラッシュの有無だけで別 URL にしない。scheme が無いものは弾く。"
  [u]
  (when-let [u (some-> u str str/trim)]
    (when (re-find #"^https?://" u)
      (str/replace u #"/+$" ""))))

(defn origin
  "https://a.example.jp/x/y -> https://a.example.jp。解析できなければ nil。"
  [u]
  (when-let [m (re-find #"^(https?://[^/?#]+)" (str u))]
    (second m)))

(defn absolutise
  "href を base に対して絶対化する。base は origin でも深いパスでもよい。"
  [href base]
  (let [href (some-> href str str/trim)]
    (cond
      (str/blank? href) nil
      (str/starts-with? href "#") nil
      (str/starts-with? href "javascript:") nil
      ;; `mailto:` / `tel:` はページの住所ではない。落とさないと origin に継ぎ足されて
      ;; `https://host/mailto:info@example.jp?subject=...` という**実在しない URL**が
      ;; 候補として並ぶ（実測 2026-08-26、TKC 会員事務所のページ）。fetch は失敗するので
      ;; 実害は薄いが、候補枠を 1 つ食い、`:lead/note` の候補数を水増しする。
      ;; メールは `extract-emails` が生 HTML から別途拾うので、ここで捨てて失うものは無い。
      (re-find #"(?i)^(mailto|tel|sms|fax|callto):" href) nil
      (re-find #"^https?://" href) (str/replace href #"/+$" "")
      (str/starts-with? href "//") (str "https:" (str/replace href #"/+$" ""))
      (str/starts-with? href "/") (when-let [o (origin base)]
                                    (str o (str/replace href #"/+$" "")))
      :else (when-let [o (origin base)]
              (str o "/" (str/replace href #"^/+|/+$" ""))))))


;; ---------------------------------------------------------------------------
;; 社名の突き合わせ
;;
;; 名前で検索して 1 件目を採ると、**頼んだ会社とは別の会社の行が、他の行と同じ顔で
;; 並ぶ。** 実測 2026-08-25、15 社の名指しリストで 2 件出た:
;;   「株式会社リコー」 -> 「株式会社リコーエンタープライズ（閉鎖）」
;;   「株式会社ABEJA」 -> 「株式会社ABEJARIホールディングス」
;; どちらも `:lead/status :ok` で連絡先まで取れており、**出力からは正しい行と
;; 区別できなかった。** 突き合わせないなら、それは解決ではなく推測である。

(def ^:private zenkaku-ascii-offset 65248) ;; Ａ(U+FF21) - A(U+0041)

(defn- zenkaku-ascii->half [s]
  (str/join
   (map (fn [ch]
          (let [c #?(:clj (int ch) :cljs (.charCodeAt ch 0))]
            (if (and (>= c 65281) (<= c 65374))
              #?(:clj (char (- c zenkaku-ascii-offset))
                 :cljs (.fromCharCode js/String (- c zenkaku-ascii-offset)))
              ch)))
        (seq (str s)))))

(def ^:private corporate-form-re
  #"(株式会社|有限会社|合同会社|合名会社|合資会社|一般社団法人|一般財団法人|公益社団法人|公益財団法人|\(株\)|（株）|Inc\.?|Corp\.?|Co\.,?\s*Ltd\.?|Ltd\.?|K\.K\.?|LLC)")

(defn normalise-company-name
  "突き合わせ用の正規化。全角 ASCII を半角に、法人格と空白と記号を落とし、小文字化。
   **表示には使わない** —— 登記上の名前は registry の値をそのまま出す。"
  [s]
  (-> (str s)
      zenkaku-ascii->half
      (str/replace corporate-form-re "")
      ;; ⚠ 長音符 ー(U+30FC) を文字クラスに入れない。ハイフンのつもりで入れると
      ;; 「ストックマーク」が「ストックマク」になる（実測 2026-08-25）。両側が同じに
      ;; 壊れるので突き合わせ自体は通るが、別語が衝突する余地を作る。
      (str/replace #"[\s　・,、.。\-‐−–－_/\\()（）\[\]「」]" "")
      str/lower))

(def closed-name-re #"(閉鎖|清算結了|解散)")

(defn closed-hit?
  "検索結果が閉鎖・解散済みの法人か。`close_date` が入っていることもあれば、
   名前に「（閉鎖）」と付いているだけのこともある —— 両方見る。"
  [hit]
  (boolean (or (not (str/blank? (str (get hit "close_date"))))
               (re-find closed-name-re (str (get hit "name"))))))

(defn resolve-hit
  "頼んだ社名 + 検索結果 -> `{:hit .. :match :exact}` か `{:rejected [...]}`。

   **完全一致だけを採る。** 前方一致を許すと `abeja` が `abejariholdings` に、
   `リコー` が `リコーエンタープライズ` に当たる —— どちらも実測で起きた。
   一致しなかったときに nil ではなく理由の付いた map を返すのは、
   『解決できなかった』と『解決して連絡先が無かった』を出力で分けるため。"
  [asked-name hits]
  (let [want (normalise-company-name asked-name)
        live (remove closed-hit? hits)
        exact (first (filter #(= want (normalise-company-name (get % "name"))) live))]
    (if exact
      {:hit exact :match :exact}
      {:rejected (mapv (fn [h] {:name (get h "name")
                                :corporate-number (get h "corporate_number")
                                :reason (cond (closed-hit? h) :closed
                                              :else :name-mismatch)})
                       hits)})))

;; ---------------------------------------------------------------------------
;; robots.txt

(defn- robots-groups
  "robots.txt -> [{:agents #{..} :disallow [..] :allow [..]} ...]。
   コメントを落とし、User-agent の連続をひとかたまりに束ねる。"
  [txt]
  (let [lines (->> (str/split-lines (str txt))
                   (map #(str/trim (str/replace % #"#.*$" "")))
                   (remove str/blank?))]
    (:groups
     (reduce
      (fn [{:keys [groups pending] :as acc} line]
        (let [[k v] (str/split line #":" 2)
              k (str/lower (str/trim (str k)))
              v (str/trim (str v))]
          (cond
            (= k "user-agent")
            (if (:open? acc)
              ;; 直前が rule 行なら新しいグループが始まる
              (assoc acc :groups (conj groups {:agents #{(str/lower v)} :disallow [] :allow []})
                         :open? false :pending nil)
              (let [gs (if (seq groups) groups [{:agents #{} :disallow [] :allow []}])
                    gs (update gs (dec (count gs)) update :agents conj (str/lower v))]
                (assoc acc :groups gs :pending pending)))

            (contains? #{"disallow" "allow"} k)
            (if (seq groups)
              (assoc acc :groups (update groups (dec (count groups))
                                         update (if (= k "allow") :allow :disallow) conj v)
                         :open? true)
              acc)

            :else acc)))
      {:groups [] :open? false :pending nil}
      lines))))

(defn- rule-matches? [rule path]
  (and (not (str/blank? rule))
       (str/starts-with? (str path) rule)))

(defn robots-disallows?
  "robots.txt の本文・対象 UA・パスを見て、取りに行ってよいかを答える。

   robots.txt が**取れなかったときは false**（=許可）を返す。これは緩い側の既定だが、
   RFC 9309 がそう定めている（4xx は full allow）。**取れなかったことを呼び手が
   知りたいなら、それは呼び手が status で持つ** —— ここで両者を混ぜない。"
  [robots-txt ua path]
  (let [ua (str/lower (str ua))
        groups (robots-groups robots-txt)
        pick (fn [pred] (seq (filter pred groups)))
        matching (or (pick (fn [g] (some #(and (not= % "*") (str/includes? ua %)) (:agents g))))
                     (pick (fn [g] (contains? (:agents g) "*"))))
        rules (mapcat (fn [g]
                        (concat (map (fn [r] [:allow r]) (:allow g))
                                (map (fn [r] [:disallow r]) (:disallow g))))
                      matching)
        best (->> rules
                  (filter (fn [[_ r]] (rule-matches? r path)))
                  (sort-by (fn [[_ r]] (- (count r))))
                  first)]
    (= :disallow (first best))))

;; ---------------------------------------------------------------------------
;; 連絡点の候補を HTML から拾う

(def ^:private anchor-re #"(?is)<a\s[^>]*href\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a>")

(def contact-href-re
  #"(?i)(contact|inquir|otoiawase|toiawase|お問い?合わ?せ|問い?合わ?せ|form|support/?$)")

(def contact-text-re
  #"(?i)(お問い?合わ?せ|問い?合わ?せ|コンタクト|contact|inquiry|get in touch)")

(defn strip-tags
  "HTML -> 本文らしいテキスト。script/style を落とす。"
  [s]
  (-> (str s)
      (str/replace #"(?is)<script[^>]*>.*?</script>" " ")
      (str/replace #"(?is)<style[^>]*>.*?</style>" " ")
      (str/replace #"(?s)<[^>]+>" " ")
      (str/replace #"&nbsp;?" " ")
      (str/replace #"\s+" " ")
      str/trim))

(defn discover-contact-links
  "HTML から問い合わせページの候補 URL を拾う。**候補であって連絡点ではない** ——
   取得して `contact-page?` を通るまでは載せない。

   href と アンカーテキストの両方を見るのは、日本企業サイトの問い合わせリンクが
   `/contact/` のこともあれば `/cgi-bin/form.cgi?id=3` のこともあるため。
   後者は href からは判らず、テキスト『お問い合わせ』だけが手掛かりになる。

   `opts` に `{:href-re .. :text-re ..}` を渡すと語彙を差し替えられる（EU の
   独語・仏語・西語などに当てるため）。**省略すると日本語の既定** —— 既存の
   呼び手の挙動を変えない。"
  ([html base] (discover-contact-links html base nil))
  ([html base {:keys [href-re text-re]}]
   (let [href-re (or href-re contact-href-re)
         text-re (or text-re contact-text-re)]
     (->> (re-seq anchor-re (str html))
          (keep (fn [[_ href inner]]
                  (let [text (strip-tags inner)]
                    (when (or (re-find href-re (str href))
                              (re-find text-re text))
                      (absolutise href base)))))
          (remove nil?)
          (remove #(re-find #"(?i)\.(pdf|jpe?g|png|gif|zip|docx?|xlsx?)$" %))
          distinct
          vec))))

(def ^:private strong-path-re
  #"(?i)/(contact|inquir(y|ies)|otoiawase|toiawase|form|support/contact)")

(def ^:private decoy-path-re
  ;; `contact-page?` を通るが連絡窓口ではないページ。実測 2026-08-25: Stockmark の
  ;; `/company/information` が『お問い合わせ』の語と入力欄を持っていたため 1 位で
  ;; 掴まれ、実際の窓口 `/contact/sales/` を押しのけた。**通ることと、正しいことは別。**
  #"(?i)/(company|corporate|about|profile|access|recruit|career|privacy|policy|news|blog|ir)(/|$)")

(defn score-contact-candidate
  "候補 URL の連絡窓口らしさ。大きいほど良い。**fetch の前に順序を決める**ので、
   1 件目が通った時点で止めてよくなる（＝リクエストを増やさずに精度が上がる）。

   `opts` に `{:strong-re .. :decoy-re ..}` を渡すと語彙を差し替えられる。"
  ([url] (score-contact-candidate url nil))
  ([url {:keys [strong-re decoy-re]}]
   (let [strong-re (or strong-re strong-path-re)
         decoy-re (or decoy-re decoy-path-re)
         path (or (second (re-find #"^https?://[^/]+(/.*)$" (str url))) "/")]
     (cond-> 0
       (re-find strong-re path) (+ 100)
       (re-find decoy-re path) (- 80)
       true (- (min 40 (count path)))))))

(defn rank-contact-candidates
  "候補を良い順に並べる。同点は入力順を保つ。"
  ([urls] (rank-contact-candidates urls nil))
  ([urls opts]
   (vec (sort-by (fn [u] (- (score-contact-candidate u opts))) (distinct urls)))))

(def common-contact-paths
  "autodiscovery が空振りしたときの当て先。**当てただけでは載せない。**
   順序は日本企業サイトで実際に当たりやすい順。"
  ["/contact" "/contact/" "/contact-us" "/inquiry" "/otoiawase" "/toiawase"
   "/support/contact" "/company/contact" "/ja/contact" "/contact/index.html"])

(defn contact-page?
  "取得できた HTML が実際に連絡点かどうか。form か mailto か、連絡を表す語が
   本文に在ることを求める —— 200 を返しただけの SPA シェルを連絡点にしない。

   `text-re` を渡すと語彙を差し替えられる。省略すると日本語の既定。"
  ([html] (contact-page? html nil))
  ([html text-re]
   (let [text-re (or text-re contact-text-re)
         h (str html)
         text (strip-tags h)]
     (boolean
      (or (re-find #"(?i)<form[\s>]" h)
          (re-find #"(?i)mailto:" h)
          (and (re-find text-re text)
               (re-find #"(?i)(<input[\s>]|<textarea[\s>]|電話|TEL|E-?mail|メール|Telefon|Tel\.|Téléphone|Teléfono|Telefono)" h)))))))

;; ---------------------------------------------------------------------------
;; メール

(def ^:private mailto-re #"(?i)mailto:([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})")
(def ^:private text-email-re #"(?i)\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")

(def ^:private junk-email-re
  ;; 実測で拾ってしまったもの: 解析タグ・CMS ベンダ・サンプル・画像ファイル名。
  #"(?i)(example\.(com|org|net)|sentry\.io|wixpress|\.png$|\.jpe?g$|\.gif$|@sentry|@2x|your-?email|test@)")

(def role-locals
  "窓口アドレスの local part。会社の連絡窓口であって個人ではない。"
  #{"info" "contact" "contactus" "contact-us" "inquiry" "inquiries" "otoiawase"
    "toiawase" "sales" "support" "office" "hello" "mail" "webmaster" "admin"
    "press" "pr" "recruit" "hr" "biz" "business" "partner" "partners" "cs"
    "customer" "help" "service" "marketing" "ir" "info-jp" "japan"})

(defn classify-email
  "アドレス -> `:role` / `:personal`。

   個人名らしさは local part に `.` や `_` で区切られた 2 語が在るか、または
   role 語彙に無い短い語であるかで見る。**確実な判定ではない**ので、迷ったら
   `:personal` に倒す —— 誤って個人アドレスを窓口として出力するより、
   誤って窓口を落とす方が安い。"
  [email]
  (let [local (str/lower (str/trim (first (str/split (str email) #"@"))))]
    (cond
      (contains? role-locals local) :role
      (re-find #"^(info|contact|inquiry|sales|support|office|hello|press|recruit)[._\-]" local) :role
      :else :personal)))

(defn extract-emails
  "HTML -> 公開されているメールアドレス。

   `mailto:` を先に取るのは、**サイトがそれを連絡リンクとして張った**という
   意思表示だから。本文テキストからの抽出も行うが、出所を分けて記録する
   （`:mailto` / `:text`）—— 前者は連絡先、後者は本文にたまたま在った文字列でもありうる。"
  [html]
  (let [h (str html)
        mailtos (->> (re-seq mailto-re h) (map second))
        texts (->> (re-seq text-email-re (strip-tags h)) (map second))
        clean (fn [xs] (->> xs
                            (map str/trim)
                            (map str/lower)
                            (remove #(re-find junk-email-re %))
                            distinct))
        mailtos (clean mailtos)
        texts (remove (set mailtos) (clean texts))]
    (vec (concat (map (fn [e] {:email e :via :mailto :kind (classify-email e)}) mailtos)
                 (map (fn [e] {:email e :via :text :kind (classify-email e)}) texts)))))

;; ---------------------------------------------------------------------------
;; 営業お断りの観測

(def solicitation-forbidden-re
  #"(?i)(営業目的|営業・?勧誘|勧誘目的|セールス目的|売り込み|営業のお問い?合わ?せ|営業メール|広告・?宣伝目的|営業活動を目的|no\s+solicitation|not\s+accept\s+(sales|marketing)|sales\s+inquiries\s+are\s+not)")

(defn solicitation-forbidden?
  "相手のページが営業目的の連絡を断っているか。**こちらの判断ではなく観測**。
   true の行に cold outbound をしない（`outbound-leads-p0.csv` が Preferred
   Networks に `skip-cold` と書いたのと同じ列を、機械で埋める）。

   `re` を渡すと語彙を差し替えられる。省略すると日本語 + 最小限の英語の既定 ——
   **EU の面でこれを既定のまま使わない**（独語・仏語・西語を 1 語も見ない）。"
  ([html] (solicitation-forbidden? html nil))
  ([html re]
   (boolean (re-find (or re solicitation-forbidden-re) (strip-tags html)))))

;; ---------------------------------------------------------------------------
;; 住所

(def ^:private postal-re
  ;; 区切りは半角ハイフンだけではない。実測で当たった全角ハイフンマイナス（U+FF0D）が
  ;; 抜けていて、全角で書かれた 〒 を 1 件も拾えていなかった。
  #"〒\s*([0-9０-９]{3})\s*[-‐−ー–－―ー]\s*([0-9０-９]{4})")

(defn- zenkaku->ascii [s]
  (reduce (fn [acc [z a]] (str/replace acc z a))
          (str s)
          [["０" "0"] ["１" "1"] ["２" "2"] ["３" "3"] ["４" "4"]
           ["５" "5"] ["６" "6"] ["７" "7"] ["８" "8"] ["９" "9"]]))

(defn format-postal-code
  "registry の `1070062` -> `107-0062`。7 桁でなければそのまま返す（捏造しない）。"
  [pc]
  (let [s (str/replace (zenkaku->ascii (str pc)) #"[^0-9]" "")]
    (if (= 7 (count s)) (str (subs s 0 3) "-" (subs s 3)) (str pc))))

(defn extract-site-postal-code
  "ページ本文に 〒 が在ればそれを拾う。**登記の所在地を上書きしない** ——
   支社・営業所であることがあるので、別の列として記録するためだけに使う。"
  [html]
  (when-let [m (re-find postal-re (strip-tags html))]
    (str (zenkaku->ascii (nth m 1)) "-" (zenkaku->ascii (nth m 2)))))

;; ---------------------------------------------------------------------------
;; レコード

(defn- put [m k v]
  (if (or (nil? v) (and (string? v) (str/blank? v)) (and (coll? v) (empty? v)))
    m
    (assoc m k v)))

(defn ->record
  "登記側の事実 + 観測 -> 1 社 1 レコード。

   `registry` は gBizINFO の `/v2/hojin/{n}` レスポンス 1 件（string キー）。
   `observation` は収集器が実際に取れたもの:
     `{:status ... :contact-url ... :emails [...] :solicitation-forbidden? ...
       :site-postal-code ... :observed-at ...}`

   **status が `:ok` 以外でもレコードは作る。** 「見に行けなかった会社」の行が
   消えると、次の run が同じ会社をまた見に行き、同じ理由でまた消える。"
  [registry observation]
  (let [status (:status observation)
        _ (assert (contains? statuses status) (str "unknown lead status: " status))
        role-emails (->> (:emails observation)
                         (filter #(= :role (:kind %)))
                         (reduce (fn [acc e] (if (some #(= (:email %) (:email e)) acc) acc (conj acc e))) []))
        emails (mapv :email role-emails)
        ;; **出所を落とさない。** `mailto:` はサイトが連絡リンクとして張ったもの、
        ;; `text` は本文にたまたま在った文字列で、同じ扱いにする理由が無い。
        ;; 以前はここで `:email` だけを取り出しており、`extract-emails` が分けて
        ;; いた出所が台帳に 1 件も残っていなかった（実測 2026-08-26: 台帳の
        ;; `:via` は 0 件）。**純関数が区別していることと、記録に残ることは別。**
        emails-via (mapv (fn [e] {:email (:email e) :via (name (:via e))}) role-emails)
        personal-n (count (filter #(= :personal (:kind %)) (:emails observation)))]
    (-> {:source/dataset dataset
         :source/authority authority-id
         :company/houjin-bangou (get registry "corporate_number")
         :company/jurisdiction "JP"
         :lead/status status}
        (put :company/legal-name (get registry "name"))
        (put :company/legal-name-en (get registry "name_en"))
        (put :company/representative-name (some-> (get registry "representative_name")
                                                  str (str/replace #"[　\s]+" " ") str/trim))
        (put :company/location (get registry "location"))
        (put :company/postal-code (some-> (get registry "postal_code") format-postal-code))
        (put :company/employee-number (get registry "employee_number"))
        (put :company/capital-stock (get registry "capital_stock"))
        (put :company/industry (some-> (get registry "industry") vec))
        (put :company/business-summary (get registry "business_summary"))
        (put :company/date-of-establishment (get registry "date_of_establishment"))
        (put :web/url (normalise-url (get registry "company_url")))
        ;; URL の出所を残す。登記の自己申告と、こちらが手で当てた URL を混ぜない
        ;; —— 後者は「その会社がそう名乗った」ではなく「私たちがそう当てた」である。
        (put :web/url-source (some-> (:web-url-source observation) name))
        (put :contact/form-url (:contact-url observation))
        (put :contact/emails emails)
        (put :contact/emails-via emails-via)
        (put :contact/site-postal-code (:site-postal-code observation))
        (put :contact/personal-emails-excluded (when (pos? personal-n) personal-n))
        (put :contact/solicitation-forbidden? (:solicitation-forbidden? observation))
        (put :source/observed-at (:observed-at observation))
        (put :lead/name-match (some-> (:name-match observation) name))
        (put :lead/rejected-candidates (:rejected-candidates observation))
        (put :lead/note (:note observation)))))

(defn contactable?
  "outbound に出してよい行か。**status と営業お断りの両方を見る。**
   片方だけ見ると、見に行けなかった会社に営業をかけるか、断っている会社に
   営業をかけるかのどちらかになる。"
  [record]
  (and (= :ok (:lead/status record))
       (not (:contact/solicitation-forbidden? record))
       (boolean (or (:contact/form-url record) (seq (:contact/emails record))))))

(defn coverage
  "レコード列 -> 何を測れて何を測れなかったかの 1 entity。

   **`:scanned` は分母であって成果ではない。** これを出すのは、次に読む人が
   『連絡先が取れた会社が N 件』と『見に行けた会社が N 件』を区別できるように
   するためで、`:ok` だけを数えると取りこぼしが clean に見える。"
  [records]
  (let [by-status (frequencies (map :lead/status records))]
    {:source/dataset dataset
     :coverage/scanned (count records)
     :coverage/by-status by-status
     :coverage/contactable (count (filter contactable? records))
     :coverage/solicitation-forbidden (count (filter :contact/solicitation-forbidden? records))
     :coverage/with-form-url (count (filter :contact/form-url records))
     :coverage/with-role-email (count (filter #(seq (:contact/emails %)) records))}))

;; ---------------------------------------------------------------------------
;; registry を持たない面 —— URL から始める
;;
;; 上のレコードは**法人番号が起点**で、gBizINFO の詳細に載っている `company_url`
;; を見に行く。実測 2026-08-26、節税 ICP ではその URL 保有率が 4% だったので、
;; 母集団の 96% に対して起点そのものが無かった。
;;
;; 士業・IT 顧問のような専門サービス業は逆で、**サイトの側が先に手に入る**。
;; その面のためのレコードをここに置く。**法人番号を持たない**ことが、この面と
;; 上の面の決定的な違いである —— だから `:company/houjin-bangou` を nil で置かず、
;; **キーごと出さない**。無い列と、空の列は違う。

(def site-dataset "lead-site-contact-point")

(def site-authority-id "self-published (operator-discovered site)")

(def site-attribution
  "連絡点は各社の自己公表ページ（`:contact/source-url` に URL、`:source/observed-at` に取得時刻）。サイトの発見経路は `:site/discovery` に記録する。登記情報は含まない。")

(def discovery-methods
  "`:site/discovery` の値域。**閉じている。** どうやってその URL に辿り着いたかは
   `:web/url-source` とは別の問い —— 後者は『誰がそう言ったか』、こちらは
   『どう見つけたか』である。前者だけだと、web 検索で拾った URL と、人が名簿を
   見て打ち込んだ URL が同じ `operator-supplied` になる。"
  #{:web-search :operator-listed :directory-listing})

(defn ->site-record
  "`{:name .. :url .. :segment .. :discovery .. :query ..}` + observation -> 1 レコード。

   `segment` は営業側の区分（`\"tax-office\"` / `\"it-partner\"` など）で、
   **こちらが付けた札**である。相手がそう名乗ったわけではないので `:site/*` に置く。

   status が `:ok` 以外でもレコードは作る（理由は `->record` と同じ）。"
  [{:keys [name url segment discovery query]} observation]
  (let [status (:status observation)
        _ (assert (contains? statuses status) (str "unknown lead status: " status))
        _ (assert (or (nil? discovery) (contains? discovery-methods discovery))
                  (str "unknown discovery method: " discovery))
        role-emails (->> (:emails observation)
                         (filter #(= :role (:kind %)))
                         (reduce (fn [acc e]
                                   (if (some #(= (:email %) (:email e)) acc) acc (conj acc e)))
                                 []))
        personal-n (count (filter #(= :personal (:kind %)) (:emails observation)))]
    (-> {:source/dataset site-dataset
         :source/authority site-authority-id
         :company/jurisdiction "JP"
         :lead/status status}
        (put :site/name name)
        (put :site/segment segment)
        (put :site/discovery (some-> discovery clojure.core/name))
        (put :site/discovery-query query)
        (put :web/url (normalise-url url))
        (put :web/url-source "operator-supplied")
        (put :contact/form-url (:contact-url observation))
        (put :contact/emails (mapv :email role-emails))
        (put :contact/emails-via (mapv (fn [e] {:email (:email e)
                                                :via (clojure.core/name (:via e))})
                                       role-emails))
        (put :contact/site-postal-code (:site-postal-code observation))
        (put :contact/personal-emails-excluded (when (pos? personal-n) personal-n))
        (put :contact/solicitation-forbidden? (:solicitation-forbidden? observation))
        (put :source/observed-at (:observed-at observation))
        (put :lead/note (:note observation)))))

(defn site-coverage
  "`coverage` に、この面でだけ意味のある 2 つを足す。

   - `:coverage/email-only-personal` —— **メールは公開していたが、窓口ではなく
     個人名のアドレスだった**社の数。これを別に数えないと、規律で落とした分が
     『メールを公開していない会社』に混ざり、母集団の到達可能性を実際より低く
     見積もる（逆に、規律を緩めれば伸びる余地がどれだけ在るかも判らなくなる）。
   - `:coverage/by-segment` —— 区分ごとの窓口メール取得率。**segment を分けた
     まま数えないと、仮説そのものを検証できない。**"
  [records]
  (assoc (coverage records)
         :source/dataset site-dataset
         :coverage/email-only-personal
         (count (filter #(and (empty? (:contact/emails %))
                              (pos? (or (:contact/personal-emails-excluded %) 0)))
                        records))
         :coverage/by-segment
         (into {}
               (for [[seg rs] (group-by :site/segment records)]
                 [(or seg "unsegmented")
                  {:scanned (count rs)
                   :with-role-email (count (filter #(seq (:contact/emails %)) rs))
                   :with-form-url (count (filter :contact/form-url rs))
                   :contactable (count (filter contactable? rs))
                   :solicitation-forbidden (count (filter :contact/solicitation-forbidden? rs))
                   :fetch-failed (count (filter #(= :fetch-failed (:lead/status %)) rs))}]))))
